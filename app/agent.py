from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel
import openai
from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, ForeignKey
from app.models import db
from config import Config

class Prompt(db.Model):
    """Model to store prompt versions"""
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey('agent.id'), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    metadata = Column(JSON, nullable=True)
    is_active = Column(db.Boolean, default=True)
    
    def __init__(self, agent_id: int, content: str, description: str = None, metadata: dict = None):
        self.agent_id = agent_id
        self.content = content
        self.description = description
        self.metadata = metadata or {}
        # Get the latest version for this agent and increment
        latest = Prompt.query.filter_by(agent_id=agent_id).order_by(Prompt.version.desc()).first()
        self.version = (latest.version + 1) if latest else 1

class Message(db.Model):
    """Model to store conversation messages"""
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey('agent.id'), nullable=False)
    prompt_version = Column(Integer, nullable=False)
    role = Column(String(50), nullable=False)  # system, user, assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    metadata = Column(JSON, nullable=True)

class Agent(db.Model):
    """Model to store agent configurations and state"""
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    model = Column(String(50), default="gpt-4o")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    prompts = db.relationship('Prompt', backref='agent', lazy=True, cascade="all, delete-orphan")
    messages = db.relationship('Message', backref='agent', lazy=True, cascade="all, delete-orphan")
    
    def __init__(self, name: str, initial_prompt: str, model: str = "gpt-4o", description: str = None, metadata: dict = None):
        self.name = name
        self.model = model
        self.description = description
        self.metadata = metadata or {}
        
        # Create initial prompt version after agent is created
        db.session.add(self)
        db.session.flush()  # Get the agent ID
        self.create_prompt_version(initial_prompt, "Initial prompt")
        
    def create_prompt_version(self, content: str, description: str = None, metadata: dict = None) -> Prompt:
        """Create a new prompt version"""
        # Deactivate current prompt
        current_prompt = self.get_current_prompt()
        if current_prompt:
            current_prompt.is_active = False
            
        # Create new prompt version
        prompt = Prompt(
            agent_id=self.id,
            content=content,
            description=description,
            metadata=metadata
        )
        db.session.add(prompt)
        db.session.commit()
        return prompt
    
    def get_current_prompt(self) -> Optional[Prompt]:
        """Get the current active prompt"""
        return Prompt.query.filter_by(agent_id=self.id, is_active=True).first()
    
    def get_prompt_version(self, version: int) -> Optional[Prompt]:
        """Get a specific prompt version"""
        return Prompt.query.filter_by(agent_id=self.id, version=version).first()
    
    def get_prompt_history(self) -> List[Prompt]:
        """Get all prompt versions ordered by version"""
        return Prompt.query.filter_by(agent_id=self.id).order_by(Prompt.version.asc()).all()
        
    def add_message(self, role: str, content: str, metadata: dict = None) -> Message:
        """Add a message to the conversation history"""
        current_prompt = self.get_current_prompt()
        if not current_prompt:
            raise ValueError("No active prompt found for this agent")
            
        message = Message(
            agent_id=self.id,
            prompt_version=current_prompt.version,
            role=role,
            content=content,
            metadata=metadata
        )
        db.session.add(message)
        db.session.commit()
        return message
    
    def get_messages(self, limit: int = None, prompt_version: int = None) -> List[Message]:
        """Get conversation history, optionally limited to last n messages or specific prompt version"""
        query = Message.query.filter_by(agent_id=self.id)
        
        if prompt_version:
            query = query.filter_by(prompt_version=prompt_version)
            
        query = query.order_by(Message.created_at.asc())
        
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def clear_messages(self, prompt_version: int = None):
        """Clear messages, optionally only for a specific prompt version"""
        query = Message.query.filter_by(agent_id=self.id)
        if prompt_version:
            query = query.filter_by(prompt_version=prompt_version)
        query.delete()
        db.session.commit()
    
    def _format_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        """Format messages for OpenAI API"""
        return [{"role": msg.role, "content": msg.content} for msg in messages]
    
    def update_prompt(self, new_prompt: str, description: str = None, metadata: dict = None):
        """Create a new prompt version"""
        self.create_prompt_version(new_prompt, description, metadata)
        self.updated_at = datetime.now()
        db.session.commit()
    
    def update_metadata(self, metadata: dict):
        """Update the agent's metadata"""
        self.metadata = metadata
        self.updated_at = datetime.now()
        db.session.commit() 




