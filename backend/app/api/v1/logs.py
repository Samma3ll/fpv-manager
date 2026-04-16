"""BlackboxLog endpoints with file upload support."""

from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db_session
from app.core.minio import minio_client
from app.models import BlackboxLog, LogStatus, Drone
from app.schemas import (
    BlackboxLogCreate,
    BlackboxLogUpdate,
    BlackboxLogResponse,
    BlackboxLogListResponse,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["blackbox_logs"])


@router.post(
    "/upload",
    response_model=BlackboxLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a blackbox log file",
)
async def upload_log(
    file: Annotated[UploadFile, File(description="Betaflight blackbox log file")],
    drone_id: Annotated[int, Query(gt=0, description="Drone ID")],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BlackboxLogResponse:
    """
    Store an uploaded Betaflight blackbox log, create a corresponding DB record with pending status, and enqueue asynchronous parsing.
    
    Parameters:
        file (UploadFile): Uploaded `.bbl` file. Must include a non-empty filename and have a `.bbl` extension.
        drone_id (int): Target drone ID (must be greater than 0).
        session (AsyncSession): Database session dependency.
    
    Returns:
        BlackboxLogResponse: The created log entry with metadata and initial `PENDING` status.
    
    Raises:
        HTTPException: 400 if the upload has no filename or the file is not a `.bbl`; 404 if the specified drone does not exist; 500 if storing the file in object storage fails.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file name provided",
        )

    # Validate file extension
    filename_lower = file.filename.strip().lower()
    if not filename_lower.endswith('.bbl'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type: expected .BBL",
        )

    # Verify drone exists
    query = select(Drone).where(Drone.id == drone_id)
    result = await session.execute(query)
    drone = result.scalar_one_or_none()

    if drone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone with ID {drone_id} not found",
        )

    # Read file content
    content = await file.read()

    # Upload to MinIO
    minio_key = f"blackbox-logs/{drone_id}/{file.filename}"
    try:
        minio_client.upload_file(
            bucket=minio_client.bucket_blackbox,
            object_name=minio_key,
            file_content=content,
        )
        logger.info(f"Uploaded file to MinIO: {minio_key}")
    except Exception as e:
        logger.error(f"Failed to upload file to MinIO: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage",
        )

    # Create log entry with pending status
    log_entry = BlackboxLog(
        drone_id=drone_id,
        file_name=file.filename,
        file_path=minio_key,
        status=LogStatus.PENDING,
    )

    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)

    # Trigger Celery task to parse log
    try:
        celery_app.send_task(
            "app.workers.tasks.parse_blackbox_log",
            args=[log_entry.id],
            priority=9,  # High priority
        )
        logger.info(f"Triggered parse_blackbox_log task for log {log_entry.id}")
    except Exception as e:
        logger.error(f"Failed to trigger parse task: {e}")
        # Don't fail the request, the task will be retried later

    return BlackboxLogResponse.model_validate(log_entry)


@router.get(
    "",
    response_model=BlackboxLogListResponse,
    summary="List blackbox logs",
)
async def list_logs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    drone_id: Annotated[int | None, Query(gt=0, description="Filter by drone ID")] = None,
    status_filter: Annotated[
        LogStatus | None, Query(description="Filter by processing status")
    ] = None,
    skip: Annotated[int, Query(ge=0, description="Number of items to skip")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of items to return")] = 10,
) -> BlackboxLogListResponse:
    """
    List blackbox logs with optional filtering and pagination.
    
    - **drone_id**: Filter logs for a specific drone
    - **status**: Filter by processing status (pending, processing, ready, error)
    """
    # Build filter conditions
    conditions = []
    if drone_id is not None:
        conditions.append(BlackboxLog.drone_id == drone_id)
    if status_filter is not None:
        conditions.append(BlackboxLog.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(BlackboxLog)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = (await session.execute(count_query)).scalar()

    # Get paginated results
    query = select(BlackboxLog)
    if conditions:
        query = query.where(and_(*conditions))
    query = query.order_by(BlackboxLog.created_at.desc()).offset(skip).limit(limit)

    result = await session.execute(query)
    logs = result.scalars().all()

    return BlackboxLogListResponse(
        items=[BlackboxLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{log_id}",
    response_model=BlackboxLogResponse,
    summary="Get a log by ID",
)
async def get_log(
    log_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BlackboxLogResponse:
    """Get a specific blackbox log by its ID."""
    query = select(BlackboxLog).where(BlackboxLog.id == log_id)
    result = await session.execute(query)
    log = result.scalar_one_or_none()

    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log with ID {log_id} not found",
        )

    return BlackboxLogResponse.model_validate(log)


@router.patch(
    "/{log_id}",
    response_model=BlackboxLogResponse,
    summary="Update a log",
)
async def update_log(
    log_id: int,
    log_update: BlackboxLogUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BlackboxLogResponse:
    """Update a blackbox log with partial data."""
    query = select(BlackboxLog).where(BlackboxLog.id == log_id)
    result = await session.execute(query)
    log = result.scalar_one_or_none()

    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log with ID {log_id} not found",
        )

    # Update only provided fields
    update_data = log_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(log, field, value)

    await session.commit()
    await session.refresh(log)
    return BlackboxLogResponse.model_validate(log)


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a log",
)
async def delete_log(
    log_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete a blackbox log by its ID."""
    query = select(BlackboxLog).where(BlackboxLog.id == log_id)
    result = await session.execute(query)
    log = result.scalar_one_or_none()

    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log with ID {log_id} not found",
        )

    # TODO: Delete file from MinIO
    await session.delete(log)
    await session.commit()