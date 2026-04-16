"""Drone CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db_session
from app.models import Drone
from app.schemas import DroneCreate, DroneUpdate, DroneResponse, DroneListResponse

router = APIRouter(prefix="/drones", tags=["drones"])


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
