"""Unit tests for backend/app/analysis/pid_error.py."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from app.analysis.pid_error import (
    analyze_pid_error,
    _analyze_axis_error,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser_with_setpoint_gyro(setpoints, gyros, n_axes=3):
    """
    Build a mock parser that has setpoint[0..n_axes-1] and gyroADC[0..n_axes-1].

    setpoints and gyros are lists of 1-D arrays, one per axis.
    """
    n_samples = len(setpoints[0]) if setpoints else 0
    field_names = []
    for i in range(n_axes):
        field_names.append(f"setpoint[{i}]")
        field_names.append(f"gyroADC[{i}]")

    parser = MagicMock()
    parser.field_names = field_names

    def make_frames():
        for row_idx in range(n_samples):
            frame = MagicMock()
            row = []
            for i in range(n_axes):
                row.append(setpoints[i][row_idx])
                row.append(gyros[i][row_idx])
            frame.data = row
            yield frame

    parser.frames = MagicMock(side_effect=make_frames)
    return parser


# ---------------------------------------------------------------------------
# _analyze_axis_error
# ---------------------------------------------------------------------------

class TestAnalyzeAxisError:
    def test_empty_array_returns_error(self):
        error = np.array([])
        result = _analyze_axis_error(error)
        assert "error" in result
        assert result["error"] == "No error data"

    def test_all_nan_returns_error(self):
        error = np.array([np.nan, np.nan, np.nan])
        result = _analyze_axis_error(error)
        assert "error" in result
        assert result["error"] == "No valid error data"

    def test_returns_required_keys(self):
        error = np.array([1.0, -2.0, 3.0, -1.0, 0.5])
        result = _analyze_axis_error(error)
        for key in ("rms_error", "max_error", "mean_abs_error", "error_stats",
                    "error_drift", "error_derivative_rms", "error_percentiles"):
            assert key in result

    def test_zero_error_gives_zero_metrics(self):
        error = np.zeros(100)
        result = _analyze_axis_error(error)
        assert result["rms_error"] == pytest.approx(0.0)
        assert result["max_error"] == pytest.approx(0.0)
        assert result["mean_abs_error"] == pytest.approx(0.0)

    def test_rms_error_correct(self):
        error = np.array([3.0, 4.0])  # RMS = sqrt((9+16)/2) = sqrt(12.5)
        result = _analyze_axis_error(error)
        expected_rms = np.sqrt(12.5)
        assert result["rms_error"] == pytest.approx(expected_rms)

    def test_max_error_is_max_abs(self):
        error = np.array([1.0, -5.0, 3.0])
        result = _analyze_axis_error(error)
        assert result["max_error"] == pytest.approx(5.0)

    def test_mean_abs_error(self):
        error = np.array([2.0, -2.0, 4.0, -4.0])
        result = _analyze_axis_error(error)
        assert result["mean_abs_error"] == pytest.approx(3.0)

    def test_percentiles_keys_present(self):
        error = np.random.default_rng(42).standard_normal(200)
        result = _analyze_axis_error(error)
        for key in ("p50", "p75", "p90", "p99"):
            assert key in result["error_percentiles"]

    def test_percentiles_sorted(self):
        error = np.random.default_rng(42).standard_normal(200)
        result = _analyze_axis_error(error)
        perc = result["error_percentiles"]
        assert perc["p50"] <= perc["p75"] <= perc["p90"] <= perc["p99"]

    def test_drift_zero_for_constant_error(self):
        # Constant error should produce near-zero drift
        error = np.full(100, 5.0)
        result = _analyze_axis_error(error)
        assert abs(result["error_drift"]) == pytest.approx(0.0, abs=1e-10)

    def test_positive_drift_detected(self):
        # Linearly increasing error magnitude
        error = np.linspace(0, 10, 200)
        result = _analyze_axis_error(error)
        assert result["error_drift"] > 0

    def test_negative_drift_detected(self):
        # Linearly decreasing error magnitude
        error = np.linspace(10, 0, 200)
        result = _analyze_axis_error(error)
        assert result["error_drift"] < 0

    def test_derivative_rms_zero_for_constant_signal(self):
        error = np.full(50, 3.0)
        result = _analyze_axis_error(error)
        assert result["error_derivative_rms"] == pytest.approx(0.0)

    def test_nans_are_filtered(self):
        error = np.array([1.0, np.nan, 2.0, np.nan, 3.0])
        result = _analyze_axis_error(error)
        assert "error" not in result
        # Mean of [1, 2, 3] = 2, mean abs = 2
        assert result["mean_abs_error"] == pytest.approx(2.0)

    def test_single_sample(self):
        error = np.array([7.0])
        result = _analyze_axis_error(error)
        assert "error" not in result
        assert result["rms_error"] == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# analyze_pid_error
# ---------------------------------------------------------------------------

class TestAnalyzePidError:
    def test_missing_setpoint_returns_per_axis_error(self):
        # Only gyro fields available, no setpoint
        parser = MagicMock()
        parser.field_names = ["gyroADC[0]", "gyroADC[1]", "gyroADC[2]"]
        result = analyze_pid_error(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert "error" in result[axis]

    def test_missing_gyro_returns_per_axis_error(self):
        parser = MagicMock()
        parser.field_names = ["setpoint[0]", "setpoint[1]", "setpoint[2]"]
        result = analyze_pid_error(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert "error" in result[axis]

    def test_all_axes_analyzed_with_full_data(self):
        n = 100
        setpoints = [np.zeros(n), np.zeros(n), np.zeros(n)]
        gyros = [np.ones(n) * 2, np.ones(n) * 3, np.ones(n) * 1]
        parser = _make_parser_with_setpoint_gyro(setpoints, gyros)
        result = analyze_pid_error(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert axis in result
            assert "error" not in result[axis]

    def test_returns_roll_pitch_yaw_keys(self):
        n = 50
        setpoints = [np.ones(n)] * 3
        gyros = [np.zeros(n)] * 3
        parser = _make_parser_with_setpoint_gyro(setpoints, gyros)
        result = analyze_pid_error(parser)
        assert set(result.keys()) == {"roll", "pitch", "yaw"}

    def test_error_is_setpoint_minus_gyro(self):
        # setpoint=10, gyro=3 → error=7 for each sample
        n = 100
        setpoints = [np.full(n, 10.0)] * 3
        gyros = [np.full(n, 3.0)] * 3
        parser = _make_parser_with_setpoint_gyro(setpoints, gyros)
        result = analyze_pid_error(parser)
        assert result["roll"]["rms_error"] == pytest.approx(7.0)
        assert result["roll"]["max_error"] == pytest.approx(7.0)

    def test_different_length_arrays_handled(self):
        # If data has mismatched lengths, truncates to min_len
        n = 100
        setpoints = [np.ones(n) * 5] * 3
        gyros = [np.ones(n) * 2] * 3
        parser = _make_parser_with_setpoint_gyro(setpoints, gyros)
        result = analyze_pid_error(parser)
        # Should succeed without error
        for axis in ("roll", "pitch", "yaw"):
            assert "error" not in result[axis]