"""Shared test fixtures for the FPV Manager backend test suite."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models import BlackboxLog, LogStatus, Drone


@pytest.fixture
def mock_minio_raw():
    """Return a mock for the underlying Minio() client object."""
    mock = MagicMock()
    mock.put_object.return_value = None
    mock.get_object.return_value = MagicMock(
        read=MagicMock(return_value=b"file content"),
        close=MagicMock(),
    )
    mock.remove_object.return_value = None
    mock.stat_object.return_value = MagicMock()
    return mock


@pytest.fixture
def sample_drone():
    """Return a sample Drone ORM object (unsaved)."""
    drone = Drone(
        id=1,
        name="Test Drone",
        description="A test drone",
        frame_size="5-inch",
        motor_kv=2400,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    return drone


@pytest.fixture
def sample_log_entry():
    """Return a sample BlackboxLog ORM object (unsaved, pending status)."""
    log = BlackboxLog(
        id=42,
        drone_id=1,
        file_name="flight_001.bbl",
        file_path="blackbox-logs/1/flight_001.bbl",
        status=LogStatus.PENDING,
        tags=[],
        created_at=datetime.utcnow(),
    )
    return log


@pytest.fixture
def sample_log_entry_ready():
    """Return a sample BlackboxLog ORM object with READY status and parsed data."""
    log = BlackboxLog(
        id=43,
        drone_id=1,
        file_name="flight_002.bbl",
        file_path="blackbox-logs/1/flight_002.bbl",
        status=LogStatus.READY,
        betaflight_version="Betaflight 2025.12.1 (85d201376) STM32F405",
        craft_name="MyQuad",
        pid_roll=45.0,
        pid_pitch=47.0,
        pid_yaw=40.0,
        duration_s=120.5,
        tags=[],
        created_at=datetime.utcnow(),
    )
    return log