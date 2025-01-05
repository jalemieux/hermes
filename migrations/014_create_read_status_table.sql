-- Migration: 014 Create read status table
-- Description: Creates table for tracking read status of items
-- Created: 2024-03-20

-- Create read_status table
CREATE TABLE read_status (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL,
    item_type VARCHAR(20) NOT NULL,  -- 'summary', 'email', or 'newsletter'
    read_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Add unique constraint to prevent duplicate read status entries
    CONSTRAINT unique_read_status UNIQUE(user_id, item_id, item_type)
);

-- Create index for faster lookups by user_id
CREATE INDEX idx_read_status_user_id ON read_status(user_id);

-- Create index for item lookup
CREATE INDEX idx_read_status_item ON read_status(item_id, item_type);

-- Add comment to table
COMMENT ON TABLE read_status IS 'Tracks which items (summaries, emails, newsletters) have been read by users'; 