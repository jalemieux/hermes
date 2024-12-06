from datetime import datetime
import logging
import os
from pathlib import Path
import uuid
from elevenlabs import ElevenLabs, VoiceSettings
from openai import OpenAI
from config import Config
from app.models import Summary, db
from pydub import AudioSegment
import io

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
        
        if summary.key_points:
            segments.append("Key Points:")
            for point in summary.key_points:
                segments.append(f"• {point['text']}")
        
        if summary.sections:
            for section in summary.sections:
                segments.append(f"{section['header']}:")
                segments.append(section['content'])
        
        return segments
    
    def eleven_labs_text_to_speech(self, file_path, summary: Summary) -> str:
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
        with open(file_path, 'wb') as file:
            for chunk in data:
                file.write(chunk)
        return file_path
    


    def _coalesce_audio_segments(self, audio_segments: list, output_path: str, pause_duration: int = 2000) -> None:
        """
        Combines audio segments with pauses between them.
        
        Args:
            audio_segments: List of audio response objects from OpenAI
            output_path: Path where the final audio file will be saved
            pause_duration: Duration of pause between segments in milliseconds (default 2000ms = 2s)
        """
        # Create a silent audio segment for pauses
        silence = AudioSegment.silent(duration=pause_duration)
        
        # Initialize an empty audio segment
        final_audio = AudioSegment.empty()
        
        for i, segment in enumerate(audio_segments):
            # Convert the audio bytes to an AudioSegment
            #segment_bytes = io.BytesIO()
            #segment.stream_to_file(segment_bytes)
            #segment_bytes.seek(0)
            audio_segment = AudioSegment.from_mp3(segment)
            
            # Add the audio segment
            final_audio += audio_segment
            
            # Add silence after each segment (except the last one)
            if i < len(audio_segments) - 1:
                final_audio += silence
        
        # Export the final audio file
        final_audio.export(output_path, format="mp3")

    def openai_text_to_speech(self, file_path: str, summary: Summary) -> str:
        segments = self._generate_summary_list(summary)
        audio_segments = []
        #speech_file_path = Path(__file__).parent / file_path

        for segment in segments:
            response = self.client_openai.audio.speech.create(
                model="tts-1",
                voice="alloy", 
                input=segment
            )
            tmp_file = f"tmp_{uuid.uuid4()}.mp3"
            response.write_to_file(tmp_file)
            audio_segments.append(tmp_file)

        # Use the new coalesce function instead of direct writing
        self._coalesce_audio_segments(audio_segments, file_path)
        # Clean up temporary audio files
        for tmp_file in audio_segments:
            try:
                os.remove(tmp_file)
            except OSError as e:
                logging.warning(f"Error removing temporary file {tmp_file}: {e}")

        return file_path

    def generate_voice_clip(self, summary_id: int) -> bool:
        """
        Generate a voice clip for a given summary.
        
        Args:
            summary_id: The ID of the summary to generate voice for
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            summary = Summary.query.get(summary_id)
            if not summary:
                logging.error(f"Summary {summary_id} not found")
                return False

            
            # Convert text to speech
            # Generate unique filename based on summary ID and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"app/static/audio/summary_{summary_id}_{timestamp}.mp3"
            if Config.VOICE_GENERATOR == "elevenlabs":
                self.eleven_labs_text_to_speech(file_path, summary)
            else:
                self.openai_text_to_speech(file_path, summary)
            
            # Update summary record with audio information
            summary.has_audio = True
            summary.audio_url = f"/static/audio/summary_{summary_id}_{timestamp}.mp3"
            db.session.commit()
            
            logging.info(f"Successfully generated voice clip for summary {summary_id}")
            return True
            
        except Exception as e:
            raise e
            logging.error(f"Error generating voice clip for summary {summary_id}: {str(e)} {e.traceback}")
            return False 