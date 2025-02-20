ALTER TABLE email ADD COLUMN cleaned_content TEXT;
ALTER TABLE email ADD COLUMN sender TEXT;
ALTER TABLE email ADD COLUMN text_content TEXT;
ALTER TABLE email ADD COLUMN is_summarized BOOLEAN default false