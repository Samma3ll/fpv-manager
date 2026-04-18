"""Unit tests for backend/app/api/v1/modules.py.

Tests list_modules, get_module, and update_module async API handlers
introduced in Phase 7.  All tests use AsyncMock sessions following the
pattern established in test_drones_api.py.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.modules import get_module, list_modules, update_module
from app.models.module import Module
from app.schemas.module import ModuleUpdate


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def _result_with_scalar(value):
    """Return a MagicMock whose scalar_one_or_none() returns *value*."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _result_with_scalar_count(count):
    """Return a MagicMock whose scalar() returns *count* (for count queries)."""
    result = MagicMock()
    result.scalar.return_value = count
    return result


def _result_with_scalars(values):
    """Return a MagicMock whose scalars().all() returns *values*."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _sample_module(
    module_id=1,
    name="step_response",
    display_name="Step Response Analysis",
    enabled=True,
    module_type="analysis",
    analysis_task="analyze_log_step_response",
    frontend_route="step_response",
    config_json=None,
):
    """Create a Module ORM instance for tests."""
    now = datetime.now(timezone.utc)
    return Module(
        id=module_id,
        name=name,
        display_name=display_name,
        description="A test analysis module",
        enabled=enabled,
        module_type=module_type,
        analysis_task=analysis_task,
        frontend_route=frontend_route,
        config_json=config_json if config_json is not None else {},
        created_at=now,
    )


# ---------------------------------------------------------------------------
# list_modules
# ---------------------------------------------------------------------------


class TestListModules:
    @pytest.mark.asyncio
    async def test_returns_all_modules_with_no_filters(self):
        """With no filter params, all modules are returned ordered by id."""
        modules = [
            _sample_module(1, "step_response"),
            _sample_module(2, "fft_noise", display_name="FFT Noise"),
        ]
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_with_scalar_count(2),
                _result_with_scalars(modules),
            ]
        )

        result = await list_modules(session)

        assert result.total == 2
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_modules(self):
        """Empty database returns items=[] and total=0."""
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_with_scalar_count(0),
                _result_with_scalars([]),
            ]
        )

        result = await list_modules(session)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_module_type_filter_passes_param(self):
        """module_type filter is applied; result reflects what DB returns."""
        analysis_module = _sample_module(1, "step_response", module_type="analysis")
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_with_scalar_count(1),
                _result_with_scalars([analysis_module]),
            ]
        )

        result = await list_modules(session, module_type="analysis")

        assert result.total == 1
        assert result.items[0].module_type == "analysis"

    @pytest.mark.asyncio
    async def test_enabled_only_filter_passes_param(self):
        """enabled_only=True is applied; result reflects what DB returns."""
        enabled_module = _sample_module(1, "step_response", enabled=True)
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_with_scalar_count(1),
                _result_with_scalars([enabled_module]),
            ]
        )

        result = await list_modules(session, enabled_only=True)

        assert result.total == 1
        assert result.items[0].enabled is True

    @pytest.mark.asyncio
    async def test_combined_filters_applied_together(self):
        """module_type and enabled_only can be combined."""
        module = _sample_module(1, "step_response", enabled=True, module_type="analysis")
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_with_scalar_count(1),
                _result_with_scalars([module]),
            ]
        )

        result = await list_modules(session, module_type="analysis", enabled_only=True)

        assert result.total == 1

    @pytest.mark.asyncio
    async def test_items_are_module_response_objects(self):
        """items in the response are ModuleResponse objects with all fields."""
        module = _sample_module(
            7,
            name="motor_analysis",
            display_name="Motor Analysis",
            analysis_task="analyze_log_motor",
            frontend_route="motor_analysis",
        )
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_with_scalar_count(1),
                _result_with_scalars([module]),
            ]
        )

        result = await list_modules(session)

        item = result.items[0]
        assert item.id == 7
        assert item.name == "motor_analysis"
        assert item.analysis_task == "analyze_log_motor"
        assert item.frontend_route == "motor_analysis"

    @pytest.mark.asyncio
    async def test_items_with_null_optional_fields_are_serialized(self):
        """Modules with None analysis_task / frontend_route are included correctly."""
        module = _sample_module(
            2,
            name="video",
            module_type="storage",
            analysis_task=None,
            frontend_route="video",
        )
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_with_scalar_count(1),
                _result_with_scalars([module]),
            ]
        )

        result = await list_modules(session)

        assert result.items[0].analysis_task is None
        assert result.items[0].frontend_route == "video"

    @pytest.mark.asyncio
    async def test_total_count_matches_query_count(self):
        """total field reflects the count returned by the count query."""
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result_with_scalar_count(42),
                _result_with_scalars([]),
            ]
        )

        result = await list_modules(session)

        assert result.total == 42


# ---------------------------------------------------------------------------
# get_module
# ---------------------------------------------------------------------------


class TestGetModule:
    @pytest.mark.asyncio
    async def test_returns_module_when_found(self):
        """Existing module is returned as ModuleResponse."""
        module = _sample_module(3, "pid_error", display_name="PID Error")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        result = await get_module(3, session)

        assert result.id == 3
        assert result.name == "pid_error"
        assert result.display_name == "PID Error"

    @pytest.mark.asyncio
    async def test_raises_404_when_module_not_found(self):
        """HTTPException 404 is raised when the module ID does not exist."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(None))

        with pytest.raises(HTTPException) as exc_info:
            await get_module(999, session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_404_detail_contains_module_id(self):
        """404 error detail message includes the requested module ID."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(None))

        with pytest.raises(HTTPException) as exc_info:
            await get_module(77, session)

        assert "77" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_returns_all_module_fields(self):
        """All ModuleResponse fields are populated from the ORM object."""
        module = _sample_module(
            5,
            name="fft_noise",
            display_name="FFT Noise",
            enabled=False,
            module_type="analysis",
            analysis_task="analyze_log_fft",
            frontend_route="fft_noise",
            config_json={"window_size": 512},
        )
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        result = await get_module(5, session)

        assert result.enabled is False
        assert result.analysis_task == "analyze_log_fft"
        assert result.frontend_route == "fft_noise"
        assert result.config_json == {"window_size": 512}

    @pytest.mark.asyncio
    async def test_returns_module_with_null_optional_fields(self):
        """Module with None optional fields is serialized correctly."""
        module = _sample_module(
            8,
            name="gps_track",
            module_type="utility",
            analysis_task=None,
            frontend_route="gps_track",
        )
        module.description = None
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        result = await get_module(8, session)

        assert result.description is None
        assert result.analysis_task is None

    @pytest.mark.asyncio
    async def test_returns_disabled_module(self):
        """Disabled modules are returned without error (get_module has no enabled filter)."""
        module = _sample_module(4, "video", enabled=False, module_type="storage")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        result = await get_module(4, session)

        assert result.enabled is False


# ---------------------------------------------------------------------------
# update_module
# ---------------------------------------------------------------------------


class TestUpdateModule:
    @pytest.mark.asyncio
    async def test_raises_404_when_module_not_found(self):
        """HTTPException 404 is raised when the module ID does not exist."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(None))
        update = ModuleUpdate(enabled=True)

        with pytest.raises(HTTPException) as exc_info:
            await update_module(999, update, session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_404_detail_contains_module_id(self):
        """404 error detail includes the requested module ID."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(None))

        with pytest.raises(HTTPException) as exc_info:
            await update_module(55, ModuleUpdate(), session)

        assert "55" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_disables_module(self):
        """enabled=False in update payload is applied to the module."""
        module = _sample_module(1, "step_response", enabled=True)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        await update_module(1, ModuleUpdate(enabled=False), session)

        assert module.enabled is False

    @pytest.mark.asyncio
    async def test_enables_module(self):
        """enabled=True in update payload is applied to the module."""
        module = _sample_module(2, "video", enabled=False, module_type="storage")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        await update_module(2, ModuleUpdate(enabled=True), session)

        assert module.enabled is True

    @pytest.mark.asyncio
    async def test_updates_config_json(self):
        """config_json in update payload replaces existing config."""
        module = _sample_module(3, "fft_noise", config_json={})
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        new_config = {"threshold": 0.75, "window": 1024}
        await update_module(3, ModuleUpdate(config_json=new_config), session)

        assert module.config_json == new_config

    @pytest.mark.asyncio
    async def test_commits_and_refreshes_on_update(self):
        """commit() and refresh() are called after applying update."""
        module = _sample_module(4, "pid_error")
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        await update_module(4, ModuleUpdate(enabled=False), session)

        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(module)

    @pytest.mark.asyncio
    async def test_empty_update_payload_does_not_modify_fields(self):
        """An empty update payload leaves the module fields unchanged."""
        module = _sample_module(6, "motor_analysis", enabled=True)
        original_enabled = module.enabled
        original_config = module.config_json
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        await update_module(6, ModuleUpdate(), session)

        assert module.enabled == original_enabled
        assert module.config_json == original_config

    @pytest.mark.asyncio
    async def test_returns_updated_module_response(self):
        """Return value is a ModuleResponse reflecting the updated state."""
        module = _sample_module(7, "step_response", enabled=True)

        async def mock_refresh(m):
            """Simulate refresh by setting enabled=False on the module."""
            m.enabled = False

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))
        session.refresh = AsyncMock(side_effect=mock_refresh)

        result = await update_module(7, ModuleUpdate(enabled=False), session)

        assert result.enabled is False

    @pytest.mark.asyncio
    async def test_only_explicitly_set_fields_are_applied(self):
        """model_dump(exclude_unset=True) ensures only set fields are applied."""
        module = _sample_module(8, "fft_noise", enabled=True, config_json={"old": True})
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        # Only update config_json — enabled should stay unchanged
        await update_module(8, ModuleUpdate(config_json={"new": True}), session)

        assert module.enabled is True  # not changed
        assert module.config_json == {"new": True}

    @pytest.mark.asyncio
    async def test_update_both_enabled_and_config_json(self):
        """Both enabled and config_json can be updated in a single request."""
        module = _sample_module(9, "pid_error", enabled=True, config_json={})
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        await update_module(
            9,
            ModuleUpdate(enabled=False, config_json={"gain": 1.5}),
            session,
        )

        assert module.enabled is False
        assert module.config_json == {"gain": 1.5}

    @pytest.mark.asyncio
    async def test_update_does_not_change_non_updatable_fields(self):
        """Fields not in ModuleUpdate (name, module_type, etc.) are unaffected."""
        module = _sample_module(10, "step_response", module_type="analysis")
        original_name = module.name
        original_module_type = module.module_type
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result_with_scalar(module))

        await update_module(10, ModuleUpdate(enabled=False), session)

        assert module.name == original_name
        assert module.module_type == original_module_type