"""BlackboxLog endpoints with file upload support."""

from typing import Annotated
import logging
import uuid

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

    # Generate unique object key using UUID to prevent overwrites
    unique_id = uuid.uuid4()
    minio_key = f"blackbox-logs/{drone_id}/{unique_id}.bbl"
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
            "parse_blackbox_log",
            args=[log_entry.id],
            priority=9,  # High priority
        )
        logger.info(f"Triggered parse_blackbox_log task for log {log_entry.id}")
    except Exception as e:
        logger.error(f"Failed to trigger parse task: {e}")
        # Update log status to ERROR and save error message
        log_entry.status = LogStatus.ERROR
        log_entry.error_message = str(e)
        await session.commit()
        await session.refresh(log_entry)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue parsing task",
        )

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


@router.get(
    "/{log_id}/analyses",
    response_model=dict,
    summary="Get all analyses for a log",
)
async def get_log_analyses(
    log_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """
    Retrieve all persisted analysis results for a BlackboxLog.
    
    Returns a dictionary keyed by analysis module name. Each value is a dict containing:
    - `module` (str): analysis module name
    - `result` (Any): parsed analysis payload from `result_json`
    - `created_at` (str): ISO 8601 timestamp when the analysis was created
    
    Raises:
        HTTPException: 404 if the log does not exist or if no analyses are found for the log.
    """
    from app.models import LogAnalysis
    
    # Verify log exists
    log_query = select(BlackboxLog).where(BlackboxLog.id == log_id)
    log_result = await session.execute(log_query)
    log = log_result.scalar_one_or_none()
    
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log with ID {log_id} not found",
        )
    
    # Fetch analyses
    analysis_query = select(LogAnalysis).where(LogAnalysis.log_id == log_id)
    analysis_result = await session.execute(analysis_query)
    analyses = analysis_result.scalars().all()
    
    if not analyses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analyses found for log {log_id}",
        )
    
    # Organize by module
    result = {}
    for analysis in analyses:
        result[analysis.module] = {
            "module": analysis.module,
            "result": analysis.result_json,
            "created_at": analysis.created_at.isoformat(),
        }
    
    return result


@router.get(
    "/{log_id}/analyses/{module}",
    response_model=dict,
    summary="Get analysis for a specific module",
)
async def get_log_analysis(
    log_id: int,
    module: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """
    Retrieve the analysis result for a specific analysis module within a blackbox log.
    
    Parameters:
        module (str): Analysis module name (e.g., "step_response", "fft_noise", "pid_error", "motor_analysis", "tune_score").
    
    Returns:
        dict: Mapping with keys:
            - "module": the analysis module name.
            - "result": the analysis payload as stored in `result_json`.
            - "created_at": ISO 8601 timestamp string of when the analysis was created.
    """
    from app.models import LogAnalysis
    
    # Verify log exists
    log_query = select(BlackboxLog).where(BlackboxLog.id == log_id)
    log_result = await session.execute(log_query)
    log = log_result.scalar_one_or_none()
    
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log with ID {log_id} not found",
        )
    
    # Fetch specific analysis
    analysis_query = select(LogAnalysis).where(
        and_(
            LogAnalysis.log_id == log_id,
            LogAnalysis.module == module,
        )
    )
    analysis_result = await session.execute(analysis_query)
    analysis = analysis_result.scalar_one_or_none()
    
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for module '{module}' in log {log_id}",
        )
    
    return {
        "module": analysis.module,
        "result": analysis.result_json,
        "created_at": analysis.created_at.isoformat(),
    }