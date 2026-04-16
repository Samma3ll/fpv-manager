"""Unit tests for backend/app/core/minio.py (MinIOClient)."""

import pytest
from io import BytesIO
from unittest.mock import MagicMock, patch, call
from minio.error import S3Error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(mock_minio_raw):
    """Instantiate MinIOClient with a patched underlying Minio object."""
    with patch("app.core.minio.Minio", return_value=mock_minio_raw):
        from app.core.minio import MinIOClient
        client = MinIOClient()
    return client


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------

class TestUploadFile:
    def test_upload_calls_put_object_with_correct_args(self, mock_minio_raw):
        client = _make_client(mock_minio_raw)
        content = b"BBL log data"

        result = client.upload_file(
            bucket="blackbox-logs",
            object_name="logs/1/flight.bbl",
            file_content=content,
        )

        mock_minio_raw.put_object.assert_called_once()
        call_kwargs = mock_minio_raw.put_object.call_args
        assert call_kwargs.kwargs["bucket_name"] == "blackbox-logs"
        assert call_kwargs.kwargs["object_name"] == "logs/1/flight.bbl"
        assert call_kwargs.kwargs["length"] == len(content)
        # data must be BytesIO wrapping the content
        data_arg = call_kwargs.kwargs["data"]
        assert isinstance(data_arg, BytesIO)
        assert data_arg.read() == content

    def test_upload_returns_object_name_on_success(self, mock_minio_raw):
        client = _make_client(mock_minio_raw)
        key = "logs/1/flight.bbl"
        result = client.upload_file("bucket", key, b"data")
        assert result == key

    def test_upload_raises_s3error_on_failure(self, mock_minio_raw):
        s3_err = S3Error(
            code="NoSuchBucket",
            message="The specified bucket does not exist.",
            resource=None,
            request_id=None,
            host_id=None,
            response=MagicMock(),
        )
        mock_minio_raw.put_object.side_effect = s3_err
        client = _make_client(mock_minio_raw)

        with pytest.raises(S3Error):
            client.upload_file("bad-bucket", "obj", b"data")

    def test_upload_empty_bytes(self, mock_minio_raw):
        """Uploading empty content should still call put_object with length=0."""
        client = _make_client(mock_minio_raw)
        result = client.upload_file("bucket", "empty.bbl", b"")
        call_kwargs = mock_minio_raw.put_object.call_args.kwargs
        assert call_kwargs["length"] == 0
        assert result == "empty.bbl"

    def test_upload_large_file(self, mock_minio_raw):
        """Large file content is passed as BytesIO with correct length."""
        client = _make_client(mock_minio_raw)
        content = b"x" * (10 * 1024 * 1024)  # 10 MB
        client.upload_file("bucket", "large.bbl", content)
        call_kwargs = mock_minio_raw.put_object.call_args.kwargs
        assert call_kwargs["length"] == len(content)


# ---------------------------------------------------------------------------
# download_file
# ---------------------------------------------------------------------------

