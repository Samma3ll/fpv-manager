"""Unit tests for sanitize_for_json in backend/app/workers/tasks.py."""

import math
import pytest

from app.workers.tasks import sanitize_for_json


class TestSanitizeForJson:
    # --- Float handling ---

    def test_nan_float_becomes_none(self):
        assert sanitize_for_json(float("nan")) is None

    def test_positive_inf_becomes_none(self):
        assert sanitize_for_json(float("inf")) is None

    def test_negative_inf_becomes_none(self):
        assert sanitize_for_json(float("-inf")) is None

    def test_normal_float_returned_unchanged(self):
        assert sanitize_for_json(3.14) == pytest.approx(3.14)

    def test_zero_float_returned_unchanged(self):
        assert sanitize_for_json(0.0) == pytest.approx(0.0)

    def test_negative_float_returned_unchanged(self):
        assert sanitize_for_json(-2.5) == pytest.approx(-2.5)

    # --- Non-float scalar handling ---

    def test_int_returned_unchanged(self):
        assert sanitize_for_json(42) == 42

    def test_string_returned_unchanged(self):
        assert sanitize_for_json("hello") == "hello"

    def test_none_returned_unchanged(self):
        assert sanitize_for_json(None) is None

    def test_bool_true_returned_unchanged(self):
        assert sanitize_for_json(True) is True

    def test_bool_false_returned_unchanged(self):
        assert sanitize_for_json(False) is False

    # --- Dict handling ---

    def test_dict_nan_values_sanitized(self):
        result = sanitize_for_json({"a": float("nan"), "b": 1.0})
        assert result["a"] is None
        assert result["b"] == pytest.approx(1.0)

    def test_dict_inf_values_sanitized(self):
        result = sanitize_for_json({"x": float("inf"), "y": float("-inf")})
        assert result["x"] is None
        assert result["y"] is None

    def test_dict_clean_values_unchanged(self):
        data = {"key": 42, "name": "test", "value": 3.14}
        result = sanitize_for_json(data)
        assert result == data

    def test_nested_dict_sanitized(self):
        data = {"outer": {"inner": float("nan"), "ok": 5.0}}
        result = sanitize_for_json(data)
        assert result["outer"]["inner"] is None
        assert result["outer"]["ok"] == pytest.approx(5.0)

    def test_deeply_nested_dict(self):
        data = {"a": {"b": {"c": float("inf")}}}
        result = sanitize_for_json(data)
        assert result["a"]["b"]["c"] is None

    # --- List handling ---

    def test_list_with_nan_sanitized(self):
        result = sanitize_for_json([1.0, float("nan"), 3.0])
        assert result[0] == pytest.approx(1.0)
        assert result[1] is None
        assert result[2] == pytest.approx(3.0)

    def test_list_clean_unchanged(self):
        data = [1, 2, 3, "hello"]
        result = sanitize_for_json(data)
        assert result == data

    def test_empty_list_returns_empty_list(self):
        assert sanitize_for_json([]) == []

    def test_nested_list(self):
        data = [[float("nan"), 1.0], [2.0, float("inf")]]
        result = sanitize_for_json(data)
        assert result[0][0] is None
        assert result[0][1] == pytest.approx(1.0)
        assert result[1][1] is None

    # --- Tuple handling ---

    def test_tuple_converted_to_list(self):
        result = sanitize_for_json((1.0, float("nan"), 3.0))
        assert isinstance(result, list)
        assert result[1] is None

    def test_tuple_values_sanitized(self):
        result = sanitize_for_json((float("inf"), 2.5))
        assert result[0] is None
        assert result[1] == pytest.approx(2.5)

    # --- Mixed nested structures ---

    def test_dict_with_list_of_floats(self):
        data = {"freqs": [10.0, float("nan"), 30.0]}
        result = sanitize_for_json(data)
        assert result["freqs"][1] is None

    def test_list_of_dicts_with_nan(self):
        data = [
            {"frequency_hz": 100.0, "power_db": float("nan")},
            {"frequency_hz": 200.0, "power_db": -60.0},
        ]
        result = sanitize_for_json(data)
        assert result[0]["power_db"] is None
        assert result[1]["power_db"] == pytest.approx(-60.0)

    def test_typical_analysis_result_sanitized(self):
        """Regression: simulate an analysis result dict that may contain NaN."""
        data = {
            "roll": {
                "rms_error": float("nan"),
                "max_error": 15.0,
                "error_percentiles": {"p50": 3.0, "p99": float("inf")},
            }
        }
        result = sanitize_for_json(data)
        assert result["roll"]["rms_error"] is None
        assert result["roll"]["max_error"] == pytest.approx(15.0)
        assert result["roll"]["error_percentiles"]["p99"] is None

    def test_empty_dict_returns_empty_dict(self):
        assert sanitize_for_json({}) == {}

    def test_returns_new_dict_not_same_object(self):
        original = {"a": 1.0}
        result = sanitize_for_json(original)
        assert result is not original

    def test_math_nan_inf_check_consistency(self):
        # Ensure our test values are actually NaN/Inf
        val_nan = float("nan")
        val_inf = float("inf")
        assert math.isnan(val_nan)
        assert math.isinf(val_inf)
        assert sanitize_for_json(val_nan) is None
        assert sanitize_for_json(val_inf) is None