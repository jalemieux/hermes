-- Migration: 010 Create audio_files table and remove file-based audio columns
-- Created: 2024-03-19

-- First drop the old audio-related columns
ALTER TABLE summary 
    DROP COLUMN IF EXISTS audio_filename,
    DROP COLUMN IF EXISTS audio_url;

ALTER TABLE email 
    DROP COLUMN IF EXISTS audio_filename;

-- Create the new audio_files table
CREATE TABLE audio_file (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    data BYTEA NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    summary_id INTEGER REFERENCES summary(id) ON DELETE CASCADE,
    email_id INTEGER REFERENCES email(id) ON DELETE CASCADE,
    CONSTRAINT one_content_type CHECK (
        (summary_id IS NOT NULL AND email_id IS NULL) OR
        (summary_id IS NULL AND email_id IS NOT NULL)
    )
);

-- Create indexes for better query performance
CREATE INDEX idx_audio_file_summary_id ON audio_file(summary_id);
CREATE INDEX idx_audio_file_email_id ON audio_file(email_id);