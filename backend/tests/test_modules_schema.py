"""Unit tests for backend/app/schemas/module.py.

Tests ModuleResponse, ModuleUpdate, and ModuleListResponse Pydantic schemas
introduced in Phase 7 for the module registry / plugin architecture.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.module import ModuleListResponse, ModuleResponse, ModuleUpdate


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def _make_module_data(
    id=1,
    name="step_response",
    display_name="Step Response Analysis",
    description="Analyses step response data",
    enabled=True,
    module_type="analysis",
    analysis_task="analyze_log_step_response",
    frontend_route="step_response",
    config_json=None,
    created_at=None,
):
    """Return a dict suitable for constructing a ModuleResponse."""
    return {
        "id": id,
        "name": name,
        "display_name": display_name,
        "description": description,
        "enabled": enabled,
        "module_type": module_type,
        "analysis_task": analysis_task,
        "frontend_route": frontend_route,
        "config_json": config_json if config_json is not None else {},
        "created_at": created_at or datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# ModuleResponse — field validation
# ---------------------------------------------------------------------------


class TestModuleResponseFields:
    def test_valid_data_creates_schema(self):
        """A complete, valid payload should construct a ModuleResponse without error."""
        data = _make_module_data()
        schema = ModuleResponse(**data)

        assert schema.id == 1
        assert schema.name == "step_response"
        assert schema.display_name == "Step Response Analysis"
        assert schema.enabled is True
        assert schema.module_type == "analysis"

    def test_description_defaults_to_none(self):
        """Optional `description` field should default to None when omitted."""
        data = _make_module_data()
        data.pop("description")

        schema = ModuleResponse(**data)
        assert schema.description is None

    def test_description_can_be_none(self):
        """Explicit None for description is accepted."""
        data = _make_module_data(description=None)
        schema = ModuleResponse(**data)
        assert schema.description is None

    def test_analysis_task_defaults_to_none(self):
        """Optional `analysis_task` should default to None when omitted."""
        data = _make_module_data()
        data.pop("analysis_task")

        schema = ModuleResponse(**data)
        assert schema.analysis_task is None

    def test_analysis_task_can_be_none(self):
        """Explicit None for analysis_task is accepted."""
        data = _make_module_data(analysis_task=None)
        schema = ModuleResponse(**data)
        assert schema.analysis_task is None

    def test_frontend_route_defaults_to_none(self):
        """Optional `frontend_route` should default to None when omitted."""
        data = _make_module_data()
        data.pop("frontend_route")

        schema = ModuleResponse(**data)
        assert schema.frontend_route is None

    def test_frontend_route_can_be_none(self):
        """Explicit None for frontend_route is accepted."""
        data = _make_module_data(frontend_route=None)
        schema = ModuleResponse(**data)
        assert schema.frontend_route is None

    def test_config_json_defaults_to_empty_dict(self):
        """config_json should default to {} when omitted."""
        data = _make_module_data()
        data.pop("config_json")

        schema = ModuleResponse(**data)
        assert schema.config_json == {}

    def test_config_json_accepts_nested_dict(self):
        """config_json should accept arbitrary nested dict values."""
        config = {"threshold": 0.5, "nested": {"key": "value"}}
        data = _make_module_data(config_json=config)
        schema = ModuleResponse(**data)
        assert schema.config_json == config

    def test_created_at_stored_correctly(self):
        """created_at is stored and returned as provided."""
        now = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
        data = _make_module_data(created_at=now)
        schema = ModuleResponse(**data)
        assert schema.created_at == now

    def test_enabled_false(self):
        """enabled=False is accepted and stored."""
        data = _make_module_data(enabled=False)
        schema = ModuleResponse(**data)
        assert schema.enabled is False

    def test_storage_module_type(self):
        """module_type='storage' is valid."""
        data = _make_module_data(module_type="storage", analysis_task=None)
        schema = ModuleResponse(**data)
        assert schema.module_type == "storage"

    def test_utility_module_type(self):
        """module_type='utility' is valid."""
        data = _make_module_data(module_type="utility", analysis_task=None)
        schema = ModuleResponse(**data)
        assert schema.module_type == "utility"

    def test_missing_required_id_raises_validation_error(self):
        """Omitting required field 'id' must raise ValidationError."""
        data = _make_module_data()
        data.pop("id")

        with pytest.raises(ValidationError):
            ModuleResponse(**data)

    def test_missing_required_name_raises_validation_error(self):
        """Omitting required field 'name' must raise ValidationError."""
        data = _make_module_data()
        data.pop("name")

        with pytest.raises(ValidationError):
            ModuleResponse(**data)

    def test_missing_required_enabled_raises_validation_error(self):
        """Omitting required field 'enabled' must raise ValidationError."""
        data = _make_module_data()
        data.pop("enabled")

        with pytest.raises(ValidationError):
            ModuleResponse(**data)

    def test_missing_required_created_at_raises_validation_error(self):
        """Omitting required field 'created_at' must raise ValidationError."""
        data = _make_module_data()
        data.pop("created_at")

        with pytest.raises(ValidationError):
            ModuleResponse(**data)


# ---------------------------------------------------------------------------
# ModuleResponse — from_attributes (ORM model compatibility)
# ---------------------------------------------------------------------------


class TestModuleResponseFromAttributes:
    def test_model_validate_works_on_orm_like_object(self):
        """model_validate should read attributes from an ORM-style object."""

        class FakeModuleORM:
            id = 5
            name = "fft_noise"
            display_name = "FFT Noise"
            description = "Frequency analysis"
            enabled = True
            module_type = "analysis"
            analysis_task = "analyze_log_fft"
            frontend_route = "fft_noise"
            config_json = {}
            created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        schema = ModuleResponse.model_validate(FakeModuleORM())

        assert schema.id == 5
        assert schema.name == "fft_noise"
        assert schema.frontend_route == "fft_noise"
        assert schema.analysis_task == "analyze_log_fft"

    def test_model_validate_preserves_none_optional_fields(self):
        """Optional None fields remain None when read from ORM-like object."""

        class FakeOrm:
            id = 3
            name = "video"
            display_name = "DVR Video"
            description = None
            enabled = False
            module_type = "storage"
            analysis_task = None
            frontend_route = "video"
            config_json = {}
            created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        schema = ModuleResponse.model_validate(FakeOrm())

        assert schema.description is None
        assert schema.analysis_task is None
        assert schema.enabled is False

    def test_model_validate_preserves_config_json_dict(self):
        """config_json from ORM object is passed through unchanged."""

        class FakeOrm:
            id = 10
            name = "custom"
            display_name = "Custom"
            description = "desc"
            enabled = True
            module_type = "analysis"
            analysis_task = "analyze_log_custom"
            frontend_route = "custom"
            config_json = {"alpha": 0.9, "window": 256}
            created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        schema = ModuleResponse.model_validate(FakeOrm())
        assert schema.config_json == {"alpha": 0.9, "window": 256}


# ---------------------------------------------------------------------------
# ModuleUpdate — field validation
# ---------------------------------------------------------------------------


class TestModuleUpdateFields:
    def test_empty_payload_is_valid(self):
        """Empty payload (all fields omitted) is valid for a partial update."""
        schema = ModuleUpdate()
        assert schema.enabled is None
        assert schema.config_json is None

    def test_enabled_true(self):
        """enabled=True is accepted."""
        schema = ModuleUpdate(enabled=True)
        assert schema.enabled is True

    def test_enabled_false(self):
        """enabled=False is accepted."""
        schema = ModuleUpdate(enabled=False)
        assert schema.enabled is False

    def test_config_json_updated(self):
        """config_json dict is stored as provided."""
        cfg = {"threshold": 0.3}
        schema = ModuleUpdate(config_json=cfg)
        assert schema.config_json == cfg

    def test_config_json_empty_dict(self):
        """config_json={} is accepted."""
        schema = ModuleUpdate(config_json={})
        assert schema.config_json == {}

    def test_only_enabled_in_model_dump_exclude_unset(self):
        """model_dump(exclude_unset=True) only includes explicitly set fields."""
        schema = ModuleUpdate(enabled=False)
        dumped = schema.model_dump(exclude_unset=True)

        assert "enabled" in dumped
        assert "config_json" not in dumped
        assert dumped["enabled"] is False

    def test_only_config_json_in_model_dump_exclude_unset(self):
        """model_dump(exclude_unset=True) excludes fields not explicitly set."""
        schema = ModuleUpdate(config_json={"key": "val"})
        dumped = schema.model_dump(exclude_unset=True)

        assert "config_json" in dumped
        assert "enabled" not in dumped

    def test_both_fields_in_model_dump_when_set(self):
        """Both fields present in dump when both explicitly set."""
        schema = ModuleUpdate(enabled=True, config_json={"x": 1})
        dumped = schema.model_dump(exclude_unset=True)

        assert "enabled" in dumped
        assert "config_json" in dumped

    def test_invalid_enabled_type_raises_validation_error(self):
        """Non-bool/coercible value for enabled raises ValidationError."""
        with pytest.raises(ValidationError):
            ModuleUpdate(enabled="not-a-bool-and-not-coercible")


# ---------------------------------------------------------------------------
# ModuleListResponse — field validation
# ---------------------------------------------------------------------------


class TestModuleListResponseFields:
    def test_empty_list_is_valid(self):
        """items=[] and total=0 is a valid list response."""
        schema = ModuleListResponse(items=[], total=0)
        assert schema.items == []
        assert schema.total == 0

    def test_single_item(self):
        """A list with one ModuleResponse item is accepted."""
        item = ModuleResponse(**_make_module_data())
        schema = ModuleListResponse(items=[item], total=1)

        assert schema.total == 1
        assert len(schema.items) == 1
        assert schema.items[0].name == "step_response"

    def test_multiple_items(self):
        """Multiple ModuleResponse items are accepted."""
        item1 = ModuleResponse(**_make_module_data(id=1, name="step_response"))
        item2 = ModuleResponse(**_make_module_data(id=2, name="fft_noise", display_name="FFT Noise"))
        schema = ModuleListResponse(items=[item1, item2], total=2)

        assert schema.total == 2
        assert len(schema.items) == 2

    def test_total_count_independent_of_items_list(self):
        """total is an independent integer field, not derived from items length."""
        item = ModuleResponse(**_make_module_data())
        # total=100 but only 1 item - both are valid
        schema = ModuleListResponse(items=[item], total=100)
        assert schema.total == 100

    def test_missing_items_raises_validation_error(self):
        """Omitting required 'items' field raises ValidationError."""
        with pytest.raises(ValidationError):
            ModuleListResponse(total=0)

    def test_missing_total_raises_validation_error(self):
        """Omitting required 'total' field raises ValidationError."""
        with pytest.raises(ValidationError):
            ModuleListResponse(items=[])

    def test_items_contain_all_optional_none_fields(self):
        """Items with None optional fields are included in the list without error."""
        item = ModuleResponse(**_make_module_data(
            description=None,
            analysis_task=None,
            frontend_route=None,
        ))
        schema = ModuleListResponse(items=[item], total=1)
        assert schema.items[0].description is None
        assert schema.items[0].analysis_task is None
        assert schema.items[0].frontend_route is None