"""
SheetFlow AI - Google Drive Service
Handles file operations with Google Drive API.
"""
import logging
from datetime import datetime
from io import BytesIO
from typing import Optional, List, Dict, Any

import httpx
from fastapi import HTTPException, status

from app.services.encryption import get_encryption
from app.models import User

logger = logging.getLogger(__name__)

# Google Drive API endpoints
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_FILES_URL = f"{DRIVE_API_BASE}/files"


class GoogleDriveService:
    """Service for interacting with Google Drive API."""
    
    def __init__(self, user: User):
        """
        Initialize with user's encrypted tokens.
        
        Args:
            user: User model with encrypted google_token
        """
        self.user = user
        self._access_token: Optional[str] = None
    
    @property
    def access_token(self) -> str:
        """Decrypt and cache access token."""
        if self._access_token is None:
            if not self.user.google_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No Google token available. Please re-authenticate."
                )
            encryption = get_encryption()
            self._access_token = encryption.decrypt(self.user.google_token)
        return self._access_token
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {"Authorization": f"Bearer {self.access_token}"}
    
    async def list_excel_files(
        self, 
        page_token: Optional[str] = None,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        List Excel files from user's Google Drive.
        
        Args:
            page_token: Token for pagination
            page_size: Number of files per page
            
        Returns:
            Dict with files list and next_page_token
        """
        # Query for Excel files
        query = (
            "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' "
            "or mimeType='application/vnd.ms-excel'"
        )
        
        params = {
            "q": query,
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,size)",
            "pageSize": page_size,
            "orderBy": "modifiedTime desc",
        }
        if page_token:
            params["pageToken"] = page_token
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                DRIVE_FILES_URL,
                headers=self._get_headers(),
                params=params
            )
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google token expired. Please refresh or re-authenticate."
                )
            
            response.raise_for_status()
            data = response.json()
        
        return {
            "files": data.get("files", []),
            "next_page_token": data.get("nextPageToken")
        }
    
    async def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """
        Get metadata for a specific file.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            File metadata dict
        """
        params = {
            "fields": "id,name,mimeType,modifiedTime,size"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                headers=self._get_headers(),
                params=params
            )
            
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found in Google Drive"
                )
            
            response.raise_for_status()
            return response.json()
    
    async def download_file(self, file_id: str) -> bytes:
        """
        Download file content from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            File content as bytes
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                headers=self._get_headers(),
                params={"alt": "media"}
            )
            
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found in Google Drive"
                )
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google token expired. Please refresh or re-authenticate."
                )
            
            response.raise_for_status()
            
            logger.info(f"Downloaded file {file_id}, size: {len(response.content)} bytes")
            return response.content
    
    async def get_file_modified_time(self, file_id: str) -> Optional[datetime]:
        """
        Get the last modified time of a file.
        
        Useful for checking if file has changed since last sync.
        """
        metadata = await self.get_file_metadata(file_id)
        modified_time_str = metadata.get("modifiedTime")
        
        if modified_time_str:
            # Parse ISO format datetime
            return datetime.fromisoformat(modified_time_str.replace("Z", "+00:00"))
        return None
