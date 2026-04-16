"""Unit tests for backend/app/analysis/pid_error.py."""

import pytest
import numpy as np
from unittest.mock import MagicMock

from app.analysis.pid_error import analyze_pid_error, _analyze_axis_error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser(field_names, frames_data):
    """Build a minimal mock parser."""
    parser = MagicMock()
    parser.field_names = field_names
    frames = []
    for row in frames_data:
        frame = MagicMock()
        frame.data = row
        frames.append(frame)
    parser.frames = MagicMock(return_value=iter(frames))
    return parser


def _make_parser_multi_call(field_names, frames_data):
    """Build a parser that can be iterated multiple times."""
    parser = MagicMock()
    parser.field_names = field_names
    parser.frames = MagicMock(side_effect=lambda: iter([
        MagicMock(data=row) for row in frames_data
    ]))
    return parser


# ---------------------------------------------------------------------------
# _analyze_axis_error
# ---------------------------------------------------------------------------

class TestAnalyzeAxisError:
    def test_returns_expected_keys(self):
        error = np.array([1.0, 2.0, -1.0, 0.5, 3.0] * 20)
        result = _analyze_axis_error(error)
        for key in ("rms_error", "max_error", "mean_abs_error", "error_stats", "error_drift", "error_derivative_rms", "error_percentiles"):
            assert key in result

    def test_empty_error_returns_error_key(self):
        error = np.array([])
        result = _analyze_axis_error(error)
        assert "error" in result

    def test_all_nan_returns_error_key(self):
        error = np.array([np.nan, np.nan, np.nan])
        result = _analyze_axis_error(error)
        assert "error" in result

    def test_rms_error_is_positive(self):
        error = np.array([1.0, -2.0, 3.0, -4.0] * 10)
        result = _analyze_axis_error(error)
        assert result["rms_error"] > 0.0

    def test_zero_error_has_zero_rms(self):
        error = np.zeros(100)
        result = _analyze_axis_error(error)
        assert result["rms_error"] == pytest.approx(0.0)
        assert result["max_error"] == pytest.approx(0.0)

    def test_max_error_is_max_absolute_value(self):
        error = np.array([1.0, -5.0, 3.0])
        result = _analyze_axis_error(error)
        assert result["max_error"] == pytest.approx(5.0)

    def test_mean_abs_error_is_nonnegative(self):
        error = np.array([-3.0, 1.0, -2.0, 4.0] * 5)
        result = _analyze_axis_error(error)
        assert result["mean_abs_error"] >= 0.0

    def test_nan_values_ignored(self):
        error = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
        result = _analyze_axis_error(error)
        assert "error" not in result
        # Should use only the 3 valid values
        assert result["max_error"] == pytest.approx(5.0)

    def test_error_drift_on_increasing_error(self):
        # Error magnitude clearly increasing over time
        error = np.concatenate([np.ones(100) * i for i in range(1, 11)])
        result = _analyze_axis_error(error)
        # Positive drift means increasing error
        assert result["error_drift"] > 0.0

    def test_error_drift_on_decreasing_error(self):
        # Error magnitude clearly decreasing over time
        error = np.concatenate([np.ones(100) * (10 - i) for i in range(10)])
        result = _analyze_axis_error(error)
        # Negative drift means decreasing error
        assert result["error_drift"] < 0.0

    def test_constant_error_has_near_zero_drift(self):
        error = np.ones(1000) * 5.0
        result = _analyze_axis_error(error)
        assert abs(result["error_drift"]) < 0.01

    def test_error_percentiles_present(self):
        error = np.arange(100.0)
        result = _analyze_axis_error(error)
        percentiles = result["error_percentiles"]
        assert "p50" in percentiles
        assert "p75" in percentiles
        assert "p90" in percentiles
        assert "p99" in percentiles

    def test_percentiles_are_nondecreasing(self):
        error = np.random.RandomState(42).normal(0, 5, 500)
        result = _analyze_axis_error(error)
        p = result["error_percentiles"]
        assert p["p50"] <= p["p75"] <= p["p90"] <= p["p99"]

    def test_error_derivative_rms_is_nonnegative(self):
        error = np.sin(np.linspace(0, 10, 500))
        result = _analyze_axis_error(error)
        assert result["error_derivative_rms"] >= 0.0

    def test_error_stats_contains_expected_keys(self):
        error = np.array([1.0, 2.0, 3.0, 4.0] * 25)
        result = _analyze_axis_error(error)
        for key in ("mean", "std", "min", "max", "rms", "peak"):
            assert key in result["error_stats"]

    def test_single_element_error(self):
        error = np.array([7.0])
        result = _analyze_axis_error(error)
        assert "error" not in result
        assert result["max_error"] == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# analyze_pid_error (parser-level)
# ---------------------------------------------------------------------------

class TestAnalyzePidError:
    def _make_valid_parser(self, n=200):
        """
        Create a parser with setpoint[0..2] and gyroADC[0..2] fields.
        """
        field_names = [
            "setpoint[0]", "setpoint[1]", "setpoint[2]",
            "gyroADC[0]", "gyroADC[1]", "gyroADC[2]",
        ]
        rng = np.random.RandomState(0)
        rows = []
        for _ in range(n):
            setpoints = rng.normal(0, 50, 3).tolist()
            gyros = [s + rng.normal(0, 2) for s in setpoints]
            rows.append(setpoints + gyros)
        return _make_parser_multi_call(field_names, rows)

    def test_returns_dict_with_roll_pitch_yaw(self):
        parser = self._make_valid_parser()
        result = analyze_pid_error(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert axis in result

    def test_valid_data_no_error_key(self):
        parser = self._make_valid_parser()
        result = analyze_pid_error(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert "error" not in result[axis]

    def test_missing_gyro_field_returns_error(self):
        # Only setpoint fields, no gyroADC
        field_names = ["setpoint[0]", "setpoint[1]", "setpoint[2]"]
        rows = [[10, 20, 30]] * 50
        parser = _make_parser_multi_call(field_names, rows)
        result = analyze_pid_error(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert "error" in result[axis]

    def test_missing_setpoint_field_returns_error(self):
        field_names = ["gyroADC[0]", "gyroADC[1]", "gyroADC[2]"]
        rows = [[100, 200, 300]] * 50
        parser = _make_parser_multi_call(field_names, rows)
        result = analyze_pid_error(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert "error" in result[axis]

    def test_result_contains_rms_and_max_error(self):
        parser = self._make_valid_parser()
        result = analyze_pid_error(parser)
        assert "rms_error" in result["roll"]
        assert "max_error" in result["roll"]

    def test_zero_error_when_setpoint_equals_gyro(self):
        """When setpoint and gyro are identical, rms error should be 0."""
        field_names = [
            "setpoint[0]", "setpoint[1]", "setpoint[2]",
            "gyroADC[0]", "gyroADC[1]", "gyroADC[2]",
        ]
        rows = [[50.0, 60.0, 40.0, 50.0, 60.0, 40.0]] * 200
        parser = _make_parser_multi_call(field_names, rows)
        result = analyze_pid_error(parser)
        assert result["roll"]["rms_error"] == pytest.approx(0.0)
        assert result["pitch"]["rms_error"] == pytest.approx(0.0)