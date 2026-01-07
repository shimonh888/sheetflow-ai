"""
SheetFlow AI - Dashboards Router
Dashboard CRUD operations and refresh endpoint.
"""
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import User, Dashboard, FileSource
from app.schemas import (
    DashboardCreate, 
    DashboardUpdate, 
    DashboardResponse, 
    DashboardListResponse,
    RefreshRequest,
    RefreshResponse,
    DriveFilesResponse,
    DriveFile,
    ChartProposal,
    PreviewRequest,
    PreviewResponse,
    DataSummary,
    DashboardCreateWithCharts,
)
from app.routers.auth import get_current_user
from app.services.google_drive import GoogleDriveService
from app.services.ai_agent import DataProcessingAgent

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/drive-files", response_model=DriveFilesResponse)
async def list_drive_files(
    page_token: Optional[str] = None,
    folder_id: Optional[str] = Query(None, description="Folder ID to list contents of"),
    search: Optional[str] = Query(None, description="Search query for file names"),
    current_user: User = Depends(get_current_user),
):
    """
    List Excel files and folders from user's Google Drive.
    
    Used for the file picker when creating a new dashboard.
    Supports folder navigation and search.
    """
    drive_service = GoogleDriveService(current_user)
    result = await drive_service.list_folder_contents(
        folder_id=folder_id,
        search_query=search,
        page_token=page_token
    )
    
    files = [
        DriveFile(
            id=f["id"],
            name=f["name"],
            mime_type=f["mimeType"],
            modified_time=f.get("modifiedTime"),
            size=int(f["size"]) if f.get("size") else None,
            is_folder=f.get("is_folder", False)
        )
        for f in result["files"]
    ]
    
    return DriveFilesResponse(
        files=files,
        next_page_token=result.get("next_page_token"),
        current_folder_id=result.get("current_folder_id")
    )


