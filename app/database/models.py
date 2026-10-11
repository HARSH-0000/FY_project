from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.session import Base


class User(Base):
    """User table for authentication."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    """Chat session table for conversation threads."""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=True)  # Auto-generated from first message
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Chat message table for storing conversation history."""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(JSON, nullable=False)  # Structured content
    route = Column(String(50), nullable=True)  # SIMPLE, VERIFICATION, COMPLEX
    sources = Column(JSON, nullable=True)  # Source citations
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")


class ResearchJob(Base):
    """Research job table."""
    __tablename__ = "research_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text, nullable=False)
    route = Column(String(50), nullable=False)  # SIMPLE, VERIFICATION, COMPLEX
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    evidence = relationship("Evidence", back_populates="research_job", cascade="all, delete-orphan")


class Evidence(Base):
    """Evidence table for research results."""
    __tablename__ = "evidence"
    
    id = Column(Integer, primary_key=True, index=True)
    research_job_id = Column(Integer, ForeignKey("research_jobs.id"), nullable=False)
    claim = Column(Text, nullable=False)
    source_title = Column(String(500), nullable=False)
    source_url = Column(Text, nullable=False)
    source_name = Column(String(200), nullable=True)
    evidence_text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    research_job = relationship("ResearchJob", back_populates="evidence")


class Document(Base):
    """Document table for uploaded files."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(10), nullable=False)  # pdf, docx, txt
    file_path = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=True)
    doc_metadata = Column(JSON, nullable=True)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    analyses = relationship("DocumentAnalysis", back_populates="document", cascade="all, delete-orphan")


class DocumentAnalysis(Base):
    """Document analysis table."""
    __tablename__ = "document_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    query = Column(Text, nullable=False)
    result = Column(JSON, nullable=True)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    document = relationship("Document", back_populates="analyses")


class PersistentMemory(Base):
    """Persistent memory for user preferences, session context, and research history."""
    __tablename__ = "persistent_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=True, index=True)
    category = Column(String(50), nullable=False, index=True)  # user_preferences, session_context, research_history
    memory_key = Column(String(100), nullable=False, index=True)
    memory_value = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