class TestDownloadFile:
    def test_download_returns_bytes(self, mock_minio_raw):
        expected = b"log file bytes"
        mock_response = MagicMock()
        mock_response.read.return_value = expected
        mock_minio_raw.get_object.return_value = mock_response

        client = _make_client(mock_minio_raw)
        result = client.download_file("blackbox-logs", "logs/1/flight.bbl")

        assert result == expected

    def test_download_closes_response(self, mock_minio_raw):
        """Response.close() must be called to release the HTTP connection."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"data"
        mock_minio_raw.get_object.return_value = mock_response

        client = _make_client(mock_minio_raw)
        client.download_file("bucket", "obj")

        mock_response.close.assert_called_once()

    def test_download_calls_get_object_with_correct_args(self, mock_minio_raw):
        mock_response = MagicMock()
        mock_response.read.return_value = b"content"
        mock_minio_raw.get_object.return_value = mock_response

        client = _make_client(mock_minio_raw)
        client.download_file("my-bucket", "path/to/file.bbl")

        mock_minio_raw.get_object.assert_called_once_with(
            bucket_name="my-bucket", object_name="path/to/file.bbl"
        )

    def test_download_raises_s3error_on_failure(self, mock_minio_raw):
        s3_err = S3Error(
            code="NoSuchKey",
            message="The specified key does not exist.",
            resource=None,
            request_id=None,
            host_id=None,
            response=MagicMock(),
        )
        mock_minio_raw.get_object.side_effect = s3_err
        client = _make_client(mock_minio_raw)

        with pytest.raises(S3Error):
            client.download_file("bucket", "missing.bbl")


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------

class TestDeleteFile:
    def test_delete_calls_remove_object(self, mock_minio_raw):
        client = _make_client(mock_minio_raw)
        client.delete_file("blackbox-logs", "logs/1/flight.bbl")
        mock_minio_raw.remove_object.assert_called_once_with(
            bucket_name="blackbox-logs", object_name="logs/1/flight.bbl"
        )

    def test_delete_returns_none_on_success(self, mock_minio_raw):
        client = _make_client(mock_minio_raw)
        result = client.delete_file("bucket", "file.bbl")
        assert result is None

    def test_delete_raises_s3error_on_failure(self, mock_minio_raw):
        s3_err = S3Error(
            code="NoSuchKey",
            message="Object not found.",
            resource=None,
            request_id=None,
            host_id=None,
            response=MagicMock(),
        )
        mock_minio_raw.remove_object.side_effect = s3_err
        client = _make_client(mock_minio_raw)

        with pytest.raises(S3Error):
            client.delete_file("bucket", "ghost.bbl")


# ---------------------------------------------------------------------------
# file_exists
# ---------------------------------------------------------------------------

class TestFileExists:
    def test_returns_true_when_stat_succeeds(self, mock_minio_raw):
        mock_minio_raw.stat_object.return_value = MagicMock()
        client = _make_client(mock_minio_raw)

        assert client.file_exists("bucket", "present.bbl") is True

    def test_returns_false_when_s3error_raised(self, mock_minio_raw):
        s3_err = S3Error(
            code="NoSuchKey",
            message="Not found.",
            resource=None,
            request_id=None,
            host_id=None,
            response=MagicMock(),
        )
        mock_minio_raw.stat_object.side_effect = s3_err
        client = _make_client(mock_minio_raw)

        assert client.file_exists("bucket", "absent.bbl") is False

    def test_file_exists_calls_stat_object_with_correct_args(self, mock_minio_raw):
        client = _make_client(mock_minio_raw)
        client.file_exists("my-bucket", "some/key.bbl")
        mock_minio_raw.stat_object.assert_called_once_with(
            bucket_name="my-bucket", object_name="some/key.bbl"
        )


# ---------------------------------------------------------------------------
# MinIOClient initialisation
# ---------------------------------------------------------------------------

class TestMinIOClientInit:
    def test_init_strips_http_prefix_from_url(self):
        """Minio() should be called without the http:// scheme."""
        mock_minio_cls = MagicMock()
        with patch("app.core.minio.Minio", mock_minio_cls):
            with patch("app.core.minio.settings") as mock_settings:
                mock_settings.minio_public_url = "http://minio:9000"
                mock_settings.minio_root_user = "admin"
                mock_settings.minio_root_password = "secret"
                mock_settings.minio_bucket_blackbox_logs = "blackbox-logs"
                mock_settings.minio_bucket_assets = "assets"
                from app.core.minio import MinIOClient
                MinIOClient()
        first_arg = mock_minio_cls.call_args[0][0]
        assert not first_arg.startswith("http://")
        assert first_arg == "minio:9000"

    def test_init_strips_https_prefix_from_url(self):
        """Minio() should be called without the https:// scheme."""
        mock_minio_cls = MagicMock()
        with patch("app.core.minio.Minio", mock_minio_cls):
            with patch("app.core.minio.settings") as mock_settings:
                mock_settings.minio_public_url = "https://minio.example.com"
                mock_settings.minio_root_user = "admin"
                mock_settings.minio_root_password = "secret"
                mock_settings.minio_bucket_blackbox_logs = "blackbox-logs"
                mock_settings.minio_bucket_assets = "assets"
                from app.core.minio import MinIOClient
                MinIOClient()
        first_arg = mock_minio_cls.call_args[0][0]
        assert not first_arg.startswith("https://")
        assert first_arg == "minio.example.com"

    def test_bucket_attributes_set_from_settings(self):
        mock_minio_cls = MagicMock()
        with patch("app.core.minio.Minio", mock_minio_cls):
            with patch("app.core.minio.settings") as mock_settings:
                mock_settings.minio_public_url = "http://localhost:9000"
                mock_settings.minio_root_user = "user"
                mock_settings.minio_root_password = "pass"
                mock_settings.minio_bucket_blackbox_logs = "bb-logs"
                mock_settings.minio_bucket_assets = "my-assets"
                from app.core.minio import MinIOClient
                client = MinIOClient()
        assert client.bucket_blackbox == "bb-logs"
        assert client.bucket_assets == "my-assets"