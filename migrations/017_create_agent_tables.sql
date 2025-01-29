-- Create agent table
CREATE TABLE agent (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model VARCHAR(50) DEFAULT 'gpt-4o',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Create prompt table
CREATE TABLE prompt (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    version INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE (agent_id, version)
);

-- Create message table
CREATE TABLE message (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    prompt_version INTEGER NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    FOREIGN KEY (agent_id, prompt_version) REFERENCES prompt(agent_id, version)
);

-- Create indexes
CREATE INDEX idx_agent_name ON agent(name);
CREATE INDEX idx_prompt_agent_version ON prompt(agent_id, version);
CREATE INDEX idx_prompt_agent_active ON prompt(agent_id, is_active);
CREATE INDEX idx_message_agent_prompt ON message(agent_id, prompt_version);
CREATE INDEX idx_message_created_at ON message(created_at);

-- Create trigger to update agent.updated_at
CREATE OR REPLACE FUNCTION update_agent_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_agent_updated_at
    BEFORE UPDATE ON agent
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_updated_at(); 