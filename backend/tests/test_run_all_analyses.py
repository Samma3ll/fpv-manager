"""Unit tests for run_all_analyses task module gating and tune score behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.workers.tasks import run_all_analyses


def _build_session(log_entry, enabled_modules):
    session = MagicMock()

    log_result = MagicMock()
    log_result.scalar_one_or_none.return_value = log_entry

    enabled_modules_result = MagicMock()
    enabled_modules_scalars = MagicMock()
    enabled_modules_scalars.all.return_value = enabled_modules
    enabled_modules_result.scalars.return_value = enabled_modules_scalars

    session.execute = MagicMock(side_effect=[log_result, enabled_modules_result])
    session.query.return_value.filter.return_value.delete.return_value = None
    return session


def _run_all_analyses(enabled_modules, tune_score_result):
    log_entry = SimpleNamespace(id=1, file_path="blackbox-logs/1/test.bbl", error_message=None)
    session = _build_session(log_entry, enabled_modules)

    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    session_factory.return_value.__exit__.return_value = False

    mock_minio = MagicMock()
    mock_minio.bucket_blackbox = "blackbox-logs"
    mock_minio.download_file.return_value = b"bbl-content"

    with (
        patch("app.workers.tasks.get_sync_session_factory", return_value=session_factory),
        patch("app.workers.tasks.minio_client", mock_minio),
        patch("app.analysis.utils.load_parser_from_file_content", return_value=MagicMock()),
        patch("app.analysis.step_response.analyze_step_response", return_value={"step": "ok"}) as step_mock,
        patch("app.analysis.fft_noise.analyze_fft_noise", return_value={"fft": "ok"}) as fft_mock,
        patch("app.analysis.pid_error.analyze_pid_error", return_value={"pid": "ok"}) as pid_mock,
        patch("app.analysis.motor_analysis.analyze_motor_output", return_value={"motor": "ok"}) as motor_mock,
        patch("app.analysis.tune_score.score_tune_quality", return_value=tune_score_result) as tune_mock,
    ):
        result = run_all_analyses.run(log_entry.id)

    return result, step_mock, fft_mock, pid_mock, motor_mock, tune_mock


def test_tune_score_returned_when_enabled():
    result, step_mock, fft_mock, pid_mock, motor_mock, tune_mock = _run_all_analyses(
        enabled_modules=["tune_score"],
        tune_score_result={"overall_score": 72.0},
    )

    step_mock.assert_not_called()
    fft_mock.assert_not_called()
    pid_mock.assert_not_called()
    motor_mock.assert_not_called()
    tune_mock.assert_called_once()
    assert result["tune_score"] == 72.0
    assert result["modules_analyzed"] == 1


def test_tune_score_defaults_to_zero_when_disabled():
    result, step_mock, _, _, _, tune_mock = _run_all_analyses(
        enabled_modules=["step_response"],
        tune_score_result={"overall_score": 72.0},
    )

    step_mock.assert_called_once()
    tune_mock.assert_not_called()
    assert result["tune_score"] == 0
    assert result["modules_analyzed"] == 1


def test_tune_score_defaults_to_zero_when_overall_score_missing():
    result, _, _, _, _, tune_mock = _run_all_analyses(
        enabled_modules=["tune_score"],
        tune_score_result={"not_overall_score": 72.0},
    )

    tune_mock.assert_called_once()
    assert result["tune_score"] == 0
    assert result["modules_analyzed"] == 1
