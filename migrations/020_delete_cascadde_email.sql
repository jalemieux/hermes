ALTER TABLE topic
ADD CONSTRAINT fk_topic_email
FOREIGN KEY (email_id) REFERENCES email(id)
ON DELETE CASCADE;

ALTER TABLE news DROP CONSTRAINT news_topic_id_fkey;

ALTER TABLE news
ADD CONSTRAINT news_topic_id_fkey
FOREIGN KEY (topic_id) REFERENCES topic(id)
ON DELETE CASCADE;

ALTER TABLE source DROP CONSTRAINT fk_source_email;  -- Replace with the actual constraint name if different

ALTER TABLE source
ADD CONSTRAINT fk_source_email
FOREIGN KEY (email_id) REFERENCES email(id)
ON DELETE CASCADE;