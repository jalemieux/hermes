from datetime import datetime
import logging
import os
from pathlib import Path
import uuid
from elevenlabs import ElevenLabs, VoiceSettings
from openai import OpenAI
from app.summary_generator import SummaryGenerator
from config import Config
from app.models import Email, Summary, db, AudioFile
from pydub import AudioSegment
import io
import tempfile

class VoiceClipGenerator:
    def __init__(self):
        self.client = ElevenLabs(
            api_key=Config.ELEVEN_LABS_API_KEY,
        )
        self.client_openai = OpenAI(api_key=Config.OPENAI_API_KEY)
        
    def _generate_summary_list(self, summary: Summary) -> list[str]:
        """Generate a list of text segments from a summary.
        
        Returns:
            list[str]: A list where each item is either a key point or a topic with its content
        """
        segments = [summary.title]
        
        if Config.INCLUDE_KEY_POINTS == "true":
            if summary.key_points:
                segments.append("Key Points:")
                for point in summary.key_points:
                    segments.append(f"• {point['text']}")
        
        if summary.sections:
            for section in summary.sections:
                segments.append(f"{section['header']}:")
                segments.append(section['content'])
        
        return segments
    
    def eleven_labs_text_to_speech(self, summary: Summary) -> bytes:
        text = summary.title + "\n\n --- --- --- --- \n\n" 
        text += "Key Points: \n--- --- --- \n"
        for point in summary.key_points:
            text += f"{point['text']}\n --- --- \n"
        
        text += " --- --- Topics: --- --- \n\n"
        for section in summary.sections:
            text += f"{section['header']}:\n{section['content']} --- --- \n\n"

        data = self.client.text_to_speech.convert(
                voice_id=Config.ELEVEN_LABS_VOICE_ID,
                model_id="eleven_turbo_v2",
                text=text,
                voice_settings=VoiceSettings(
                    stability=0.3,
                    similarity_boost=0.3
                )   
            )

        # Save the audio file
        buffer = io.BytesIO()
        for chunk in data:
            buffer.write(chunk)
        return buffer.getvalue()
    


    def _coalesce_audio_segments(self, audio_segments: list, pause_duration: int = 2000) -> bytes:
        """
        Combines audio segments with pauses between them.
        Returns the combined audio as bytes.
        """
        # Create a silent audio segment for pauses
        silence = AudioSegment.silent(duration=pause_duration)
        
        # Initialize an empty audio segment
        final_audio = AudioSegment.empty()
        
        for i, segment in enumerate(audio_segments):
            logging.info(f"Processing segment {segment}")
            audio_segment = AudioSegment.from_mp3(segment)
            
            # Add the audio segment
            final_audio += audio_segment
            
            # Add silence after each segment (except the last one)
            if i < len(audio_segments) - 1:
                final_audio += silence
        
        # Export to bytes instead of file
        buffer = io.BytesIO()
        final_audio.export(buffer, format="mp3")
        return buffer.getvalue()
    
   

    def _generate_email_segments(self, email_text: str) -> list[str]:
        """Generate a list of text segments from an email.
        Similar to _generate_summary_list but for email content.
        
        Args:
            email_text: The email content in markdown format
            
        Returns:
            list[str]: A list of text segments suitable for audio generation
        """
        # Split by double newlines to get paragraphs
        segments = []
        paragraphs = email_text.split('\n\n')
        
        for paragraph in paragraphs:
            # Skip empty paragraphs
            if not paragraph.strip():
                continue
                
            # Clean up the paragraph
            cleaned = paragraph.strip()
            if cleaned:
                segments.append(cleaned)
                
        return segments

    def openai_text_to_speech(self, content, content_type='summary') -> bytes:
        """Generate audio file from text using OpenAI's text-to-speech.
        Returns the audio data as bytes.
        """
        # Generate segments based on content type
        if content_type == 'summary':
            segments = self._generate_summary_list(content)
        else:  # email
            segments = self._generate_email_segments(content)
            
        audio_segments = []
        temp_dir = tempfile.mkdtemp()
        
        try:
            for segment in segments:
                response = self.client_openai.audio.speech.create(
                    model="tts-1",
                    voice="alloy", 
                    input=segment
                )
                tmp_file = os.path.join(temp_dir, f"tmp_{uuid.uuid4()}.mp3")
                response.write_to_file(tmp_file)
                audio_segments.append(tmp_file)

            # Use the new coalesce function to get bytes
            audio_data = self._coalesce_audio_segments(audio_segments)
            
            return audio_data
            
        finally:
            # Clean up temporary files and directory
            for tmp_file in audio_segments:
                try:
                    if os.path.exists(tmp_file):
                        os.remove(tmp_file)
                except OSError as e:
                    logging.warning(f"Error removing temporary file {tmp_file}: {e}")
            try:
                os.rmdir(temp_dir)
            except OSError as e:
                logging.warning(f"Error removing temporary directory {temp_dir}: {e}")

    def generate_voice_clip(self, summary_id=None, email_id=None):
        """Generate a voice clip for a given summary or email."""
        if summary_id:
            content = Summary.query.get(summary_id)
            content_type = 'summary'
            if not content:
                logging.error(f"Summary {summary_id} not found")
                return False
        elif email_id:
            content = Email.query.get(email_id)
            content_type = 'email'
            if not content:
                logging.error(f"Email {email_id} not found")
                return False
        else:
            logging.error("Neither summary_id nor email_id provided")
            return False

        try:
            # Generate audio data
            if Config.VOICE_GENERATOR == "elevenlabs":
                audio_data = self.eleven_labs_text_to_speech(content)
            else:
                audio_data = self.openai_text_to_speech(content, content_type)
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{'summary' if summary_id else 'email'}_{summary_id or email_id}_{timestamp}.mp3"
            
            # Create AudioFile record
            audio_file = AudioFile(
                filename=filename,
                data=audio_data,
                summary_id=summary_id,
                email_id=email_id
            )
            db.session.add(audio_file)
            
            # Update content record
            if summary_id:
                content.has_audio = True
            else:
                content.has_audio = True
            
            db.session.commit()
            logging.info(f"Successfully generated voice clip for {'summary' if summary_id else 'email'} {summary_id or email_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error generating voice clip: {str(e)}")
            db.session.rollback()
            return False 
        
    def email_to_audio(self, email) -> bool:
        logging.info(f"Processing email {email.id} from {email.name}")
            
        # Convert email content to audio-friendly format
        logging.info(f"Converting email {email.id} content to audio format")
        summary_generator = SummaryGenerator()
        audio_text = summary_generator.convert_to_audio_format(email.to_md())
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_filename = f"newsletter_{email.id}_{timestamp}.mp3"
        #audio_path = os.path.join(app.config['AUDIO_DIR'], audio_filename)
        logging.info(f"Generated audio filename: {audio_filename}")
        
        # Generate audio file
        logging.info(f"Generating audio file for email {email.id}")
        voice_data = self.openai_text_to_speech( audio_text, content_type="email")
        
        if voice_data:
            # Update email record
            logging.info(f"Successfully generated audio for email {email.id}, updating database record")
            email.has_audio = True
            # Create or update AudioFile record
            audio_file = AudioFile.query.filter_by(email_id=email.id).first()
            if audio_file:
                audio_file.filename = audio_filename
                audio_file.data = voice_data
            else:
                audio_file = AudioFile(
                    filename=audio_filename,
                    data=voice_data,
                    email_id=email.id
                )
                db.session.add(audio_file)
            db.session.commit()
            logging.info(f"Database record updated for email {email.id}")
            return True
        else:
            logging.info(f"Failed to generate audio for email {email.id}")
            return False