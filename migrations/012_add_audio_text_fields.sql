-- Migration: 012 Add audio_text fields to summary and email tables
-- Description: Adds audio_text column to both summary and email tables
-- Created: 2024-03-19

-- Add audio_text column to summary table
ALTER TABLE summary 
    ADD COLUMN IF NOT EXISTS audio_text TEXT;

-- Add audio_text column to email table
ALTER TABLE email 
    ADD COLUMN IF NOT EXISTS audio_text TEXT; 