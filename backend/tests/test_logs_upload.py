"""
Unit/integration tests for the POST /api/v1/logs/upload endpoint.

All external dependencies (database, MinIO, Celery) are mocked so that
these tests run without any infrastructure.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Drone, BlackboxLog, LogStatus
from app.schemas import BlackboxLogResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_drone():
    """Drone ORM object (not persisted)."""
    return Drone(
        id=7,
        name="Test Drone",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_log():
    """BlackboxLog ORM object returned after session.refresh()."""
    return BlackboxLog(
        id=42,
        drone_id=7,
        file_name="flight_001.bbl",
        file_path="blackbox-logs/7/flight_001.bbl",
        status=LogStatus.PENDING,
        tags=[],
        created_at=datetime.utcnow(),
    )


def _make_mock_session(drone, log_entry):
    """
    Build an AsyncMock session that:
    - Returns *drone* when queried for Drone
    - Returns *log_entry* after commit+refresh (simulates DB insert)
    """
    session = AsyncMock(spec=AsyncSession)

    # first execute → drone lookup; we only need scalar_one_or_none
    drone_result = MagicMock()
    drone_result.scalar_one_or_none.return_value = drone
    session.execute = AsyncMock(return_value=drone_result)

    session.add = MagicMock()
    session.commit = AsyncMock()

    async def mock_refresh(obj):
        # Simulate DB setting the id, created_at, and tags default on the log entry
        obj.id = log_entry.id
        obj.created_at = log_entry.created_at
        if obj.tags is None:
            obj.tags = []

    session.refresh = AsyncMock(side_effect=mock_refresh)
    return session


def _make_test_app(session, mock_minio, mock_celery):
    """
    Build a minimal FastAPI test app with overridden dependencies.
    """
    from app.main import app as real_app
    from app.core import get_db_session

    # Override DB session dependency
    async def override_get_db_session():
        yield session

    real_app.dependency_overrides[get_db_session] = override_get_db_session
    return real_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BBL_CONTENT = b"H Product:Blackbox flight data recorder by Nicholas Sherlock\r\nH Firmware revision: Betaflight 4.5\r\n"


async def _post_upload(app, content=BBL_CONTENT, filename="flight.bbl", drone_id=7):
    """Helper: POST /api/v1/logs/upload with multipart file."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/logs/upload",
            files={"file": (filename, content, "application/octet-stream")},
            params={"drone_id": drone_id},
        )
    return response


# ---------------------------------------------------------------------------
# Successful upload
# ---------------------------------------------------------------------------

