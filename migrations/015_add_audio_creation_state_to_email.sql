-- Migration script to add audio_creation_state column to Email table
ALTER TABLE email ADD COLUMN audio_creation_state VARCHAR(20) DEFAULT 'none'; 