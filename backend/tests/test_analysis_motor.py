"""Unit tests for backend/app/analysis/motor_analysis.py."""

import pytest
import numpy as np
from unittest.mock import MagicMock

from app.analysis.motor_analysis import (
    analyze_motor_output,
    _analyze_motor,
    _analyze_overall_motors,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser_multi_call(field_names, frames_data):
    """Build a parser that yields fresh frames on each .frames() call."""
    parser = MagicMock()
    parser.field_names = field_names
    parser.frames = MagicMock(side_effect=lambda: iter([
        MagicMock(data=row) for row in frames_data
    ]))
    return parser


def _uniform_motor_data(n=500, value=1500.0):
    """Return a constant motor output array."""
    return np.ones(n) * value


# ---------------------------------------------------------------------------
# _analyze_motor
# ---------------------------------------------------------------------------

class TestAnalyzeMotor:
    def test_returns_expected_keys(self):
        data = np.random.RandomState(0).uniform(1000, 2000, 500)
        result = _analyze_motor(data, motor_idx=0)
        for key in ("avg_output", "min_output", "max_output", "output_range", "rms_output", "output_std", "idle_estimate", "activity_level", "throttle_changes"):
            assert key in result

    def test_all_nan_returns_error(self):
        data = np.array([np.nan, np.nan, np.nan])
        result = _analyze_motor(data, motor_idx=0)
        assert "error" in result

    def test_empty_array_returns_error(self):
        data = np.array([])
        result = _analyze_motor(data, motor_idx=0)
        assert "error" in result

    def test_avg_output_is_mean(self):
        data = np.array([1000.0, 2000.0, 3000.0])
        result = _analyze_motor(data, motor_idx=0)
        assert result["avg_output"] == pytest.approx(2000.0)

    def test_output_range_is_max_minus_min(self):
        data = np.array([1000.0, 1500.0, 2000.0])
        result = _analyze_motor(data, motor_idx=0)
        assert result["output_range"] == pytest.approx(1000.0)

    def test_activity_level_between_0_and_1(self):
        data = np.random.RandomState(1).uniform(1000, 2000, 500)
        result = _analyze_motor(data, motor_idx=0)
        assert 0.0 <= result["activity_level"] <= 1.0

    def test_constant_signal_zero_output_std(self):
        data = np.ones(200) * 1500.0
        result = _analyze_motor(data, motor_idx=0)
        assert result["output_std"] == pytest.approx(0.0, abs=1e-9)

    def test_nan_values_removed(self):
        data = np.array([1000.0, np.nan, 2000.0, np.nan, 1500.0])
        result = _analyze_motor(data, motor_idx=0)
        assert "error" not in result
        # Should use 3 valid values
        assert result["min_output"] == pytest.approx(1000.0)

    def test_active_output_stats_present_for_active_motor(self):
        # High-value data should trigger active output stats
        data = np.random.RandomState(0).uniform(1500, 2000, 300)
        result = _analyze_motor(data, motor_idx=0)
        # If there's active data, active_output_stats should be present
        if result.get("activity_level", 0) > 0:
            assert "active_output_stats" in result

    def test_two_values_minimum(self):
        # Single element causes np.diff to return empty → percentile error in production code.
        # Minimum working input requires at least 2 elements for np.percentile on diff.
        data = np.array([1500.0, 1500.0])
        result = _analyze_motor(data, motor_idx=0)
        assert "error" not in result
        assert result["avg_output"] == pytest.approx(1500.0)

    def test_throttle_changes_is_nonnegative_int(self):
        data = np.random.RandomState(2).uniform(1000, 2000, 300)
        result = _analyze_motor(data, motor_idx=0)
        assert result["throttle_changes"] >= 0
        assert isinstance(result["throttle_changes"], (int, np.integer))


# ---------------------------------------------------------------------------
# _analyze_overall_motors
# ---------------------------------------------------------------------------

class TestAnalyzeOverallMotors:
    def _make_balanced_motors(self, n=500, base=1500.0):
        """4 motors with identical outputs."""
        rng = np.random.RandomState(0)
        data = rng.normal(base, 50, n)
        return [(i, data.copy()) for i in range(4)]

    def _make_imbalanced_motors(self, n=500):
        """4 motors where motor 0 has much higher output."""
        rng = np.random.RandomState(1)
        motors = [
            (0, rng.normal(1800, 50, n)),  # High
            (1, rng.normal(1500, 50, n)),
            (2, rng.normal(1500, 50, n)),
            (3, rng.normal(1500, 50, n)),
        ]
        return motors

    def test_single_motor_returns_empty_dict(self):
        motors = [(0, np.ones(100) * 1500)]
        result = _analyze_overall_motors(motors)
        assert result == {}

    def test_returns_imbalance_pct_for_two_motors(self):
        motors = [
            (0, np.ones(200) * 1500.0),
            (1, np.ones(200) * 1500.0),
        ]
        result = _analyze_overall_motors(motors)
        assert "imbalance_pct" in result

    def test_zero_imbalance_for_identical_motors(self):
        motors = [
            (0, np.ones(200) * 1500.0),
            (1, np.ones(200) * 1500.0),
            (2, np.ones(200) * 1500.0),
            (3, np.ones(200) * 1500.0),
        ]
        result = _analyze_overall_motors(motors)
        assert result["imbalance_pct"] == pytest.approx(0.0)

    def test_high_imbalance_for_mismatched_motors(self):
        motors = self._make_imbalanced_motors()
        result = _analyze_overall_motors(motors)
        assert result["imbalance_pct"] > 0.0

    def test_four_motors_has_correlation(self):
        motors = self._make_balanced_motors()
        result = _analyze_overall_motors(motors)
        assert "motor_correlation_mean" in result
        assert "motor_correlation_min" in result
        assert "motor_correlation_max" in result

    def test_three_motors_no_correlation(self):
        rng = np.random.RandomState(0)
        motors = [(i, rng.normal(1500, 50, 200)) for i in range(3)]
        result = _analyze_overall_motors(motors)
        # Correlations only calculated for 4 motors
        assert "motor_correlation_mean" not in result

    def test_motor_deviations_length_matches_motor_count(self):
        motors = self._make_balanced_motors()
        result = _analyze_overall_motors(motors)
        assert len(result["motor_deviations"]) == len(motors)

    def test_balanced_deviations_near_zero(self):
        motors = [
            (i, np.ones(200) * 1500.0) for i in range(4)
        ]
        result = _analyze_overall_motors(motors)
        for dev in result["motor_deviations"]:
            assert abs(dev) < 1e-6

    def test_max_deviation_is_max_absolute(self):
        motors = [
            (0, np.ones(200) * 2000.0),
            (1, np.ones(200) * 1000.0),
            (2, np.ones(200) * 1500.0),
            (3, np.ones(200) * 1500.0),
        ]
        result = _analyze_overall_motors(motors)
        # Deviations from mean 1500: [500, -500, 0, 0] → max_deviation = 500
        assert result["max_deviation"] == pytest.approx(500.0, rel=0.01)

    def test_resonance_peaks_is_list(self):
        motors = self._make_balanced_motors()
        result = _analyze_overall_motors(motors)
        assert isinstance(result.get("potential_resonance_peaks", []), list)


# ---------------------------------------------------------------------------
# analyze_motor_output (parser-level)
# ---------------------------------------------------------------------------

class TestAnalyzeMotorOutput:
    def _make_valid_parser(self, n=300):
        """Parser with 4 motor fields."""
        field_names = ["motor[0]", "motor[1]", "motor[2]", "motor[3]"]
        rng = np.random.RandomState(42)
        rows = [rng.uniform(1000, 2000, 4).tolist() for _ in range(n)]
        return _make_parser_multi_call(field_names, rows)

    def test_returns_motors_and_overall_keys(self):
        parser = self._make_valid_parser()
        result = analyze_motor_output(parser)
        assert "motors" in result
        assert "overall" in result

    def test_four_motor_entries_present(self):
        parser = self._make_valid_parser()
        result = analyze_motor_output(parser)
        for m in ("motor_0", "motor_1", "motor_2", "motor_3"):
            assert m in result["motors"]

    def test_no_motor_fields_returns_error(self):
        parser = _make_parser_multi_call(["gyroADC[0]"], [[100]] * 100)
        result = analyze_motor_output(parser)
        assert "error" in result

    def test_overall_has_imbalance_pct(self):
        parser = self._make_valid_parser()
        result = analyze_motor_output(parser)
        assert "imbalance_pct" in result["overall"]

    def test_per_motor_stats_present(self):
        parser = self._make_valid_parser()
        result = analyze_motor_output(parser)
        motor0 = result["motors"]["motor_0"]
        assert "avg_output" in motor0
        assert "min_output" in motor0
        assert "max_output" in motor0