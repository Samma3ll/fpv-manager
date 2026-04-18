"""Unit tests for run_all_analyses Celery task in backend/app/workers/tasks.py.

Tests cover the Phase 7 changes: dynamic module dispatch via the Module table,
per-module error isolation, tune_score conditional execution, and result storage.

All external I/O (database, MinIO, analysis imports) is mocked so the tests
run without any infrastructure dependencies.

Patching notes:
  - `importlib` is imported *inside* run_all_analyses(), so we patch
    `importlib.import_module` at the stdlib level.
  - `load_parser_from_file_content` is imported inline from `app.analysis.utils`,
    so we patch it at `app.analysis.utils.load_parser_from_file_content`.
  - `LogAnalysis` is imported inline from `app.models`, so we patch at
    `app.models.LogAnalysis`.
  - `score_tune_quality` is imported inline from `app.analysis.tune_score`;
    we inject a fake module into sys.modules before the task runs.
"""

import sys
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models import BlackboxLog, LogStatus


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def _make_log_entry(log_id=1, file_path="blackbox-logs/1/flight.bbl"):
    """Return a minimal BlackboxLog ORM instance for testing."""
    return BlackboxLog(
        id=log_id,
        drone_id=1,
        file_name="flight.bbl",
        file_path=file_path,
        status=LogStatus.READY,
        tags=[],
        created_at=datetime.utcnow(),
    )


def _make_module_orm(name, enabled=True, module_type="analysis"):
    """Return a minimal Module-like object for the enabled modules query result."""
    m = MagicMock()
    m.name = name
    m.enabled = enabled
    m.module_type = module_type
    return m


def _make_sync_session(log_entry, enabled_module_names):
    """
    Build a synchronous mock session (context manager) that serves two execute calls:

    1. Returns log_entry via scalar_one_or_none().
    2. Returns Module mocks via scalars().all().
    """
    session = MagicMock()

    log_result = MagicMock()
    log_result.scalar_one_or_none.return_value = log_entry

    module_mocks = [_make_module_orm(name) for name in enabled_module_names]
    module_result = MagicMock()
    module_result.scalars.return_value.all.return_value = module_mocks

    session.execute.side_effect = [log_result, module_result]
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)

    return session


def _make_factory(session):
    """Wrap *session* in a factory callable that returns it as a context manager."""
    factory = MagicMock()
    factory.return_value = session
    return factory


def _make_mock_minio(file_content=b"fake_bbl_content"):
    """Return a mock MinIO client that returns *file_content* on download."""
    minio = MagicMock()
    minio.bucket_blackbox = "blackbox-logs"
    minio.download_file.return_value = file_content
    return minio


def _make_mock_parser():
    """Return a trivial mock parser (orangebox-like) for analysis functions."""
    return MagicMock()


def _make_mock_import_fn(analysis_func_results):
    """
    Build a fake `importlib.import_module` function.

    Maps each import_path to a mock module whose analysis function returns the
    corresponding entry from *analysis_func_results* (module_name -> result dict).
    """
    path_to_name = {
        "app.analysis.step_response": "step_response",
        "app.analysis.fft_noise": "fft_noise",
        "app.analysis.pid_error": "pid_error",
        "app.analysis.motor_analysis": "motor_analysis",
    }

    def fake_import(import_path):
        mock_mod = MagicMock()
        name = path_to_name.get(import_path)
        result = analysis_func_results.get(name, {"data": "ok"}) if name else {"data": "ok"}
        mock_func = MagicMock(return_value=result)
        mock_mod.analyze_step_response = mock_func
        mock_mod.analyze_fft_noise = mock_func
        mock_mod.analyze_pid_error = mock_func
        mock_mod.analyze_motor_output = mock_func
        return mock_mod

    return fake_import


