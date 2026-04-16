"""Unit tests for the sanitize_for_json helper in backend/app/workers/tasks.py."""

import math
import pytest

from app.workers.tasks import sanitize_for_json


# ---------------------------------------------------------------------------
# Primitive values
# ---------------------------------------------------------------------------

class TestSanitizeScalars:
    def test_normal_float_unchanged(self):
        assert sanitize_for_json(3.14) == pytest.approx(3.14)

    def test_zero_float_unchanged(self):
        assert sanitize_for_json(0.0) == pytest.approx(0.0)

    def test_negative_float_unchanged(self):
        assert sanitize_for_json(-1.5) == pytest.approx(-1.5)

    def test_nan_becomes_none(self):
        assert sanitize_for_json(float("nan")) is None

    def test_positive_inf_becomes_none(self):
        assert sanitize_for_json(float("inf")) is None

    def test_negative_inf_becomes_none(self):
        assert sanitize_for_json(float("-inf")) is None

    def test_integer_unchanged(self):
        assert sanitize_for_json(42) == 42

    def test_string_unchanged(self):
        assert sanitize_for_json("hello") == "hello"

    def test_none_unchanged(self):
        assert sanitize_for_json(None) is None

    def test_bool_unchanged(self):
        assert sanitize_for_json(True) is True
        assert sanitize_for_json(False) is False


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

class TestSanitizeList:
    def test_clean_list_unchanged(self):
        assert sanitize_for_json([1.0, 2.0, 3.0]) == [1.0, 2.0, 3.0]

    def test_nan_in_list_becomes_none(self):
        result = sanitize_for_json([1.0, float("nan"), 3.0])
        assert result == [1.0, None, 3.0]

    def test_inf_in_list_becomes_none(self):
        result = sanitize_for_json([float("inf"), 2.0])
        assert result == [None, 2.0]

    def test_tuple_treated_as_list(self):
        result = sanitize_for_json((1.0, float("nan")))
        assert result == [1.0, None]

    def test_nested_list(self):
        result = sanitize_for_json([[1.0, float("nan")], [float("inf"), 4.0]])
        assert result == [[1.0, None], [None, 4.0]]

    def test_empty_list(self):
        assert sanitize_for_json([]) == []

    def test_list_of_mixed_types(self):
        result = sanitize_for_json([1, "text", None, float("nan"), 3.14])
        assert result == [1, "text", None, None, 3.14]


class TestSanitizeDict:
    def test_clean_dict_unchanged(self):
        d = {"a": 1.0, "b": "ok", "c": 42}
        assert sanitize_for_json(d) == d

    def test_nan_value_becomes_none(self):
        d = {"x": float("nan"), "y": 2.0}
        result = sanitize_for_json(d)
        assert result == {"x": None, "y": 2.0}

    def test_inf_value_becomes_none(self):
        d = {"score": float("inf")}
        result = sanitize_for_json(d)
        assert result == {"score": None}

    def test_nested_dict(self):
        d = {"outer": {"inner": float("nan")}}
        result = sanitize_for_json(d)
        assert result == {"outer": {"inner": None}}

    def test_dict_with_list_values(self):
        d = {"values": [1.0, float("nan"), 3.0]}
        result = sanitize_for_json(d)
        assert result == {"values": [1.0, None, 3.0]}

    def test_empty_dict(self):
        assert sanitize_for_json({}) == {}

    def test_keys_preserved(self):
        d = {"nan_val": float("nan")}
        result = sanitize_for_json(d)
        assert "nan_val" in result


# ---------------------------------------------------------------------------
# Deeply nested structures (realistic analysis output)
# ---------------------------------------------------------------------------

class TestSanitizeNestedStructures:
    def test_typical_analysis_result(self):
        data = {
            "roll": {
                "rms_error": 2.5,
                "max_error": float("nan"),
                "error_drift": 0.01,
                "error_percentiles": {
                    "p50": 1.2,
                    "p99": float("inf"),
                },
            },
            "pitch": {
                "rms_error": 3.1,
                "peaks": [
                    {"frequency_hz": 100.0, "power": float("nan")},
                    {"frequency_hz": 200.0, "power": 0.5},
                ],
            },
        }
        result = sanitize_for_json(data)
        assert result["roll"]["max_error"] is None
        assert result["roll"]["error_percentiles"]["p99"] is None
        assert result["pitch"]["peaks"][0]["power"] is None
        assert result["pitch"]["peaks"][1]["power"] == pytest.approx(0.5)

    def test_all_special_floats_in_deeply_nested_list(self):
        data = {"levels": [[float("nan"), float("inf"), float("-inf"), 1.0]]}
        result = sanitize_for_json(data)
        assert result["levels"][0] == [None, None, None, 1.0]

    def test_output_has_no_nan_values(self):
        """After sanitization, no NaN values should remain at any level."""
        data = {
            "a": float("nan"),
            "b": [1.0, float("nan"), {"c": float("nan")}],
        }
        result = sanitize_for_json(data)

        def _has_nan(obj):
            if isinstance(obj, float) and math.isnan(obj):
                return True
            if isinstance(obj, dict):
                return any(_has_nan(v) for v in obj.values())
            if isinstance(obj, list):
                return any(_has_nan(v) for v in obj)
            return False

        assert not _has_nan(result)

    def test_output_has_no_inf_values(self):
        """After sanitization, no Inf values should remain at any level."""
        data = {"scores": [float("inf"), float("-inf"), 100.0]}
        result = sanitize_for_json(data)

        def _has_inf(obj):
            if isinstance(obj, float) and math.isinf(obj):
                return True
            if isinstance(obj, dict):
                return any(_has_inf(v) for v in obj.values())
            if isinstance(obj, list):
                return any(_has_inf(v) for v in obj)
            return False

        assert not _has_inf(result)