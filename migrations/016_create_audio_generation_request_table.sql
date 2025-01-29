CREATE TABLE AsyncProcessingRequest (
    id SERIAL PRIMARY KEY,
    email_id INTEGER NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES Email(id)
); 