def _run_task(
    log_id,
    session,
    mock_minio,
    analysis_results=None,
    tune_score_result=None,
    parser=None,
    retry_side_effect=None,
):
    """
    Execute run_all_analyses.run(log_id) with all external deps mocked.

    Args:
        log_id: Log primary key to pass to the task.
        session: Mock sync session returned by the session factory.
        mock_minio: Mock MinIO client.
        analysis_results: Dict of module_name -> result dict for analysis functions.
        tune_score_result: Return value of score_tune_quality(). Defaults to {}.
        parser: Mock parser for load_parser_from_file_content.
        retry_side_effect: If provided, patch run_all_analyses.retry to raise this.
    Returns:
        Return value of run_all_analyses.run(log_id).
    """
    from app.workers.tasks import run_all_analyses

    factory = _make_factory(session)
    parser = parser or _make_mock_parser()
    analysis_results = analysis_results or {}
    tune_result = tune_score_result if tune_score_result is not None else {}

    fake_import = _make_mock_import_fn(analysis_results)
    mock_log_analysis_cls = MagicMock()

    mock_tune_module = MagicMock()
    mock_tune_module.score_tune_quality.return_value = tune_result

    patches = [
        patch("app.workers.tasks.get_sync_session_factory", return_value=factory),
        patch("app.workers.tasks.minio_client", mock_minio),
        # importlib is imported inline inside the function; patch at stdlib level
        patch("importlib.import_module", side_effect=fake_import),
        # load_parser_from_file_content imported inline; patch at origin
        patch("app.analysis.utils.load_parser_from_file_content", return_value=parser),
        # LogAnalysis imported inline from app.models; patch at models
        patch("app.models.LogAnalysis", mock_log_analysis_cls),
        # score_tune_quality imported inline; inject fake module
        patch.dict(sys.modules, {"app.analysis.tune_score": mock_tune_module}),
    ]

    if retry_side_effect is not None:
        patches.append(
            patch.object(run_all_analyses, "retry", side_effect=retry_side_effect)
        )

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return run_all_analyses.run(log_id)


# ---------------------------------------------------------------------------
# run_all_analyses — log entry not found
# ---------------------------------------------------------------------------


class TestRunAllAnalysesNotFound:
    def test_returns_error_dict_when_log_not_found(self):
        """If the BlackboxLog does not exist, return error dict without crashing."""
        session = MagicMock()
        not_found_result = MagicMock()
        not_found_result.scalar_one_or_none.return_value = None
        session.execute.return_value = not_found_result
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)

        factory = _make_factory(session)

        from app.workers.tasks import run_all_analyses

        with patch("app.workers.tasks.get_sync_session_factory", return_value=factory), \
             patch("app.workers.tasks.minio_client", MagicMock()):
            result = run_all_analyses.run(999)

        assert result["log_id"] == 999
        assert result["status"] == "error"

    def test_returns_correct_log_id_in_error_dict(self):
        """Error dict log_id matches the provided log_id argument."""
        session = MagicMock()
        not_found_result = MagicMock()
        not_found_result.scalar_one_or_none.return_value = None
        session.execute.return_value = not_found_result
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)

        factory = _make_factory(session)

        from app.workers.tasks import run_all_analyses

        with patch("app.workers.tasks.get_sync_session_factory", return_value=factory), \
             patch("app.workers.tasks.minio_client", MagicMock()):
            result = run_all_analyses.run(42)

        assert result["log_id"] == 42


# ---------------------------------------------------------------------------
# run_all_analyses — enabled module dispatch
# ---------------------------------------------------------------------------


class TestRunAllAnalysesEnabledModules:
    def test_all_enabled_modules_run(self):
        """All modules in ANALYSIS_REGISTRY that are enabled are executed."""
        log_entry = _make_log_entry()
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["step_response", "fft_noise", "pid_error", "motor_analysis"],
        )
        mock_minio = _make_mock_minio()

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={
                "step_response": {"sr": 1},
                "fft_noise": {"fft": 2},
                "pid_error": {"pid": 3},
                "motor_analysis": {"motor": 4},
            },
        )

        assert result["status"] == "success"
        assert result["modules_analyzed"] == 4

    def test_disabled_modules_are_skipped(self):
        """Modules not in the enabled set are excluded from analysis."""
        log_entry = _make_log_entry()
        # Only step_response is enabled
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["step_response"],
        )
        mock_minio = _make_mock_minio()

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={"step_response": {"sr": 1}},
        )

        assert result["status"] == "success"
        assert result["modules_analyzed"] == 1

    def test_no_enabled_modules_returns_zero_analyzed(self):
        """With no enabled modules, modules_analyzed is 0."""
        log_entry = _make_log_entry()
        session = _make_sync_session(log_entry, enabled_module_names=[])
        mock_minio = _make_mock_minio()

        result = _run_task(log_id=1, session=session, mock_minio=mock_minio)

        assert result["status"] == "success"
        assert result["modules_analyzed"] == 0

    def test_modules_analyzed_count_reflects_actual_run(self):
        """modules_analyzed equals number of modules that were processed."""
        log_entry = _make_log_entry()
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["step_response", "fft_noise"],
        )
        mock_minio = _make_mock_minio()

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={
                "step_response": {"ok": True},
                "fft_noise": {"ok": True},
            },
        )

        assert result["modules_analyzed"] == 2

    def test_returns_log_id_in_success_result(self):
        """Success result contains the correct log_id."""
        log_entry = _make_log_entry(log_id=77)
        session = _make_sync_session(log_entry, enabled_module_names=["step_response"])
        mock_minio = _make_mock_minio()

        result = _run_task(77, session, mock_minio, {"step_response": {"x": 1}})

        assert result["log_id"] == 77

    def test_minio_download_called_with_correct_args(self):
        """MinIO download uses the log entry's file_path."""
        log_entry = _make_log_entry(file_path="blackbox-logs/5/my_log.bbl")
        session = _make_sync_session(log_entry, enabled_module_names=["step_response"])
        mock_minio = _make_mock_minio()

        _run_task(1, session, mock_minio, {"step_response": {}})

        mock_minio.download_file.assert_called_once_with(
            bucket="blackbox-logs",
            object_name="blackbox-logs/5/my_log.bbl",
        )


