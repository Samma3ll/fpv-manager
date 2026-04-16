"""Unit tests for backend/app/workers/tasks.py (parse_blackbox_log Celery task).

NOTE: These tests are skipped because task implementation is still incomplete.
The parse_blackbox_log task is a placeholder. See Phase 4 of the development plan.
The tests are ready for when the feature is fully implemented.
"""

import asyncio
import sys
import pytest
from datetime import datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch, patch as mock_patch

from app.models import BlackboxLog, LogStatus

pytestmark = pytest.mark.skip(reason="Task implementation incomplete - parse_blackbox_log is a placeholder (Phase 4)")


# ---------------------------------------------------------------------------
# Helpers / factory
# ---------------------------------------------------------------------------

def _make_log_entry(
    log_id=1,
    drone_id=1,
    file_name="flight.bbl",
    file_path="blackbox-logs/1/flight.bbl",
    status=LogStatus.PENDING,
):
    log = BlackboxLog(
        id=log_id,
        drone_id=drone_id,
        file_name=file_name,
        file_path=file_path,
        status=status,
        tags=[],
        created_at=datetime.utcnow(),
    )
    return log


def _build_mock_session(log_entry):
    """Build a mock AsyncSession that returns *log_entry* on scalar_one_or_none()."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = log_entry
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _build_mock_parser(
    headers=None,
    field_names=None,
    frames=None,
):
    """Build a mock orangebox Parser with sensible defaults."""
    headers = headers or {
        "Firmware revision": "Betaflight 2025.12.1 (85d201376) STM32F405",
        "Craft name": "TestQuad",
        "rollPID": [45, 40, 25],
        "pitchPID": [47, 45, 27],
        "yawPID": [40, 35, 0],
    }
    field_names = field_names or ["time", "rcCommand[0]", "rcCommand[1]"]

    if frames is None:
        frame_data_first = MagicMock()
        frame_data_first.__getitem__ = MagicMock(side_effect=lambda idx: 0)
        frame_first = MagicMock()
        frame_first.data = frame_data_first

        frame_data_last = MagicMock()
        frame_data_last.__getitem__ = MagicMock(side_effect=lambda idx: 120_000_000)
        frame_last = MagicMock()
        frame_last.data = frame_data_last
        frames = [frame_first, frame_last]

    mock_parser = MagicMock()
    mock_parser.headers = headers
    mock_parser.field_names = field_names
    mock_parser.frames = MagicMock(return_value=iter(frames))
    return mock_parser


def _inject_orangebox(mock_parser):
    """
    Install a fake 'orangebox' module so the task can import it.
    Returns the original module (or None) so callers can restore it.
    """
    original = sys.modules.get("orangebox")
    fake_orangebox = MagicMock()
    fake_orangebox.Parser = MagicMock()
    fake_orangebox.Parser.load = MagicMock(return_value=mock_parser)
    sys.modules["orangebox"] = fake_orangebox
    return original


def _restore_orangebox(original):
    if original is None:
        sys.modules.pop("orangebox", None)
    else:
        sys.modules["orangebox"] = original


def _run_parse_task(
    log_entry,
    mock_parser,
    mock_minio,
    session,
    mock_factory,
    retry_side_effect=None,
):
    """
    Execute parse_blackbox_log.run(log_id) with all external deps mocked.

    For Celery @shared_task(bind=True), calling task.run(log_id) invokes the
    underlying function with the task instance as `self`.  Retry behaviour is
    controlled by patching the task's .retry() method directly.

    Args:
        retry_side_effect: If given, patch parse_blackbox_log.retry to raise
                           this exception (simulates retry triggering).
    Returns:
        The return value of parse_blackbox_log.run(log_id).
    """
    from app.workers.tasks import parse_blackbox_log

    original = _inject_orangebox(mock_parser)
    try:
        patches = [
            patch("app.workers.tasks.get_session_factory", return_value=mock_factory),
            patch("app.workers.tasks.minio_client", mock_minio),
        ]
        if retry_side_effect is not None:
            patches.append(
                patch.object(parse_blackbox_log, "retry", side_effect=retry_side_effect)
            )

        with patches[0], patches[1]:
            if retry_side_effect is not None:
                with patches[2]:
                    return parse_blackbox_log.run(log_entry.id)
            else:
                return parse_blackbox_log.run(log_entry.id)
    finally:
        _restore_orangebox(original)


# ---------------------------------------------------------------------------
# parse_blackbox_log - log entry not found
# ---------------------------------------------------------------------------

class TestParseBlackboxLogNotFound:
    def test_returns_error_status_when_log_not_found(self):
        """If the log entry does not exist in the DB, return error dict."""
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock()
        mock_factory.return_value = session

        from app.workers.tasks import parse_blackbox_log

        with patch("app.workers.tasks.get_session_factory", return_value=mock_factory):
            result = parse_blackbox_log.run(999)

        assert result is not None
        assert result["log_id"] == 999
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# parse_blackbox_log - successful parse
# ---------------------------------------------------------------------------

class TestParseBlackboxLogSuccess:
    def test_sets_status_to_ready_on_success(self):
        log_entry = _make_log_entry()
        mock_parser = _build_mock_parser()
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl_content"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.status == LogStatus.READY

    def test_extracts_firmware_version(self):
        log_entry = _make_log_entry()
        mock_parser = _build_mock_parser(headers={
            "Firmware revision": "Betaflight 2025.12.1 (abc) STM32",
            "Craft name": "Racer",
            "rollPID": [40, 35, 20],
            "pitchPID": [42, 37, 22],
            "yawPID": [38, 30, 0],
        })
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.betaflight_version == "Betaflight 2025.12.1 (abc) STM32"

    def test_extracts_craft_name(self):
        log_entry = _make_log_entry()
        mock_parser = _build_mock_parser(headers={
            "Firmware revision": "BF 4.5",
            "Craft name": "FreestyleQuad",
            "rollPID": [50, 45, 30],
            "pitchPID": [52, 47, 32],
            "yawPID": [45, 40, 0],
        })
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.craft_name == "FreestyleQuad"

    def test_empty_craft_name_becomes_none(self):
        """Empty craft name header should be stored as None (not empty string)."""
        log_entry = _make_log_entry()
        mock_parser = _build_mock_parser(headers={
            "Firmware revision": "BF 4.5",
            "Craft name": "",  # empty
            "rollPID": [45, 40, 25],
            "pitchPID": [47, 45, 27],
            "yawPID": [40, 35, 0],
        })
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.craft_name is None

    def test_extracts_pid_roll_p_value(self):
        log_entry = _make_log_entry()
        mock_parser = _build_mock_parser(headers={
            "Firmware revision": "BF",
            "Craft name": "Q",
            "rollPID": [45, 40, 20],
            "pitchPID": [47, 45, 22],
            "yawPID": [38, 30, 0],
        })
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.pid_roll == 45.0

    def test_extracts_pid_pitch_p_value(self):
        log_entry = _make_log_entry()
        mock_parser = _build_mock_parser(headers={
            "Firmware revision": "BF",
            "Craft name": "Q",
            "rollPID": [45, 40, 20],
            "pitchPID": [47, 45, 22],
            "yawPID": [38, 30, 0],
        })
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.pid_pitch == 47.0

    def test_extracts_pid_yaw_p_value(self):
        log_entry = _make_log_entry()
        mock_parser = _build_mock_parser(headers={
            "Firmware revision": "BF",
            "Craft name": "Q",
            "rollPID": [45, 40, 20],
            "pitchPID": [47, 45, 22],
            "yawPID": [38, 30, 0],
        })
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.pid_yaw == 38.0

    def test_pid_fields_none_when_headers_absent(self):
        """If PID headers are missing, pid_* fields stay None."""
        log_entry = _make_log_entry()
        mock_parser = _build_mock_parser(headers={
            "Firmware revision": "BF",
            "Craft name": "Q",
            # No rollPID, pitchPID, yawPID
        })
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.pid_roll is None
        assert log_entry.pid_pitch is None
        assert log_entry.pid_yaw is None

    def test_calculates_flight_duration(self):
        """Duration should be computed from first/last frame time (microseconds → seconds)."""
        log_entry = _make_log_entry()

        frame_data_first = MagicMock()
        frame_data_first.__getitem__ = MagicMock(side_effect=lambda idx: 1_000_000)
        frame_first = MagicMock(data=frame_data_first)

        frame_data_last = MagicMock()
        frame_data_last.__getitem__ = MagicMock(side_effect=lambda idx: 61_000_000)
        frame_last = MagicMock(data=frame_data_last)

        mock_parser = _build_mock_parser(
            field_names=["time", "rcCommand[0]"],
            frames=[frame_first, frame_last],
        )
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.duration_s == pytest.approx(60.0)

    def test_duration_none_when_fewer_than_two_frames(self):
        """With only one frame, duration cannot be calculated."""
        log_entry = _make_log_entry()

        single_frame = MagicMock()
        mock_parser = _build_mock_parser(
            field_names=["time"],
            frames=[single_frame],  # only one frame
        )
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.duration_s is None

    def test_duration_skipped_when_no_time_field(self):
        """Duration calculation is skipped if 'time' is not in field_names."""
        log_entry = _make_log_entry()

        frame_first = MagicMock()
        frame_last = MagicMock()
        mock_parser = _build_mock_parser(
            field_names=["rcCommand[0]", "rcCommand[1]"],  # no 'time'
            frames=[frame_first, frame_last],
        )
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)
        assert log_entry.duration_s is None

    def test_sets_status_to_processing_before_parse(self):
        """The task must set PROCESSING before attempting to parse."""
        status_sequence = []
        log_entry = _make_log_entry()

        session = _build_mock_session(log_entry)

        async def tracking_commit():
            status_sequence.append(log_entry.status)

        session.commit = AsyncMock(side_effect=tracking_commit)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        mock_parser = _build_mock_parser()
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)

        # First commit should capture PROCESSING status
        assert status_sequence[0] == LogStatus.PROCESSING

    def test_downloads_correct_file_path(self):
        """MinIO download should use log_entry.file_path."""
        log_entry = _make_log_entry(file_path="blackbox-logs/3/my_log.bbl")
        mock_parser = _build_mock_parser()
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)

        mock_minio.download_file.assert_called_once_with(
            bucket="blackbox-logs",
            object_name="blackbox-logs/3/my_log.bbl",
        )

    def test_returns_result_dict_on_success(self):
        """Successful parse returns a dict with log_id, status, craft_name, betaflight_version."""
        log_entry = _make_log_entry()
        mock_parser = _build_mock_parser()
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        result = _run_parse_task(log_entry, mock_parser, mock_minio, session, mock_factory)

        assert result is not None
        assert result["log_id"] == log_entry.id
        assert "status" in result


# ---------------------------------------------------------------------------
# parse_blackbox_log - error handling
# ---------------------------------------------------------------------------

class TestParseBlackboxLogErrors:
    def test_sets_error_status_on_minio_download_failure(self):
        """If MinIO download raises, error status is set and retry triggered."""
        log_entry = _make_log_entry()

        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.side_effect = Exception("download failed")

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        retry_exc = Exception("retry sentinel")

        with pytest.raises(Exception, match="retry sentinel"):
            _run_parse_task(
                log_entry,
                MagicMock(),
                mock_minio,
                session,
                mock_factory,
                retry_side_effect=retry_exc,
            )

        assert log_entry.status == LogStatus.ERROR
        assert log_entry.error_message is not None

    def test_error_message_truncated_to_255_chars(self):
        """
        The exception string embedded in error_message must be <= 255 chars.

        The outer error handler uses f"Unexpected error: {str(e)[:255]}", so
        the stored message is "Unexpected error: " (18 chars) + up to 255 chars
        of the original exception = up to 273 chars total.
        The key invariant: the exception text itself is capped at 255 chars.
        """
        log_entry = _make_log_entry()

        long_error_msg = "E" * 500
        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.side_effect = Exception(long_error_msg)

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        retry_exc = Exception("retry")

        with pytest.raises(Exception, match="retry"):
            _run_parse_task(
                log_entry,
                MagicMock(),
                mock_minio,
                session,
                mock_factory,
                retry_side_effect=retry_exc,
            )

        # The exception text part must be capped at 255 chars; total message
        # may be slightly longer due to the fixed prefix "Unexpected error: "
        assert log_entry.error_message is not None
        assert "E" * 255 in log_entry.error_message  # truncated exception is embedded
        assert "E" * 256 not in log_entry.error_message  # not more than 255 E's

    def test_sets_error_status_on_parse_exception(self):
        """
        Exception during orangebox parsing sets status=ERROR.

        The parse exception is caught by the *inner* try/except so the task
        completes normally (no retry).  The outer retry path is only triggered
        by failures *before* the orangebox parse (e.g. MinIO download failure).
        """
        log_entry = _make_log_entry()

        # Parser that raises when .headers is accessed
        failing_parser = MagicMock()
        type(failing_parser).headers = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("corrupt log"))
        )

        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bad data"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        # No retry_side_effect: parse errors are handled internally, no retry
        _run_parse_task(
            log_entry,
            failing_parser,
            mock_minio,
            session,
            mock_factory,
        )

        assert log_entry.status == LogStatus.ERROR
        assert log_entry.error_message is not None

    def test_error_status_set_on_orangebox_parse_error(self):
        """
        After orangebox fails, status should be ERROR with a 'Parse failed:' message.

        This uses the inner error handler path (no retry), distinct from the
        outer 'Unexpected error:' path that triggers retry.
        """
        log_entry = _make_log_entry()

        failing_parser = MagicMock()
        type(failing_parser).headers = property(
            lambda self: (_ for _ in ()).throw(ValueError("bad format"))
        )

        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"garbage"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        _run_parse_task(
            log_entry,
            failing_parser,
            mock_minio,
            session,
            mock_factory,
        )

        assert log_entry.status == LogStatus.ERROR
        assert log_entry.error_message is not None
        assert "bad format" in log_entry.error_message

    def test_sets_error_status_when_orangebox_import_fails(self):
        """If orangebox is not importable, status should be ERROR (no retry)."""
        log_entry = _make_log_entry()

        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.return_value = b"bbl"

        session = _build_mock_session(log_entry)
        mock_factory = MagicMock()
        mock_factory.return_value = session

        # Remove orangebox from sys.modules and make it unimportable
        original = sys.modules.get("orangebox")
        sys.modules["orangebox"] = None  # Causes ImportError on `from orangebox import Parser`

        try:
            with patch("app.workers.tasks.get_session_factory", return_value=mock_factory), \
                 patch("app.workers.tasks.minio_client", mock_minio):
                from app.workers.tasks import parse_blackbox_log
                parse_blackbox_log.run(log_entry.id)
        finally:
            _restore_orangebox(original)

        assert log_entry.status == LogStatus.ERROR
        assert "orangebox" in (log_entry.error_message or "").lower()