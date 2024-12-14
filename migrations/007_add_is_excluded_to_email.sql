-- Migration: 007 Add is_excluded to email table
-- Description: Adds is_excluded boolean column with default false
-- Created: 2024-03-19

ALTER TABLE email 
    ADD COLUMN IF NOT EXISTS is_excluded BOOLEAN DEFAULT FALSE; 