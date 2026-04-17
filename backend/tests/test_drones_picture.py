"""
Unit tests for the drone picture endpoints:
  POST /{drone_id}/picture  (upload_drone_picture)
  GET  /{drone_id}/picture  (get_drone_picture)

All external dependencies (database, MinIO) are mocked so these tests run
without any infrastructure.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Drone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_IMAGE_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG-like content


def _make_s3_error(code: str = "InternalError") -> S3Error:
    """Construct a minimal S3Error instance for use in side_effect."""
    return S3Error(
        code=code,
        message="simulated storage error",
        resource=None,
        request_id=None,
        host_id=None,
        response=MagicMock(),
    )


def _make_mock_session(drone: Drone | None) -> AsyncMock:
    """
    Build an AsyncMock session that returns *drone* (or None) when
    scalar_one_or_none() is called after execute().
    """
    session = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = drone
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()

    async def mock_refresh(obj):
        pass  # no-op: drone attributes are already set on the mock object

    session.refresh = AsyncMock(side_effect=mock_refresh)
    return session


def _make_test_app(session: AsyncMock) -> FastAPI:
    """Return the real FastAPI app with the DB session dependency overridden."""
    from app.main import app as real_app
    from app.core import get_db_session

    async def override_get_db_session():
        yield session

    real_app.dependency_overrides[get_db_session] = override_get_db_session
    return real_app


def _make_drone(*, picture_path: str | None = None) -> Drone:
    """Return an in-memory Drone ORM object (not persisted)."""
    return Drone(
        id=5,
        name="Test Quad",
        description="Unit test drone",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        picture_path=picture_path,
    )


def _make_mock_minio(*, bucket_assets: str = "assets") -> MagicMock:
    """Return a pre-configured mock minio_client."""
    mock = MagicMock()
    mock.bucket_assets = bucket_assets
    mock.upload_file = MagicMock(return_value=None)
    mock.download_file = MagicMock(return_value=SAMPLE_IMAGE_BYTES)
    mock.delete_file = MagicMock(return_value=None)
    return mock


async def _post_picture(
    app: FastAPI,
    drone_id: int = 5,
    content: bytes = SAMPLE_IMAGE_BYTES,
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
) -> object:
    """POST /api/v1/drones/{drone_id}/picture with a multipart file."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/drones/{drone_id}/picture",
            files={"file": (filename, content, content_type)},
        )
    return response


