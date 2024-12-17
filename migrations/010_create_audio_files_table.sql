-- Migration: 010 Create audio files table
-- Description: Creates table for storing audio file data with user relationship
-- Created: 2024-03-19

CREATE TABLE IF NOT EXISTS audio_files (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    audio_data BYTEA NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) 
        REFERENCES "user"(id) 
        ON DELETE CASCADE
);

-- Add index on filename for faster lookups
CREATE INDEX IF NOT EXISTS idx_audio_files_filename ON audio_files(filename);

-- Add index on user_id for faster relationship lookups
CREATE INDEX IF NOT EXISTS idx_audio_files_user_id ON audio_files(user_id);