# ---------------------------------------------------------------------------
# run_all_analyses — tune_score conditional logic
# ---------------------------------------------------------------------------


class TestRunAllAnalysesTuneScore:
    def test_tune_score_runs_when_enabled(self):
        """tune_score analysis runs when 'tune_score' is in the enabled modules set."""
        log_entry = _make_log_entry()
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["step_response", "tune_score"],
        )
        mock_minio = _make_mock_minio()
        tune_result = {"overall_score": 85.5, "grade": "B"}

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={"step_response": {"sr": 1}},
            tune_score_result=tune_result,
        )

        # tune_score is included in modules_analyzed count
        assert result["modules_analyzed"] >= 2  # step_response + tune_score

    def test_tune_score_not_run_when_not_in_enabled_set(self):
        """tune_score is skipped when its module is not enabled."""
        log_entry = _make_log_entry()
        # tune_score NOT in enabled modules
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["step_response"],
        )
        mock_minio = _make_mock_minio()

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={"step_response": {"sr": 1}},
            tune_score_result={"overall_score": 99},  # should not be used
        )

        # modules_analyzed should be 1 (only step_response), tune_score excluded
        assert result["modules_analyzed"] == 1

    def test_tune_score_returned_in_result(self):
        """Overall score from tune_score result is in the success return dict."""
        log_entry = _make_log_entry()
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["tune_score"],
        )
        mock_minio = _make_mock_minio()

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={},
            tune_score_result={"overall_score": 72.0},
        )

        assert result["tune_score"] == 72.0

    def test_tune_score_defaults_to_zero_when_no_score_key(self):
        """If tune_score result dict has no 'overall_score', result returns 0."""
        log_entry = _make_log_entry()
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["tune_score"],
        )
        mock_minio = _make_mock_minio()

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={},
            tune_score_result={"some_other_key": "value"},
        )

        assert result["tune_score"] == 0

    def test_tune_score_defaults_to_zero_when_disabled(self):
        """When tune_score module is disabled, tune_score in result is 0."""
        log_entry = _make_log_entry()
        session = _make_sync_session(log_entry, enabled_module_names=["step_response"])
        mock_minio = _make_mock_minio()

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={"step_response": {"sr": 1}},
        )

        assert result["tune_score"] == 0


# ---------------------------------------------------------------------------
# run_all_analyses — per-module error isolation
# ---------------------------------------------------------------------------


def _run_task_with_custom_import(log_id, session, mock_minio, fake_import, tune_result=None):
    """Execute run_all_analyses.run with a custom importlib.import_module fake."""
    from app.workers.tasks import run_all_analyses

    factory = _make_factory(session)
    parser = _make_mock_parser()
    tune_result = tune_result or {}

    mock_tune_module = MagicMock()
    mock_tune_module.score_tune_quality.return_value = tune_result

    with patch("app.workers.tasks.get_sync_session_factory", return_value=factory), \
         patch("app.workers.tasks.minio_client", mock_minio), \
         patch("importlib.import_module", side_effect=fake_import), \
         patch("app.analysis.utils.load_parser_from_file_content", return_value=parser), \
         patch("app.models.LogAnalysis", MagicMock()), \
         patch.dict(sys.modules, {"app.analysis.tune_score": mock_tune_module}):
        return run_all_analyses.run(log_id)


