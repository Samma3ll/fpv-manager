from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.drones import (
    create_drone,
    delete_drone,
    get_drone,
    list_drones,
    update_drone,
)
from app.models import Drone
from app.schemas import DroneCreate, DroneUpdate


def _result_with_scalar(value):
    """
    Create a MagicMock whose `scalar_one_or_none()` call returns the provided value.
    
    Parameters:
        value: The object to be returned when `scalar_one_or_none()` is invoked on the mock.
    
    Returns:
        MagicMock: A mock with `scalar_one_or_none().return_value` set to `value`.
    """
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _result_with_scalars(values):
    """
    Create a MagicMock configured so its scalars().all() call returns the given values.
    
    Parameters:
        values (Sequence): Sequence of values to be returned by result.scalars().all()
    
    Returns:
        MagicMock: Mock object where calling `scalars().all()` yields `values`.
    """
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _sample_drone(drone_id=1, name="Demo Drone"):
    """
    Create a Drone instance for tests with current UTC creation and update timestamps.
    
    Parameters:
        drone_id (int): ID to assign to the returned Drone.
        name (str): Name to assign to the returned Drone.
    
    Returns:
        Drone: Instance with `id` and `name` set as provided and `created_at`/`updated_at` set to the current UTC time.
    """
    now = datetime.now(timezone.utc)
    return Drone(
        id=drone_id,
        name=name,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_drone_creates_and_returns_response():
    session = AsyncMock()
    session.add = MagicMock()

    async def refresh_side_effect(drone):
        """
        Mutates the given drone instance by assigning an id and current UTC created/updated timestamps.
        
        Parameters:
            drone: The drone model instance to update in place; should accept attributes `id`, `created_at`, and `updated_at`.
        """
        drone.id = 12
        drone.created_at = datetime.now(timezone.utc)
        drone.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=refresh_side_effect)
    payload = DroneCreate(name="New Drone", motor_kv=2300)

    result = await create_drone(payload, session)

    assert result.id == 12
    assert result.name == "New Drone"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_drones_returns_paginated_response():
    session = AsyncMock()
    drones = [_sample_drone(1, "A"), _sample_drone(2, "B")]
    session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar=MagicMock(return_value=2)),
            _result_with_scalars(drones),
        ]
    )

    result = await list_drones(session, skip=0, limit=10)

    assert result.total == 2
    assert len(result.items) == 2
    assert result.items[0].name == "A"


@pytest.mark.asyncio
async def test_get_drone_returns_404_when_missing():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_scalar(None))

    with pytest.raises(HTTPException) as exc:
        await get_drone(99, session)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_drone_applies_partial_fields():
    drone = _sample_drone(7, "Before")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_scalar(drone))
    update = DroneUpdate(name="After", motor_kv=2500)

    result = await update_drone(7, update, session)

    assert result.name == "After"
    assert drone.motor_kv == 2500
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(drone)


@pytest.mark.asyncio
async def test_delete_drone_deletes_when_found():
    drone = _sample_drone(3, "Delete Me")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_scalar(drone))

    await delete_drone(3, session)

    session.delete.assert_awaited_once_with(drone)
    session.commit.assert_awaited_once()
