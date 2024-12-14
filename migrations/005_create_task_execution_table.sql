-- Migration: 005 Create task execution table
-- Description: Creates table for tracking batch task executions
-- Created: 2024-03-19

CREATE TABLE IF NOT EXISTS task_execution (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    last_success TIMESTAMP,
    last_attempt TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    CONSTRAINT unique_task_name UNIQUE (task_name)
);

-- Add index on task_name for faster lookups
CREATE INDEX IF NOT EXISTS idx_task_execution_task_name ON task_execution(task_name); 