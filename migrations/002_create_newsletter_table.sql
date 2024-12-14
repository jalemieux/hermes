-- Migration: 002 Create newsletter table
-- Description: Creates table for storing newsletter subscriptions
-- Created: 2024-03-19

CREATE TABLE IF NOT EXISTS newsletter (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    is_subscribed BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
    frequency VARCHAR(20) NOT NULL DEFAULT 'weekly',
    last_sent_at TIMESTAMP
);
