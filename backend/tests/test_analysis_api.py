"""Unit/integration tests for GET /api/v1/logs/{log_id}/analyses endpoints."""

import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Sentinel for distinguishing "not provided" from None
_UNSET = object()

from httpx import AsyncClient, ASGITransport

from app.models import BlackboxLog, LogStatus, LogAnalysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_log_entry(log_id=1, drone_id=1):
    return BlackboxLog(
        id=log_id,
        drone_id=drone_id,
        file_name="flight.bbl",
        file_path=f"blackbox-logs/{drone_id}/flight.bbl",
        status=LogStatus.READY,
        tags=[],
        created_at=datetime.utcnow(),
    )


def _make_analysis(log_id, module, result_json=None):
    if result_json is None:
        result_json = {"overall_score": 85.0}
    analysis = LogAnalysis(
        id=1,
        log_id=log_id,
        module=module,
        result_json=result_json,
        created_at=datetime.utcnow(),
    )
    return analysis


def _make_session(log_entry, analyses=None, single_analysis=_UNSET):
    """
    Build an AsyncMock session that returns appropriate objects for
    the analysis API queries.

    The session.execute() calls are set up to handle sequential queries:
    1) Log existence check → log_entry (or None for 404 tests)
    2) Analyses query → analyses list OR single_analysis (may be None)
    """
    session = AsyncMock()

    # Build result mocks for sequential execute() calls
    call_results = []

    # First call: log lookup
    log_result = MagicMock()
    log_result.scalar_one_or_none.return_value = log_entry
    call_results.append(log_result)

    # Second call: analyses lookup (only when log exists and we need a second query)
    if single_analysis is not _UNSET:
        # For get_log_analysis endpoint - single_analysis may be None (404) or an object (200)
        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = single_analysis
        call_results.append(analysis_result)
    elif analyses is not None:
        # For get_log_analyses endpoint
        analysis_result = MagicMock()
        analysis_result.scalars.return_value.all.return_value = analyses
        call_results.append(analysis_result)

    session.execute = AsyncMock(side_effect=call_results)
    return session


def _make_test_app(session):
    from app.main import app as real_app
    from app.core import get_db_session

    async def override_get_db_session():
        yield session

    real_app.dependency_overrides[get_db_session] = override_get_db_session
    return real_app


# ---------------------------------------------------------------------------
# GET /{log_id}/analyses
# ---------------------------------------------------------------------------

class TestGetLogAnalyses:
    @pytest.mark.asyncio
    async def test_returns_200_with_analyses(self):
        log = _make_log_entry(log_id=10)
        analyses = [
            _make_analysis(10, "step_response", {"roll": {"rise_time_ms": 100}}),
            _make_analysis(10, "fft_noise", {"roll": {"peaks": []}}),
        ]
        session = _make_session(log, analyses=analyses)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/10/analyses")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_keyed_by_module(self):
        log = _make_log_entry(log_id=10)
        analyses = [
            _make_analysis(10, "step_response"),
            _make_analysis(10, "tune_score"),
        ]
        session = _make_session(log, analyses=analyses)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/10/analyses")

        data = response.json()
        assert "step_response" in data
        assert "tune_score" in data

    @pytest.mark.asyncio
    async def test_each_analysis_has_module_result_created_at(self):
        log = _make_log_entry(log_id=10)
        analyses = [_make_analysis(10, "pid_error", {"roll": {"rms_error": 5.0}})]
        session = _make_session(log, analyses=analyses)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/10/analyses")

        data = response.json()
        pid_data = data["pid_error"]
        assert "module" in pid_data
        assert "result" in pid_data
        assert "created_at" in pid_data

    @pytest.mark.asyncio
    async def test_returns_404_when_log_not_found(self):
        session = _make_session(None)  # log not found
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/999/analyses")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_no_analyses_exist(self):
        log = _make_log_entry(log_id=10)
        session = _make_session(log, analyses=[])  # empty list
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/10/analyses")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_detail_includes_log_id_when_log_not_found(self):
        session = _make_session(None)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/42/analyses")

        detail = response.json()["detail"]
        assert "42" in detail

    @pytest.mark.asyncio
    async def test_result_json_preserved(self):
        log = _make_log_entry(log_id=5)
        expected_result = {"overall_score": 77.5, "roll_score": 80.0}
        analyses = [_make_analysis(5, "tune_score", expected_result)]
        session = _make_session(log, analyses=analyses)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/5/analyses")

        data = response.json()
        assert data["tune_score"]["result"] == expected_result

    @pytest.mark.asyncio
    async def test_multiple_modules_all_returned(self):
        log = _make_log_entry(log_id=7)
        modules = ["step_response", "fft_noise", "pid_error", "motor_analysis", "tune_score"]
        analyses = [_make_analysis(7, m) for m in modules]
        session = _make_session(log, analyses=analyses)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/7/analyses")

        data = response.json()
        for module in modules:
            assert module in data


# ---------------------------------------------------------------------------
# GET /{log_id}/analyses/{module}
# ---------------------------------------------------------------------------

class TestGetLogAnalysis:
    @pytest.mark.asyncio
    async def test_returns_200_for_existing_analysis(self):
        log = _make_log_entry(log_id=10)
        analysis = _make_analysis(10, "step_response")
        session = _make_session(log, single_analysis=analysis)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/10/analyses/step_response")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_module_result_created_at(self):
        log = _make_log_entry(log_id=10)
        analysis = _make_analysis(10, "fft_noise", {"peaks": [{"frequency_hz": 100.0}]})
        session = _make_session(log, single_analysis=analysis)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/10/analyses/fft_noise")

        data = response.json()
        assert data["module"] == "fft_noise"
        assert "result" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_returns_404_when_log_not_found(self):
        session = _make_session(None)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/999/analyses/tune_score")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_module_not_found(self):
        log = _make_log_entry(log_id=10)
        session = _make_session(log, single_analysis=None)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/10/analyses/nonexistent_module")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_detail_includes_module_name(self):
        log = _make_log_entry(log_id=10)
        session = _make_session(log, single_analysis=None)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/10/analyses/custom_module")

        detail = response.json()["detail"]
        assert "custom_module" in detail

    @pytest.mark.asyncio
    async def test_result_json_preserved(self):
        log = _make_log_entry(log_id=3)
        expected_result = {"roll": {"rms_error": 4.2}, "pitch": {"rms_error": 3.1}}
        analysis = _make_analysis(3, "pid_error", expected_result)
        session = _make_session(log, single_analysis=analysis)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/3/analyses/pid_error")

        data = response.json()
        assert data["result"] == expected_result

    @pytest.mark.asyncio
    async def test_module_name_in_response_matches_url(self):
        log = _make_log_entry(log_id=8)
        analysis = _make_analysis(8, "motor_analysis")
        session = _make_session(log, single_analysis=analysis)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/8/analyses/motor_analysis")

        data = response.json()
        assert data["module"] == "motor_analysis"

    @pytest.mark.asyncio
    async def test_404_detail_includes_log_id_when_log_not_found(self):
        session = _make_session(None)
        app = _make_test_app(session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/logs/55/analyses/tune_score")

        detail = response.json()["detail"]
        assert "55" in detail