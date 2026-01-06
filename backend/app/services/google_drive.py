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
    
    async def list_folder_contents(
        self, 
        folder_id: Optional[str] = None,
        search_query: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        List folders and Excel files from user's Google Drive.
        
        Args:
            folder_id: Parent folder ID (None = root/all accessible files)
            search_query: Optional search filter for file names
            page_token: Token for pagination
            page_size: Number of files per page
            
        Returns:
            Dict with files list (including folders) and next_page_token
        """
        # Build query for Excel files AND folders
        mime_conditions = (
            "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' "
            "or mimeType='application/vnd.ms-excel' "
            "or mimeType='application/vnd.google-apps.folder'"
        )
        
        query_parts = [f"({mime_conditions})"]
        
        # Add folder filter if specified
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        
        # Add search filter if specified
        if search_query:
            # Escape single quotes in search query
            safe_query = search_query.replace("'", "\\'")
            query_parts.append(f"name contains '{safe_query}'")
        
        # Exclude trashed files
        query_parts.append("trashed = false")
        
        query = " and ".join(query_parts)
        
        params = {
            "q": query,
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,size,parents)",
            "pageSize": page_size,
            "orderBy": "folder,name",  # Folders first, then alphabetically
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
        
        # Add is_folder flag to each file
        files = []
        for f in data.get("files", []):
            files.append({
                **f,
                "is_folder": f.get("mimeType") == "application/vnd.google-apps.folder"
            })
        
        return {
            "files": files,
            "next_page_token": data.get("nextPageToken"),
            "current_folder_id": folder_id
        }
    
    async def list_excel_files(
        self, 
        page_token: Optional[str] = None,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        List Excel files from user's Google Drive (legacy method for backwards compatibility).
        
        Args:
            page_token: Token for pagination
            page_size: Number of files per page
            
        Returns:
            Dict with files list and next_page_token
        """
        # Use list_folder_contents but filter out folders
        result = await self.list_folder_contents(
            folder_id=None,
            search_query=None,
            page_token=page_token,
            page_size=page_size
        )
        
        # Filter out folders for backwards compatibility
        result["files"] = [f for f in result["files"] if not f.get("is_folder")]
        return result
    
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
