-- Add summarization_type column to summary table
ALTER TABLE summary ADD COLUMN summarization_type VARCHAR(255);

-- Update existing records to have 'summarize_content' as the default value
UPDATE summary SET summarization_type = 'summarize_content' WHERE summarization_type IS NULL; mode