class TestUploadLogSuccess:
    @pytest.mark.asyncio
    async def test_returns_201_on_success(self, sample_drone, sample_log):
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock(return_value="blackbox-logs/7/flight.bbl")

        mock_celery = MagicMock()
        mock_celery.send_task = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="flight.bbl")

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_response_contains_log_id(self, sample_drone, sample_log):
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock(return_value="blackbox-logs/7/flight.bbl")

        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="flight.bbl")

        data = response.json()
        assert "id" in data
        assert data["id"] == sample_log.id

    @pytest.mark.asyncio
    async def test_response_status_is_pending(self, sample_drone, sample_log):
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="flight.bbl")

        assert response.json()["status"] == "pending"

    @pytest.mark.asyncio
    async def test_minio_upload_called_with_correct_args(self, sample_drone, sample_log):
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            await _post_upload(app, content=BBL_CONTENT, filename="flight.bbl", drone_id=7)

        mock_minio.upload_file.assert_called_once()
        call_kwargs = mock_minio.upload_file.call_args[1]
        assert call_kwargs["bucket"] == "blackbox-logs"
        assert call_kwargs["object_name"] == "blackbox-logs/7/flight.bbl"
        assert call_kwargs["file_content"] == BBL_CONTENT

    @pytest.mark.asyncio
    async def test_celery_task_triggered_with_log_id(self, sample_drone, sample_log):
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            await _post_upload(app, filename="flight.bbl")

        mock_celery.send_task.assert_called_once()
        call_args = mock_celery.send_task.call_args
        assert call_args[0][0] == "app.workers.tasks.parse_blackbox_log"
        assert call_args[1]["args"] == [sample_log.id]

    @pytest.mark.asyncio
    async def test_celery_task_uses_high_priority(self, sample_drone, sample_log):
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            await _post_upload(app, filename="flight.bbl")

        call_kwargs = mock_celery.send_task.call_args[1]
        assert call_kwargs.get("priority") == 9

    @pytest.mark.asyncio
    async def test_file_path_stored_as_minio_key(self, sample_drone, sample_log):
        """The file_path on the log entry must be the MinIO key, not just the filename."""
        session = _make_mock_session(sample_drone, sample_log)
        captured_log = {}

        original_add = session.add

        def capture_add(obj):
            if isinstance(obj, BlackboxLog):
                captured_log["instance"] = obj
            return original_add(obj)

        session.add = MagicMock(side_effect=capture_add)

        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            await _post_upload(app, filename="flight.bbl", drone_id=7)

        log_instance = captured_log.get("instance")
        assert log_instance is not None
        assert log_instance.file_path == "blackbox-logs/7/flight.bbl"

    @pytest.mark.asyncio
    async def test_celery_failure_does_not_fail_request(self, sample_drone, sample_log):
        """If Celery send_task raises, the endpoint should still return 201."""
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock()

        mock_celery = MagicMock()
        mock_celery.send_task = MagicMock(side_effect=Exception("Celery unavailable"))

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="flight.bbl")

        assert response.status_code == 201


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestUploadLogValidation:
    @pytest.mark.asyncio
    async def test_rejects_non_bbl_extension(self, sample_drone, sample_log):
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="flight.csv")

        assert response.status_code == 400
        assert "BBL" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_rejects_txt_extension(self, sample_drone, sample_log):
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="flight.txt")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_accepts_uppercase_bbl_extension(self, sample_drone, sample_log):
        """Extension check should be case-insensitive (FLIGHT.BBL should be accepted)."""
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="FLIGHT.BBL")

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_returns_404_when_drone_not_found(self, sample_log):
        """If drone does not exist, return 404."""
        # Session that returns None for drone lookup
        session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        mock_minio = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="flight.bbl", drone_id=9999)

        assert response.status_code == 404
        assert "9999" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_error_when_no_filename(self, sample_drone, sample_log):
        """
        If UploadFile has no/empty filename, the request is rejected with a client
        error (4xx).  When httpx sends an empty filename, FastAPI's multipart parser
        raises a 422 before the endpoint code runs; the endpoint's own `if not
        file.filename` guard returns 400.  Either way the request must not succeed.
        """
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            # Send multipart with empty filename — httpx/FastAPI may return 400 or 422
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/logs/upload",
                    files={"file": ("", BBL_CONTENT, "application/octet-stream")},
                    params={"drone_id": 7},
                )

        assert response.status_code in (400, 422), (
            f"Expected a 4xx client error but got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# MinIO upload failure
# ---------------------------------------------------------------------------

class TestUploadLogMinIOFailure:
    @pytest.mark.asyncio
    async def test_returns_500_when_minio_upload_fails(self, sample_drone, sample_log):
        """If MinIO upload raises, respond with 500."""
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock(side_effect=Exception("storage error"))
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="flight.bbl")

        assert response.status_code == 500
        assert "storage" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_db_not_written_when_minio_fails(self, sample_drone, sample_log):
        """If MinIO upload fails, no log entry should be inserted."""
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock(side_effect=Exception("storage error"))
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            await _post_upload(app, filename="flight.bbl")

        session.add.assert_not_called()
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Boundary / regression cases
# ---------------------------------------------------------------------------

class TestUploadLogBoundary:
    @pytest.mark.asyncio
    async def test_drone_id_zero_returns_422(self, sample_drone, sample_log):
        """drone_id=0 violates gt=0 constraint → 422 Unprocessable Entity."""
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, filename="flight.bbl", drone_id=0)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_file_is_accepted_and_uploaded(self, sample_drone, sample_log):
        """An empty .bbl file should pass validation and be uploaded to MinIO."""
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            response = await _post_upload(app, content=b"", filename="empty.bbl")

        assert response.status_code == 201
        call_kwargs = mock_minio.upload_file.call_args[1]
        assert call_kwargs["file_content"] == b""

    @pytest.mark.asyncio
    async def test_minio_key_includes_drone_id_and_filename(self, sample_drone, sample_log):
        """The MinIO object key must follow the pattern blackbox-logs/{drone_id}/{filename}."""
        session = _make_mock_session(sample_drone, sample_log)
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.upload_file = MagicMock()
        mock_celery = MagicMock()

        with patch("app.api.v1.logs.minio_client", mock_minio), \
             patch("app.api.v1.logs.celery_app", mock_celery):
            app = _make_test_app(session, mock_minio, mock_celery)
            await _post_upload(app, filename="my_log.bbl", drone_id=7)

        call_kwargs = mock_minio.upload_file.call_args[1]
        assert call_kwargs["object_name"] == "blackbox-logs/7/my_log.bbl"