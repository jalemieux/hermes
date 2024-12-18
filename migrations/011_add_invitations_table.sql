CREATE TABLE invitation (
    id SERIAL PRIMARY KEY,
    email VARCHAR(120) NOT NULL UNIQUE,
    token VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    invited_by_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
);

CREATE INDEX idx_invitation_token ON invitation(token);
CREATE INDEX idx_invitation_email ON invitation(email); 