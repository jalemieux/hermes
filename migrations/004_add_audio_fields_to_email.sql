-- Migration: 004 Add audio fields to email table
-- Description: Adds audio filename and has_audio flag to email table
-- Created: 2024-03-19

ALTER TABLE email 
    ADD COLUMN IF NOT EXISTS audio_filename VARCHAR(255),
    ADD COLUMN IF NOT EXISTS has_audio BOOLEAN NOT NULL DEFAULT false; 