"""
SheetFlow AI - Configuration Settings
Pydantic Settings for environment variables with validation.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "SheetFlow AI"
    DEBUG: bool = False
    SECRET_KEY: str = Field(..., description="Secret key for JWT signing")
    
    # Database
    DATABASE_URL: str = Field(
        ..., 
        description="PostgreSQL connection string",
        examples=["postgresql+asyncpg://user:pass@localhost:5432/sheetflow"]
    )
    
    # Google OAuth2
    GOOGLE_CLIENT_ID: str = Field(..., description="Google OAuth2 Client ID")
    GOOGLE_CLIENT_SECRET: str = Field(..., description="Google OAuth2 Client Secret")
    GOOGLE_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/auth/callback",
        description="OAuth2 callback URL"
    )
    
    # Token Encryption
    ENCRYPTION_KEY: str = Field(
        ..., 
        description="Fernet encryption key for token storage (32 url-safe base64 chars)"
    )
    
    # Gemini AI
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API key")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash", description="Gemini model name")
    
    # Frontend
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Frontend URL for CORS and redirects"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
