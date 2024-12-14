-- Drop existing newsletter table
DROP TABLE IF EXISTS newsletter;

-- Create new newsletter table with current model structure
CREATE TABLE newsletter (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    sender VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    subject VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    latest_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES "user" (id)
);

-- Create index on user_id for better query performance
CREATE INDEX idx_newsletter_user_id ON newsletter(user_id);

-- Create index on latest_date for sorting
CREATE INDEX idx_newsletter_latest_date ON newsletter(latest_date); 