async def _get_picture(app: FastAPI, drone_id: int = 5) -> object:
    """GET /api/v1/drones/{drone_id}/picture."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/drones/{drone_id}/picture")
    return response


# ---------------------------------------------------------------------------
# POST /{drone_id}/picture — successful upload
# ---------------------------------------------------------------------------

class TestUploadDronePictureSuccess:
    @pytest.mark.asyncio
    async def test_returns_200_on_success(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_drone_id(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, drone_id=5)

        assert response.json()["id"] == 5

    @pytest.mark.asyncio
    async def test_minio_upload_called_once(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app)

        mock_minio.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_minio_upload_uses_assets_bucket(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio(bucket_assets="drone-assets")

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app)

        call_kwargs = mock_minio.upload_file.call_args[1]
        assert call_kwargs["bucket"] == "drone-assets"

    @pytest.mark.asyncio
    async def test_minio_object_key_contains_drone_id_and_extension(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app, drone_id=5, filename="shot.png")

        call_kwargs = mock_minio.upload_file.call_args[1]
        key: str = call_kwargs["object_name"]
        assert key.startswith("drone-pictures/5/")
        assert key.endswith(".png")

    @pytest.mark.asyncio
    async def test_minio_upload_receives_file_bytes(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        image_data = b"fake PNG data IDAT"

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app, content=image_data, filename="img.png")

        call_kwargs = mock_minio.upload_file.call_args[1]
        assert call_kwargs["file_content"] == image_data

    @pytest.mark.asyncio
    async def test_db_committed_after_upload(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app)

        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_old_picture_is_deleted_when_present(self):
        old_key = "drone-pictures/5/old-uuid.jpg"
        drone = _make_drone(picture_path=old_key)
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app)

        mock_minio.delete_file.assert_called_once()
        delete_kwargs = mock_minio.delete_file.call_args[1]
        assert delete_kwargs["object_name"] == old_key

    @pytest.mark.asyncio
    async def test_no_delete_when_no_previous_picture(self):
        drone = _make_drone(picture_path=None)
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app)

        mock_minio.delete_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_old_picture_delete_failure_does_not_fail_request(self):
        """S3Error when deleting the old picture must not propagate – just log warning."""
        old_key = "drone-pictures/5/stale-uuid.webp"
        drone = _make_drone(picture_path=old_key)
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.delete_file = MagicMock(side_effect=_make_s3_error())

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_accepts_jpeg_extension(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, filename="drone.jpeg")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_accepts_png_extension(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, filename="drone.png", content_type="image/png")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_accepts_gif_extension(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, filename="drone.gif", content_type="image/gif")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_accepts_webp_extension(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, filename="drone.webp", content_type="image/webp")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_accepts_uppercase_extension(self):
        """Extension check must be case-insensitive (PHOTO.JPG should pass)."""
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, filename="PHOTO.JPG")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /{drone_id}/picture — validation errors
# ---------------------------------------------------------------------------

class TestUploadDronePictureValidation:
    @pytest.mark.asyncio
    async def test_rejects_empty_filename(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/drones/5/picture",
                    files={"file": ("", SAMPLE_IMAGE_BYTES, "image/jpeg")},
                )

        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_rejects_unsupported_extension_txt(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, filename="file.txt", content_type="image/jpeg")

        assert response.status_code == 400
        assert "Invalid image type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_rejects_unsupported_extension_pdf(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(
                app, filename="document.pdf", content_type="application/pdf"
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_non_image_content_type(self):
        """Valid extension but non-image content type must be rejected."""
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(
                app, filename="photo.jpg", content_type="application/octet-stream"
            )

        assert response.status_code == 400
        assert "content type" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_allows_no_content_type_header(self):
        """
        When the client sends no content_type (None), the check is skipped
        and the file is accepted if the extension is valid.
        """
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            # httpx sends None content_type when not specified explicitly
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/drones/5/picture",
                    files={"file": ("photo.jpg", SAMPLE_IMAGE_BYTES)},
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rejects_empty_file_content(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, content=b"", filename="empty.jpg")

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_404_when_drone_not_found(self):
        session = _make_mock_session(drone=None)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, drone_id=9999)

        assert response.status_code == 404
        assert "9999" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_minio_not_called_when_drone_missing(self):
        """MinIO upload must not be attempted if the drone does not exist."""
        session = _make_mock_session(drone=None)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app, drone_id=9999)

        mock_minio.upload_file.assert_not_called()


# ---------------------------------------------------------------------------
# POST /{drone_id}/picture — MinIO upload failure
# ---------------------------------------------------------------------------

class TestUploadDronePictureStorageFailure:
    @pytest.mark.asyncio
    async def test_returns_500_when_minio_upload_raises_s3error(self):
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.upload_file = MagicMock(side_effect=_make_s3_error())

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app)

        assert response.status_code == 500
        assert "Failed to upload drone picture" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_db_not_committed_when_upload_fails(self):
        """picture_path must not be persisted if MinIO upload fails."""
        drone = _make_drone()
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.upload_file = MagicMock(side_effect=_make_s3_error())

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app)

        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_old_picture_not_deleted_when_upload_fails(self):
        """If upload fails, the old picture must not be removed."""
        old_key = "drone-pictures/5/old-uuid.jpg"
        drone = _make_drone(picture_path=old_key)
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.upload_file = MagicMock(side_effect=_make_s3_error())

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app)

        mock_minio.delete_file.assert_not_called()


# ---------------------------------------------------------------------------
# GET /{drone_id}/picture — success
# ---------------------------------------------------------------------------

class TestGetDronePictureSuccess:
    @pytest.mark.asyncio
    async def test_returns_200_with_image_bytes(self):
        drone = _make_drone(picture_path="drone-pictures/5/abc.jpg")
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.download_file = MagicMock(return_value=SAMPLE_IMAGE_BYTES)

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _get_picture(app)

        assert response.status_code == 200
        assert response.content == SAMPLE_IMAGE_BYTES

    @pytest.mark.asyncio
    async def test_content_type_jpeg_for_jpg_path(self):
        drone = _make_drone(picture_path="drone-pictures/5/abc.jpg")
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.download_file = MagicMock(return_value=SAMPLE_IMAGE_BYTES)

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _get_picture(app)

        assert "image/jpeg" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_content_type_png_for_png_path(self):
        drone = _make_drone(picture_path="drone-pictures/5/photo.png")
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.download_file = MagicMock(return_value=b"\x89PNG\r\n")

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _get_picture(app)

        assert "image/png" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_content_type_octet_stream_for_unknown_extension(self):
        drone = _make_drone(picture_path="drone-pictures/5/img.unknownext")
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.download_file = MagicMock(return_value=b"data")

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _get_picture(app)

        # Unknown extension → falls back to application/octet-stream
        assert response.status_code == 200
        assert "octet-stream" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_minio_download_called_with_correct_key(self):
        path = "drone-pictures/5/some-uuid.jpg"
        drone = _make_drone(picture_path=path)
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.download_file = MagicMock(return_value=SAMPLE_IMAGE_BYTES)

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _get_picture(app)

        call_kwargs = mock_minio.download_file.call_args[1]
        assert call_kwargs["object_name"] == path
        assert call_kwargs["bucket"] == mock_minio.bucket_assets


# ---------------------------------------------------------------------------
# GET /{drone_id}/picture — error cases
# ---------------------------------------------------------------------------

class TestGetDronePictureErrors:
    @pytest.mark.asyncio
    async def test_returns_404_when_drone_not_found(self):
        session = _make_mock_session(drone=None)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _get_picture(app, drone_id=1234)

        assert response.status_code == 404
        assert "1234" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_404_when_drone_has_no_picture(self):
        drone = _make_drone(picture_path=None)
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _get_picture(app, drone_id=5)

        assert response.status_code == 404
        assert "no picture" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_404_when_picture_path_is_empty_string(self):
        """picture_path='' (falsy) should behave the same as None."""
        drone = _make_drone(picture_path="")
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _get_picture(app, drone_id=5)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_500_when_minio_download_raises_s3error(self):
        drone = _make_drone(picture_path="drone-pictures/5/abc.jpg")
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()
        mock_minio.download_file = MagicMock(side_effect=_make_s3_error())

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _get_picture(app, drone_id=5)

        assert response.status_code == 500
        assert "Failed to retrieve drone picture" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_minio_not_called_when_no_picture_path(self):
        """download_file must not be called when there is no picture stored."""
        drone = _make_drone(picture_path=None)
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _get_picture(app, drone_id=5)

        mock_minio.download_file.assert_not_called()


# ---------------------------------------------------------------------------
# Regression / boundary
# ---------------------------------------------------------------------------

class TestDronePictureBoundary:
    @pytest.mark.asyncio
    async def test_upload_replaces_picture_path_on_drone(self):
        """After a successful upload the new object key is written to picture_path."""
        captured = {}
        drone = _make_drone(picture_path=None)
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        original_upload = mock_minio.upload_file

        def capturing_upload(**kwargs):
            captured["object_name"] = kwargs["object_name"]
            return original_upload(**kwargs)

        mock_minio.upload_file = MagicMock(side_effect=capturing_upload)

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            await _post_picture(app, drone_id=5, filename="new.jpg")

        # The drone's picture_path attribute must have been updated before commit
        assert drone.picture_path == captured.get("object_name")

    @pytest.mark.asyncio
    async def test_upload_object_key_is_unique_on_each_call(self):
        """Two consecutive uploads must produce distinct object keys (UUID-based)."""
        drone1 = _make_drone()
        drone2 = _make_drone()
        mock_minio = _make_mock_minio()

        keys = []

        def capture_upload(**kwargs):
            keys.append(kwargs["object_name"])

        mock_minio.upload_file = MagicMock(side_effect=capture_upload)

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app1 = _make_test_app(_make_mock_session(drone1))
            await _post_picture(app1, filename="pic.jpg")

            app2 = _make_test_app(_make_mock_session(drone2))
            await _post_picture(app2, filename="pic.jpg")

        assert len(keys) == 2
        assert keys[0] != keys[1], "Object keys should differ between uploads"

    @pytest.mark.asyncio
    async def test_upload_picture_url_in_response_reflects_new_picture(self):
        """picture_url in the response body must point to the correct API endpoint."""
        drone = _make_drone(picture_path=None)
        session = _make_mock_session(drone)
        mock_minio = _make_mock_minio()

        # Simulate session.refresh updating picture_path on the drone object
        async def mock_refresh_with_path(obj):
            obj.picture_path = "drone-pictures/5/new-uuid.jpg"

        session.refresh = AsyncMock(side_effect=mock_refresh_with_path)

        with patch("app.api.v1.drones.minio_client", mock_minio):
            app = _make_test_app(session)
            response = await _post_picture(app, drone_id=5)

        data = response.json()
        assert data.get("picture_url") == "/api/v1/drones/5/picture"