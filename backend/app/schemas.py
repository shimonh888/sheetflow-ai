"""
SheetFlow AI - Pydantic Schemas
Request/Response models for API validation.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ============================================================================
# User Schemas
# ============================================================================

class UserBase(BaseModel):
    """Base user properties."""
    email: EmailStr
    name: Optional[str] = None
    picture_url: Optional[str] = None


class UserCreate(UserBase):
    """Properties for creating a user (from OAuth)."""
    pass


class UserResponse(UserBase):
    """User response model (public info only)."""
    id: UUID
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserWithToken(UserResponse):
    """User response with JWT token for auth."""
    access_token: str
    token_type: str = "bearer"


# ============================================================================
# Dashboard Schemas
# ============================================================================

class DashboardCreate(BaseModel):
    """Properties for creating a dashboard."""
    file_id: str = Field(..., description="Google Drive file ID")
    file_name: str = Field(..., description="Original file name")
    title: Optional[str] = Field(None, description="Dashboard title")


class DashboardUpdate(BaseModel):
    """Properties for updating a dashboard."""
    title: Optional[str] = None
    description: Optional[str] = None
    dashboard_config: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None


class ChartConfig(BaseModel):
    """Individual chart configuration."""
    id: str
    type: str = Field(..., description="bar, line, pie, area, etc.")
    title: str
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    data_key: Optional[str] = None
    color: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class DashboardConfigSchema(BaseModel):
    """Full dashboard configuration."""
    charts: List[ChartConfig] = []
    layout: Optional[Dict[str, Any]] = None
    theme: Optional[str] = "dark"


class DashboardResponse(BaseModel):
    """Dashboard response model."""
    id: UUID
    file_id: str
    file_name: str
    title: Optional[str]
    description: Optional[str]
    sheet_names: List[str] = []
    dashboard_config: Optional[Dict[str, Any]]
    last_synced: Optional[datetime]
    last_sync_status: Optional[str]
    last_sync_message: Optional[str]
    is_public: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DashboardListResponse(BaseModel):
    """Paginated list of dashboards."""
    items: List[DashboardResponse]
    total: int
    page: int
    page_size: int


# ============================================================================
# Refresh Schemas
# ============================================================================

class SchemaDriftInfo(BaseModel):
    """Information about detected schema changes."""
    sheet_name: str
    added_columns: List[str] = []
    removed_columns: List[str] = []
    renamed_columns: Dict[str, str] = {}  # old_name -> new_name
    type_changes: Dict[str, Dict[str, str]] = {}  # column -> {old: type, new: type}


class RefreshRequest(BaseModel):
    """Optional parameters for refresh."""
    force_reprocess: bool = Field(False, description="Force full reprocessing even if no changes")
    accept_schema_drift: bool = Field(True, description="Auto-accept detected schema changes")


class RefreshResponse(BaseModel):
    """Response from dashboard refresh."""
    success: bool
    message: str
    dashboard_id: UUID
    last_synced: datetime
    schema_drift_detected: bool = False
    schema_drift_info: Optional[List[SchemaDriftInfo]] = None
    chart_data: Optional[Dict[str, Any]] = None


# ============================================================================
# Google Drive Schemas
# ============================================================================

class DriveFile(BaseModel):
    """Google Drive file info."""
    id: str
    name: str
    mime_type: str
    modified_time: Optional[datetime] = None
    size: Optional[int] = None
    is_folder: bool = False


class DriveFilesResponse(BaseModel):
    """List of Drive files."""
    files: List[DriveFile]
    next_page_token: Optional[str] = None
    current_folder_id: Optional[str] = None


# ============================================================================
# Auth Schemas
# ============================================================================

class GoogleAuthURL(BaseModel):
    """Google OAuth URL response."""
    auth_url: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
