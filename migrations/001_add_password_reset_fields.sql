-- Migration: 001 Add password reset fields
-- Description: Adds reset token and expiry fields to user table
-- Created: 2024-03-19

-- Add reset token fields to user table
ALTER TABLE "user" 
    ADD COLUMN IF NOT EXISTS reset_token VARCHAR(100) UNIQUE,
    ADD COLUMN IF NOT EXISTS reset_token_expiry TIMESTAMP;