@router.post("/preview", response_model=PreviewResponse)
async def preview_dashboard(
    data: PreviewRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Analyze multiple files and return chart proposals for user review.
    
    Does NOT create a dashboard - just returns AI suggestions
    that the user can edit before finalizing.
    """
    # 1. Download all files from Drive
    drive_service = GoogleDriveService(current_user)
    files_data = []
    
    try:
        for file in data.files:
            file_bytes = await drive_service.download_file(file.file_id)
            files_data.append({
                "file_id": file.file_id,
                "file_name": file.file_name,
                "file_bytes": file_bytes,
                "file_context": file.file_context
            })
    except Exception as e:
        logger.error(f"Failed to download files: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to download files: {str(e)}"
        )
    
    # 2. Run AI agent with multi-file context support
    try:
        agent = DataProcessingAgent(gemini_api_key=settings.GEMINI_API_KEY)
        result = await agent.process_multiple_files(
            files_data=files_data,
            global_description=data.global_description
        )
        
        # 3. Convert suggestions to ChartProposal format
        proposals = []
        for chart in result.suggested_charts:
            proposals.append(ChartProposal(
                id=chart.get("id", f"chart_{len(proposals)}"),
                type=chart.get("type", "bar"),
                title=chart.get("title", "Chart"),
                x_axis=chart.get("x_axis"),
                y_axis=chart.get("y_axis"),
                data_key=chart.get("data_key"),
                color=chart.get("color", "#14FF6E"),
                reasoning=chart.get("reasoning", "AI-suggested visualization for your data.")
            ))
        
        # 4. Build data summary for frontend editing
        data_summary = DataSummary(
            columns=[],
            numeric_cols=[],
            categorical_cols=[],
            date_cols=[],
            row_count=0
        )
        
        # Extract summary from chart_data if available
        if result.chart_data and "raw_data" in result.chart_data:
            raw_data = result.chart_data["raw_data"]
            if raw_data:
                import pandas as pd
                df = pd.DataFrame(raw_data)
                data_summary = DataSummary(
                    columns=list(df.columns),
                    numeric_cols=[col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])],
                    categorical_cols=[col for col in df.columns if df[col].dtype == 'object'],
                    date_cols=[col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])],
                    row_count=len(df)
                )
        
        # Use first file's info for response (backwards compatible)
        first_file = data.files[0] if data.files else None
        logger.info(f"Generated {len(proposals)} chart proposals for {len(data.files)} files")
        
        return PreviewResponse(
            file_id=first_file.file_id if first_file else "",
            file_name=first_file.file_name if first_file else "",
            sheet_names=result.sheet_names,
            proposals=proposals,
            data_summary=data_summary,
            preview_data=result.chart_data or {}
        )
        
    except Exception as e:
        logger.error(f"Failed to process files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze files: {str(e)}"
        )


@router.get("", response_model=DashboardListResponse)
async def list_dashboards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all dashboards for the current user."""
    # Get total count
    count_query = select(func.count(Dashboard.id)).where(Dashboard.user_id == current_user.id)
    total = (await db.execute(count_query)).scalar()
    
    # Get paginated results
    offset = (page - 1) * page_size
    query = (
        select(Dashboard)
        .where(Dashboard.user_id == current_user.id)
        .options(selectinload(Dashboard.file_sources))
        .order_by(Dashboard.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    dashboards = result.scalars().all()
    
    return DashboardListResponse(
        items=dashboards,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    data: DashboardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new dashboard from multiple Google Drive Excel files.
    
    This will:
    1. Verify file access in Google Drive
    2. Create dashboard record with file sources
    3. Trigger initial data processing
    """
    if not data.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file is required"
        )
    
    # Verify first file exists and get metadata
    drive_service = GoogleDriveService(current_user)
    first_file = data.files[0]
    file_metadata = await drive_service.get_file_metadata(first_file.file_id)
    
    # Create dashboard with first file info (backwards compatible)
    dashboard = Dashboard(
        user_id=current_user.id,
        file_id=first_file.file_id,
        file_name=file_metadata["name"],
        mime_type=file_metadata.get("mimeType"),
        title=data.title or file_metadata["name"],
        global_description=data.global_description,
    )
    
    db.add(dashboard)
    await db.flush()  # Get dashboard.id before creating file sources
    
    # Create file sources for all files
    for file in data.files:
        file_source = FileSource(
            dashboard_id=dashboard.id,
            file_id=file.file_id,
            file_name=file.file_name,
            file_context=file.file_context,
        )
        db.add(file_source)
    
    await db.commit()
    await db.refresh(dashboard)
    
    # Re-query with eager loading to avoid async issues
    result = await db.execute(
        select(Dashboard)
        .where(Dashboard.id == dashboard.id)
        .options(selectinload(Dashboard.file_sources))
    )
    dashboard = result.scalar_one()
    
    logger.info(f"Created dashboard {dashboard.id} with {len(data.files)} file sources")
    
    return dashboard


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific dashboard."""
    result = await db.execute(
        select(Dashboard)
        .where(
            Dashboard.id == dashboard_id,
            Dashboard.user_id == current_user.id
        )
        .options(selectinload(Dashboard.file_sources))
    )
    dashboard = result.scalar_one_or_none()
    
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found"
        )
    
    return dashboard


@router.patch("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: UUID,
    data: DashboardUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update dashboard settings."""
    result = await db.execute(
        select(Dashboard)
        .where(
            Dashboard.id == dashboard_id,
            Dashboard.user_id == current_user.id
        )
        .options(selectinload(Dashboard.file_sources))
    )
    dashboard = result.scalar_one_or_none()
    
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found"
        )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dashboard, field, value)
    
    dashboard.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(dashboard)
    
    return dashboard


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a dashboard."""
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.user_id == current_user.id
        )
    )
    dashboard = result.scalar_one_or_none()
    
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found"
        )
    
    await db.delete(dashboard)
    await db.commit()
    
    logger.info(f"Deleted dashboard {dashboard_id}")


@router.post("/{dashboard_id}/refresh", response_model=RefreshResponse)
async def refresh_dashboard(
    dashboard_id: UUID,
    request: RefreshRequest = RefreshRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh dashboard by fetching latest Excel data from Google Drive.
    
    This endpoint:
    1. Fetches the latest version of all Excel files from Google Drive
    2. Triggers the AI Agent to re-process with file contexts
    3. Detects schema drift and attempts auto-remapping
    4. Returns updated JSON data for the charts
    """
    # Get dashboard with file sources eagerly loaded
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.user_id == current_user.id
        )
    )
    dashboard = result.scalar_one_or_none()
    
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found"
        )
    
    try:
        drive_service = GoogleDriveService(current_user)
        
        # Fetch all file sources for this dashboard
        file_sources_result = await db.execute(
            select(FileSource).where(FileSource.dashboard_id == dashboard.id)
        )
        file_sources = file_sources_result.scalars().all()
        
        # Build files_data with context from file sources
        files_data = []
        if file_sources:
            logger.info(f"Refreshing dashboard {dashboard_id} with {len(file_sources)} file sources")
            for fs in file_sources:
                file_bytes = await drive_service.download_file(fs.file_id)
                files_data.append({
                    "file_id": fs.file_id,
                    "file_name": fs.file_name,
                    "file_bytes": file_bytes,
                    "file_context": fs.file_context
                })
        else:
            # Fallback to single file mode for backwards compatibility
            logger.info(f"Refreshing dashboard {dashboard_id}, file: {dashboard.file_id}")
            file_bytes = await drive_service.download_file(dashboard.file_id)
            files_data.append({
                "file_id": dashboard.file_id,
                "file_name": dashboard.file_name,
                "file_bytes": file_bytes,
                "file_context": None
            })
        
        # Get previous schema for drift detection
        previous_schema = dashboard.column_schema or {}
        
        # Process data with AI Agent using multi-file context
        agent = DataProcessingAgent(gemini_api_key=settings.GEMINI_API_KEY)
        processing_result = await agent.process_multiple_files(
            files_data=files_data,
            global_description=dashboard.global_description,
            previous_schema=previous_schema,
            accept_schema_drift=request.accept_schema_drift
        )
        
        # Update dashboard
        dashboard.sheet_names = processing_result.sheet_names
        dashboard.column_schema = processing_result.new_schema
        dashboard.cached_data = processing_result.chart_data
        dashboard.last_synced = datetime.utcnow()
        dashboard.last_sync_status = "success" if not processing_result.schema_drift_detected else "schema_drift"
        dashboard.last_sync_message = processing_result.message
        dashboard.updated_at = datetime.utcnow()
        
        # Update dashboard config if AI suggested charts
        if processing_result.suggested_charts:
            dashboard.dashboard_config = {
                **(dashboard.dashboard_config or {}),
                "charts": processing_result.suggested_charts
            }
        await db.commit()
        await db.refresh(dashboard)
        
        logger.info(f"Dashboard {dashboard_id} refreshed successfully")
        
        return RefreshResponse(
            success=True,
            message=processing_result.message,
            dashboard_id=dashboard.id,
            last_synced=dashboard.last_synced,
            schema_drift_detected=processing_result.schema_drift_detected,
            schema_drift_info=processing_result.schema_drift_info,
            chart_data=processing_result.chart_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard refresh failed: {e}")
        
        # Update status
        dashboard.last_sync_status = "error"
        dashboard.last_sync_message = str(e)
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh dashboard: {str(e)}"
        )


@router.get("/{dashboard_id}/data")
async def get_dashboard_data(
    dashboard_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get cached chart data for a dashboard.
    
    Returns the processed data without triggering a refresh.
    """
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.user_id == current_user.id
        )
    )
    dashboard = result.scalar_one_or_none()
    
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard not found"
        )
    
    if not dashboard.cached_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No data available. Please refresh the dashboard first."
        )
    
    return {
        "dashboard_id": str(dashboard.id),
        "last_synced": dashboard.last_synced.isoformat() if dashboard.last_synced else None,
        "sheet_names": dashboard.sheet_names,
        "charts": dashboard.dashboard_config.get("charts", []) if dashboard.dashboard_config else [],
        "data": dashboard.cached_data
    }