class TestRunAllAnalysesModuleErrors:
    def test_module_error_does_not_abort_other_modules(self):
        """A failure in one analysis module does not prevent others from running."""
        log_entry = _make_log_entry()
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["step_response", "fft_noise"],
        )
        mock_minio = _make_mock_minio()

        def fake_import_with_error(import_path):
            mock_mod = MagicMock()
            if "step_response" in import_path:
                mock_mod.analyze_step_response = MagicMock(
                    side_effect=RuntimeError("analysis failed")
                )
            else:
                mock_mod.analyze_fft_noise = MagicMock(return_value={"fft": 1})
            return mock_mod

        result = _run_task_with_custom_import(1, session, mock_minio, fake_import_with_error)

        # Both modules attempted; step_response stores error dict, fft_noise succeeds
        assert result["status"] == "success"
        assert result["modules_analyzed"] == 2

    def test_single_module_failure_still_returns_success_status(self):
        """Per-module failures are isolated; overall task still returns status=success."""
        log_entry = _make_log_entry()
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["fft_noise"],
        )
        mock_minio = _make_mock_minio()

        def fake_import_raises(import_path):
            mock_mod = MagicMock()
            mock_mod.analyze_fft_noise = MagicMock(side_effect=ValueError("bad data"))
            return mock_mod

        result = _run_task_with_custom_import(1, session, mock_minio, fake_import_raises)

        assert result["status"] == "success"
        assert result["modules_analyzed"] == 1  # still stored, with error dict


# ---------------------------------------------------------------------------
# run_all_analyses — database operations
# ---------------------------------------------------------------------------


class TestRunAllAnalysesDatabaseOps:
    def test_existing_analyses_deleted_before_storing_new(self):
        """Existing LogAnalysis rows for the log are deleted before inserting new ones."""
        log_entry = _make_log_entry()
        session = _make_sync_session(log_entry, enabled_module_names=["step_response"])
        mock_minio = _make_mock_minio()

        _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={"step_response": {"sr": 1}},
        )

        # session.query(...).filter(...).delete() should have been called
        session.query.assert_called()

    def test_session_committed_after_storing_results(self):
        """Session is committed once after storing all analysis results."""
        log_entry = _make_log_entry()
        session = _make_sync_session(log_entry, enabled_module_names=["step_response"])
        mock_minio = _make_mock_minio()

        _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={"step_response": {"sr": 1}},
        )

        session.commit.assert_called()

    def test_analysis_result_added_to_session_for_each_module(self):
        """session.add() is called once per analysis result."""
        log_entry = _make_log_entry()
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["step_response", "fft_noise"],
        )
        mock_minio = _make_mock_minio()

        _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={
                "step_response": {"sr": 1},
                "fft_noise": {"fft": 1},
            },
        )

        # 2 modules -> 2 add calls
        assert session.add.call_count == 2


# ---------------------------------------------------------------------------
# run_all_analyses — minio download failure / retry
# ---------------------------------------------------------------------------


