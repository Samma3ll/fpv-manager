"""Drone CRUD endpoints."""

from typing import Annotated
import logging
import mimetypes
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from minio.error import S3Error
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db_session
from app.core.minio import minio_client
from app.models import Drone
from app.schemas import DroneCreate, DroneUpdate, DroneResponse, DroneListResponse

router = APIRouter(prefix="/drones", tags=["drones"])
logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "",
    response_model=DroneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new drone",
)
async def create_drone(
    drone_in: DroneCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DroneResponse:
    """Create a new drone with the provided information."""
    drone = Drone(**drone_in.model_dump())
    session.add(drone)
    await session.commit()
    await session.refresh(drone)
    return DroneResponse.model_validate(drone)


@router.get(
    "",
    response_model=DroneListResponse,
    summary="List all drones",
)
async def list_drones(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0, description="Number of items to skip")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of items to return")] = 10,
) -> DroneListResponse:
    """List all drones with pagination."""
    # Get total count
    count_query = select(func.count()).select_from(Drone)
    total = (await session.execute(count_query)).scalar()

    # Get paginated results
    query = select(Drone).offset(skip).limit(limit)
    result = await session.execute(query)
    drones = result.scalars().all()

    return DroneListResponse(
        items=[DroneResponse.model_validate(drone) for drone in drones],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/{drone_id}/picture",
    response_model=DroneResponse,
    summary="Upload or replace a drone picture",
)
async def upload_drone_picture(
    drone_id: int,
    file: Annotated[UploadFile, File(description="Drone image file")],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DroneResponse:
    """Upload a picture for a drone and store it in object storage."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file name provided",
        )

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image type. Allowed: jpg, jpeg, png, gif, webp",
        )

    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content type. Expected an image",
        )

    query = select(Drone).where(Drone.id == drone_id)
    result = await session.execute(query)
    drone = result.scalar_one_or_none()
    if drone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone with ID {drone_id} not found",
        )

    # Stream-read the file in chunks to enforce max upload size
    content_chunks = []
    total_bytes = 0
    CHUNK_SIZE = 64 * 1024  # 64 KB chunks

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded image exceeds maximum size of {MAX_UPLOAD_BYTES} bytes",
            )
        content_chunks.append(chunk)

    content = b"".join(content_chunks)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty",
        )

    new_object_key = f"drone-pictures/{drone_id}/{uuid.uuid4()}{extension}"
    try:
        minio_client.upload_file(
            bucket=minio_client.bucket_assets,
            object_name=new_object_key,
            file_content=content,
        )
    except S3Error as err:
        logger.exception("Failed to upload drone picture to object storage")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload drone picture",
        ) from err

    old_picture = drone.picture_path
    drone.picture_path = new_object_key
    try:
        await session.commit()
        await session.refresh(drone)
    except Exception:
        # Best-effort cleanup: delete the just-uploaded object
        try:
            minio_client.delete_file(
                bucket=minio_client.bucket_assets,
                object_name=new_object_key,
            )
        except Exception:
            logger.warning("Failed to cleanup uploaded object after commit failure: %s", new_object_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update drone record",
        )

    if old_picture:
        try:
            minio_client.delete_file(
                bucket=minio_client.bucket_assets,
                object_name=old_picture,
            )
        except S3Error:
            logger.warning("Failed to delete old drone picture '%s'", old_picture)

    return DroneResponse.model_validate(drone)


@router.get(
    "/{drone_id}/picture",
    response_class=Response,
    summary="Get drone picture",
)
async def get_drone_picture(
    drone_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Retrieve a drone picture from object storage."""
    query = select(Drone).where(Drone.id == drone_id)
    result = await session.execute(query)
    drone = result.scalar_one_or_none()
    if drone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone with ID {drone_id} not found",
        )

    if not drone.picture_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone with ID {drone_id} has no picture",
        )

    try:
        content = minio_client.download_file(
            bucket=minio_client.bucket_assets,
            object_name=drone.picture_path,
        )
    except S3Error as err:
        logger.exception("Failed to download drone picture from object storage")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve drone picture",
        ) from err

    media_type = mimetypes.guess_type(drone.picture_path)[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type)


@router.get(
    "/{drone_id}",
    response_model=DroneResponse,
    summary="Get a drone by ID",
)
async def get_drone(
    drone_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DroneResponse:
    """Get a specific drone by its ID."""
    query = select(Drone).where(Drone.id == drone_id)
    result = await session.execute(query)
    drone = result.scalar_one_or_none()

    if drone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone with ID {drone_id} not found",
        )

    return DroneResponse.model_validate(drone)


@router.patch(
    "/{drone_id}",
    response_model=DroneResponse,
    summary="Update a drone",
)
async def update_drone(
    drone_id: int,
    drone_update: DroneUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DroneResponse:
    """Update a drone with partial data."""
    query = select(Drone).where(Drone.id == drone_id)
    result = await session.execute(query)
    drone = result.scalar_one_or_none()

    if drone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone with ID {drone_id} not found",
        )

    # Update only provided fields
    update_data = drone_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(drone, field, value)

    await session.commit()
    await session.refresh(drone)
    return DroneResponse.model_validate(drone)


@router.delete(
    "/{drone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a drone",
)
async def delete_drone(
    drone_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete a drone by its ID."""
    query = select(Drone).where(Drone.id == drone_id)
    result = await session.execute(query)
    drone = result.scalar_one_or_none()

    if drone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone with ID {drone_id} not found",
        )

    await session.delete(drone)
    await session.commit()