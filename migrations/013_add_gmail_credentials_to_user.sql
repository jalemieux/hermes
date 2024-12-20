-- Add Gmail credentials and selected newsletters columns to user table
ALTER TABLE "user" 
    ADD COLUMN gmail_credentials JSONB,
    ADD COLUMN selected_newsletters JSONB;

-- Add comment to explain the columns
COMMENT ON COLUMN "user".gmail_credentials IS 'Stores Gmail OAuth credentials as JSON';
COMMENT ON COLUMN "user".selected_newsletters IS 'Stores selected newsletter IDs and preferences as JSON';

-- Create an index on gmail_credentials to improve query performance
CREATE INDEX idx_user_gmail_credentials ON "user" ((gmail_credentials IS NOT NULL)); 