from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from app.api.v1.logs import (
    delete_log,
    get_log,
    get_log_analyses,
    get_log_analysis,
    list_logs,
    update_log,
    upload_log,
)
from app.models import BlackboxLog, Drone, LogAnalysis, LogStatus
from app.schemas import BlackboxLogUpdate


def _scalar_result(value):
    """
    Create a MagicMock that simulates a SQLAlchemy result object for queries returning a single scalar.
    
    Parameters:
        value: The value that the mocked `scalar_one_or_none()` call will return.
    
    Returns:
        MagicMock: A mock object whose `scalar_one_or_none()` method returns `value`.
    """
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars_result(values):
    """
    Create a MagicMock that simulates a SQLAlchemy result whose `scalars().all()` returns the given values.
    
    Parameters:
        values (Sequence): The sequence to be returned by `scalars().all()`.
    
    Returns:
        MagicMock: A mock result configured so `result.scalars().all()` yields `values`.
    """
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _sample_drone(drone_id=1):
    """
    Create a deterministic sample Drone instance for use in tests.
    
    Parameters:
        drone_id (int): ID to assign to the created Drone (defaults to 1).
    
    Returns:
        Drone: Drone with the given `id`, `name` set to "Drone {id}", and `created_at`/`updated_at` set to the current UTC time.
    """
    now = datetime.now(timezone.utc)
    return Drone(id=drone_id, name=f"Drone {drone_id}", created_at=now, updated_at=now)


def _sample_log(log_id=1, drone_id=1, status=LogStatus.PENDING):
    """
    Create a sample BlackboxLog instance for tests with deterministic identifiers and file metadata.
    
    Parameters:
        log_id (int): ID to assign to the created log.
        drone_id (int): Drone ID to assign and embed in the file_path.
        status (LogStatus): Status to set on the log.
    
    Returns:
        BlackboxLog: A BlackboxLog populated with `id`, `drone_id`, `file_name` "flight.bbl",
        `file_path` "blackbox-logs/{drone_id}/flight.bbl", empty `tags`, and `created_at` set to now (UTC).
    """
    return BlackboxLog(
        id=log_id,
        drone_id=drone_id,
        file_name="flight.bbl",
        file_path=f"blackbox-logs/{drone_id}/flight.bbl",
        status=status,
        tags=[],
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_upload_log_success_creates_entry_and_enqueues_task():
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(_sample_drone(5)))
    file = UploadFile(filename="test.bbl", file=BytesIO(b"bbl-data"))

    async def refresh_side_effect(log_entry):
        """
        Populate a log entry with deterministic fields to simulate a database refresh.
        
        Sets the entry's `id` to 77, updates `created_at` to the current UTC datetime, and ensures `tags` is an empty list if it was None.
        
        Parameters:
            log_entry: The log object to modify in-place.
        """
        log_entry.id = 77
        log_entry.created_at = datetime.now(timezone.utc)
        if log_entry.tags is None:
            log_entry.tags = []

    session.refresh = AsyncMock(side_effect=refresh_side_effect)

    mock_minio = MagicMock()
    mock_minio.bucket_blackbox = "blackbox-logs"
    mock_celery = MagicMock()

    with patch("app.api.v1.logs.minio_client", mock_minio), patch(
        "app.api.v1.logs.celery_app", mock_celery
    ), patch("app.api.v1.logs.uuid.uuid4", return_value="fixed-uuid"):
        response = await upload_log(file=file, drone_id=5, session=session)

    assert response.id == 77
    assert response.file_path == "blackbox-logs/5/fixed-uuid.bbl"
    mock_minio.upload_file.assert_called_once()
    mock_celery.send_task.assert_called_once_with(
        "parse_blackbox_log", args=[77], priority=9
    )


@pytest.mark.asyncio
async def test_upload_log_rejects_non_bbl_extensions():
    session = AsyncMock()
    file = UploadFile(filename="test.csv", file=BytesIO(b"abc"))

    with pytest.raises(HTTPException) as exc:
        await upload_log(file=file, drone_id=1, session=session)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_log_returns_404_when_drone_missing():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(None))
    file = UploadFile(filename="test.bbl", file=BytesIO(b"abc"))

    with pytest.raises(HTTPException) as exc:
        await upload_log(file=file, drone_id=404, session=session)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_upload_log_returns_500_when_minio_upload_fails():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(_sample_drone(1)))
    file = UploadFile(filename="test.bbl", file=BytesIO(b"abc"))
    mock_minio = MagicMock()
    mock_minio.bucket_blackbox = "blackbox-logs"
    mock_minio.upload_file.side_effect = Exception("boom")

    with patch("app.api.v1.logs.minio_client", mock_minio), pytest.raises(
        HTTPException
    ) as exc:
        await upload_log(file=file, drone_id=1, session=session)

    assert exc.value.status_code == 500
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_list_logs_returns_paginated_items():
    session = AsyncMock()
    logs = [_sample_log(1), _sample_log(2)]
    session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar=MagicMock(return_value=2)),
            _scalars_result(logs),
        ]
    )

    response = await list_logs(session=session, skip=0, limit=10)

    assert response.total == 2
    assert len(response.items) == 2


@pytest.mark.asyncio
async def test_get_log_returns_404_when_missing():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(None))

    with pytest.raises(HTTPException) as exc:
        await get_log(999, session)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_log_updates_fields():
    log_entry = _sample_log(10)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(log_entry))
    payload = BlackboxLogUpdate(notes="updated note", status=LogStatus.READY)

    result = await update_log(10, payload, session)

    assert result.notes == "updated note"
    assert result.status == LogStatus.READY
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_log_deletes_entry():
    log_entry = _sample_log(11)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_scalar_result(log_entry))

    await delete_log(11, session)

    session.delete.assert_awaited_once_with(log_entry)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_log_analyses_returns_module_keyed_mapping():
    log_entry = _sample_log(1)
    analysis = LogAnalysis(
        id=5,
        log_id=1,
        module="pid_error",
        result_json={"rms_error": 0.22},
        created_at=datetime.now(timezone.utc),
    )
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_scalar_result(log_entry), _scalars_result([analysis])]
    )

    result = await get_log_analyses(1, session)

    assert "pid_error" in result
    assert result["pid_error"]["result"]["rms_error"] == 0.22


@pytest.mark.asyncio
async def test_get_log_analysis_returns_404_when_module_missing():
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_scalar_result(_sample_log(3)), _scalar_result(None)]
    )

    with pytest.raises(HTTPException) as exc:
        await get_log_analysis(3, "fft_noise", session)

    assert exc.value.status_code == 404
