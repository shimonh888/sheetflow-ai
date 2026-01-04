"""
SheetFlow AI - Google OAuth2 Authentication Router
Handles Google OAuth2 flow and JWT token generation.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import UserResponse, UserWithToken, GoogleAuthURL, TokenResponse
from app.services.encryption import get_encryption

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Google OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# OAuth2 scopes
SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.readonly",
]


def create_access_token(user_id: str, expires_delta: timedelta = timedelta(days=7)) -> str:
    """Create JWT access token."""
    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


async def get_current_user(
    token: str = Query(..., alias="token"),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise credentials_exception
    
    return user


@router.get("/login", response_model=GoogleAuthURL)
async def login():
    """
    Get Google OAuth2 authorization URL.
    
    Returns the URL that the frontend should redirect users to
    for Google OAuth2 consent.
    """
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return GoogleAuthURL(auth_url=auth_url)


@router.get("/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Google OAuth2 callback.
    
    Exchanges the authorization code for tokens, fetches user info,
    creates/updates user in DB, and redirects to frontend with JWT.
    """
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                },
            )
            token_response.raise_for_status()
            tokens = token_response.json()
        
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)
        
        # Get user info
        async with httpx.AsyncClient() as client:
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()
        
        email = userinfo["email"]
        name = userinfo.get("name")
        picture = userinfo.get("picture")
        
        # Check if user exists
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        # Encrypt tokens
        encryption = get_encryption()
        encrypted_access = encryption.encrypt(access_token)
        encrypted_refresh = encryption.encrypt(refresh_token) if refresh_token else None
        token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        
        if user:
            # Update existing user
            user.name = name
            user.picture_url = picture
            user.google_token = encrypted_access
            if encrypted_refresh:
                user.refresh_token = encrypted_refresh
            user.token_expiry = token_expiry
            user.updated_at = datetime.utcnow()
        else:
            # Create new user
            user = User(
                email=email,
                name=name,
                picture_url=picture,
                google_token=encrypted_access,
                refresh_token=encrypted_refresh,
                token_expiry=token_expiry,
            )
            db.add(user)
        
        await db.commit()
        await db.refresh(user)
        
        # Create JWT for frontend
        jwt_token = create_access_token(str(user.id))
        
        # Redirect to frontend with token
        redirect_url = f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}"
        return RedirectResponse(url=redirect_url)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"OAuth token exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to authenticate with Google"
        )
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return current_user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout user.
    
    Note: JWT tokens are stateless, so this just returns success.
    Frontend should discard the token.
    """
    return {"message": "Logged out successfully"}


@router.post("/refresh-google-token")
async def refresh_google_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh the Google OAuth token using the refresh token.
    """
    if not current_user.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token available. Please re-authenticate."
        )
    
    encryption = get_encryption()
    refresh_token = encryption.decrypt(current_user.refresh_token)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            tokens = response.json()
        
        new_access_token = tokens["access_token"]
        expires_in = tokens.get("expires_in", 3600)
        
        # Update encrypted token
        current_user.google_token = encryption.encrypt(new_access_token)
        current_user.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        current_user.updated_at = datetime.utcnow()
        
        await db.commit()
        
        return {"message": "Token refreshed successfully"}
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to refresh Google token. Please re-authenticate."
        )
