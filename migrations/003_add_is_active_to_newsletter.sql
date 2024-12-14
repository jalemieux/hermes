-- Migration: 003 Add is_active column to newsletter table
-- Description: Adds is_active boolean column with default true
-- Created: 2024-03-19

ALTER TABLE newsletter 
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true; 