-- Migration: 009 Add cascade delete rules
-- Description: Adds ON DELETE CASCADE rules to foreign key relationships
-- Created: 2024-03-19

-- First drop existing foreign key constraints
ALTER TABLE summary DROP CONSTRAINT IF EXISTS summary_user_id_fkey;
ALTER TABLE news DROP CONSTRAINT IF EXISTS news_topic_id_fkey;
ALTER TABLE topic DROP CONSTRAINT IF EXISTS topic_email_id_fkey;
ALTER TABLE source DROP CONSTRAINT IF EXISTS source_email_id_fkey;
ALTER TABLE email DROP CONSTRAINT IF EXISTS email_user_id_fkey;
ALTER TABLE newsletter DROP CONSTRAINT IF EXISTS newsletter_user_id_fkey;

-- Re-add constraints with CASCADE delete rules
ALTER TABLE summary 
    ADD CONSTRAINT summary_user_id_fkey 
    FOREIGN KEY (user_id) 
    REFERENCES "user"(id) 
    ON DELETE CASCADE;

ALTER TABLE news 
    ADD CONSTRAINT news_topic_id_fkey 
    FOREIGN KEY (topic_id) 
    REFERENCES topic(id) 
    ON DELETE CASCADE;

ALTER TABLE topic 
    ADD CONSTRAINT topic_email_id_fkey 
    FOREIGN KEY (email_id) 
    REFERENCES email(id) 
    ON DELETE CASCADE;

ALTER TABLE source 
    ADD CONSTRAINT source_email_id_fkey 
    FOREIGN KEY (email_id) 
    REFERENCES email(id) 
    ON DELETE CASCADE;

ALTER TABLE email 
    ADD CONSTRAINT email_user_id_fkey 
    FOREIGN KEY (user_id) 
    REFERENCES "user"(id) 
    ON DELETE CASCADE;

ALTER TABLE newsletter 
    ADD CONSTRAINT newsletter_user_id_fkey 
    FOREIGN KEY (user_id) 
    REFERENCES "user"(id) 
    ON DELETE CASCADE; 