class TestRunAllAnalysesDownloadFailure:
    def test_minio_download_failure_triggers_retry_raises(self):
        """MinIO download failure causes the task to retry (raises on .retry())."""
        log_entry = _make_log_entry()
        session = _make_sync_session(log_entry, enabled_module_names=["step_response"])

        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.side_effect = IOError("S3 connection failed")

        from app.workers.tasks import run_all_analyses

        factory = _make_factory(session)
        parser = _make_mock_parser()
        mock_tune_module = MagicMock()

        retry_exc = Exception("retry sentinel")

        with patch("app.workers.tasks.get_sync_session_factory", return_value=factory), \
             patch("app.workers.tasks.minio_client", mock_minio), \
             patch("importlib.import_module", side_effect=_make_mock_import_fn({})), \
             patch("app.analysis.utils.load_parser_from_file_content", return_value=parser), \
             patch("app.models.LogAnalysis", MagicMock()), \
             patch.dict(sys.modules, {"app.analysis.tune_score": mock_tune_module}), \
             patch.object(run_all_analyses, "retry", side_effect=retry_exc):
            with pytest.raises(Exception, match="retry sentinel"):
                run_all_analyses.run(1)

    def test_minio_download_failure_stores_error_message_on_log(self):
        """After download failure, the log entry's error_message is updated."""
        log_entry = _make_log_entry()

        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.side_effect = IOError("timeout")

        # Re-query within error handler returns the same log_entry
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        error_result = MagicMock()
        error_result.scalar_one_or_none.return_value = log_entry
        session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": log_entry}),
            MagicMock(**{"scalars.return_value.all.return_value": [_make_module_orm("step_response")]}),
            error_result,
        ]

        from app.workers.tasks import run_all_analyses

        factory = _make_factory(session)
        parser = _make_mock_parser()
        mock_tune_module = MagicMock()
        retry_exc = Exception("retry")

        with patch("app.workers.tasks.get_sync_session_factory", return_value=factory), \
             patch("app.workers.tasks.minio_client", mock_minio), \
             patch("importlib.import_module", side_effect=_make_mock_import_fn({})), \
             patch("app.analysis.utils.load_parser_from_file_content", return_value=parser), \
             patch("app.models.LogAnalysis", MagicMock()), \
             patch.dict(sys.modules, {"app.analysis.tune_score": mock_tune_module}), \
             patch.object(run_all_analyses, "retry", side_effect=retry_exc):
            with pytest.raises(Exception, match="retry"):
                run_all_analyses.run(1)

        assert log_entry.error_message is not None

    def test_error_message_truncated_to_255_chars(self):
        """Exception message stored in error_message is limited to 255 chars."""
        long_error = "X" * 500
        log_entry = _make_log_entry()

        mock_minio = MagicMock()
        mock_minio.bucket_blackbox = "blackbox-logs"
        mock_minio.download_file.side_effect = IOError(long_error)

        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        error_result = MagicMock()
        error_result.scalar_one_or_none.return_value = log_entry
        session.execute.side_effect = [
            MagicMock(**{"scalar_one_or_none.return_value": log_entry}),
            MagicMock(**{"scalars.return_value.all.return_value": []}),
            error_result,
        ]

        from app.workers.tasks import run_all_analyses

        factory = _make_factory(session)
        parser = _make_mock_parser()
        mock_tune_module = MagicMock()
        retry_exc = Exception("retry")

        with patch("app.workers.tasks.get_sync_session_factory", return_value=factory), \
             patch("app.workers.tasks.minio_client", mock_minio), \
             patch("importlib.import_module", side_effect=_make_mock_import_fn({})), \
             patch("app.analysis.utils.load_parser_from_file_content", return_value=parser), \
             patch("app.models.LogAnalysis", MagicMock()), \
             patch.dict(sys.modules, {"app.analysis.tune_score": mock_tune_module}), \
             patch.object(run_all_analyses, "retry", side_effect=retry_exc):
            with pytest.raises(Exception, match="retry"):
                run_all_analyses.run(1)

        assert log_entry.error_message is not None
        # Exception text portion must be capped at 255 chars
        assert "X" * 255 in log_entry.error_message
        assert "X" * 256 not in log_entry.error_message


# ---------------------------------------------------------------------------
# run_all_analyses — analysis registry coverage
# ---------------------------------------------------------------------------


class TestRunAllAnalysesRegistry:
    def test_analysis_registry_contains_expected_modules(self):
        """All four standard registry modules can be enabled and dispatched."""
        log_entry = _make_log_entry()
        all_modules = ["step_response", "fft_noise", "pid_error", "motor_analysis"]
        session = _make_sync_session(log_entry, enabled_module_names=all_modules)
        mock_minio = _make_mock_minio()

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={name: {name: True} for name in all_modules},
        )

        assert result["status"] == "success"
        assert result["modules_analyzed"] == len(all_modules)

    def test_unknown_module_name_in_db_is_ignored(self):
        """A module name in the DB that has no entry in ANALYSIS_REGISTRY is skipped."""
        log_entry = _make_log_entry()
        # 'unknown_module' does not exist in ANALYSIS_REGISTRY
        session = _make_sync_session(
            log_entry,
            enabled_module_names=["step_response", "unknown_module"],
        )
        mock_minio = _make_mock_minio()

        result = _run_task(
            log_id=1,
            session=session,
            mock_minio=mock_minio,
            analysis_results={"step_response": {"sr": 1}},
        )

        assert result["status"] == "success"
        # Only step_response was dispatched (unknown_module not in registry)
        assert result["modules_analyzed"] == 1

    def test_success_result_has_required_keys(self):
        """Success result dict has log_id, status, tune_score, modules_analyzed."""
        log_entry = _make_log_entry(log_id=10)
        session = _make_sync_session(log_entry, enabled_module_names=["step_response"])
        mock_minio = _make_mock_minio()

        result = _run_task(10, session, mock_minio, {"step_response": {"sr": 1}})

        assert "log_id" in result
        assert "status" in result
        assert "tune_score" in result
        assert "modules_analyzed" in result