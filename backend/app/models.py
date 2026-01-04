"""
SheetFlow AI - Database Models
SQLAlchemy models with encrypted token storage.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, LargeBinary, Boolean
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """
    User model with encrypted OAuth tokens.
    
    Tokens are stored as LargeBinary (Fernet-encrypted bytes).
    Use the TokenEncryption service to encrypt/decrypt.
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    picture_url = Column(Text, nullable=True)
    
    # Encrypted OAuth tokens (Fernet encrypted bytes)
    google_token = Column(LargeBinary, nullable=True)
    refresh_token = Column(LargeBinary, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    dashboards = relationship("Dashboard", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"


class Dashboard(Base):
    """
    Dashboard model with Excel file metadata and schema tracking.
    
    Stores the Google Drive file reference, sheet information,
    column schema for drift detection, and chart configurations.
    """
    __tablename__ = "dashboards"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Google Drive file info
    file_id = Column(String(255), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=True)
    
    # Multi-sheet tracking
    sheet_names = Column(ARRAY(String), nullable=True, default=list)
    
    # Schema drift detection - stores last known column structure per sheet
    # Format: {"sheet_name": {"columns": [...], "types": {...}}}
    column_schema = Column(JSONB, nullable=True, default=dict)
    
    # Dashboard configuration - chart types, layouts, etc.
    # Format: {"charts": [...], "layout": {...}, "theme": {...}}
    dashboard_config = Column(JSONB, nullable=True, default=dict)
    
    # Cached processed data for quick rendering
    # This is the unified DataFrame output from the AI agent
    cached_data = Column(JSONB, nullable=True)
    
    # Metadata
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)
    last_synced = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String(50), nullable=True)  # success, error, schema_drift
    last_sync_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="dashboards")
    
    def __repr__(self):
        return f"<Dashboard {self.title or self.file_name}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "file_id": self.file_id,
            "file_name": self.file_name,
            "title": self.title or self.file_name,
            "sheet_names": self.sheet_names or [],
            "dashboard_config": self.dashboard_config or {},
            "cached_data": self.cached_data,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
            "last_sync_status": self.last_sync_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
