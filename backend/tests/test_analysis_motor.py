"""Unit tests for backend/app/analysis/motor_analysis.py."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from app.analysis.motor_analysis import (
    analyze_motor_output,
    _analyze_motor,
    _analyze_overall_motors,
    _find_motor_resonances,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser_with_motors(motor_arrays, extra_fields=None):
    """
    Build a mock parser that includes motor[0]..motor[n-1] fields.

    motor_arrays: list of 1-D arrays, one per motor.
    """
    n_motors = len(motor_arrays)
    n_samples = len(motor_arrays[0]) if motor_arrays else 0

    field_names = [f"motor[{i}]" for i in range(n_motors)]
    if extra_fields:
        field_names += extra_fields

    parser = MagicMock()
    parser.field_names = field_names

    def make_frames():
        for row_idx in range(n_samples):
            frame = MagicMock()
            frame.data = [motor_arrays[mi][row_idx] for mi in range(n_motors)]
            yield frame

    parser.frames = MagicMock(side_effect=make_frames)
    return parser


# ---------------------------------------------------------------------------
# _analyze_motor
# ---------------------------------------------------------------------------

class TestAnalyzeMotor:
    def test_all_nan_returns_error(self):
        motor_data = np.array([np.nan, np.nan, np.nan])
        result = _analyze_motor(motor_data, motor_idx=0)
        assert "error" in result

    def test_returns_required_keys(self):
        motor_data = np.linspace(1000, 1900, 200)
        result = _analyze_motor(motor_data, motor_idx=0)
        for key in ("avg_output", "min_output", "max_output", "output_range",
                    "rms_output", "output_std", "idle_estimate", "activity_level",
                    "throttle_changes"):
            assert key in result

    def test_output_range_is_max_minus_min(self):
        motor_data = np.array([1000.0, 1500.0, 2000.0])
        result = _analyze_motor(motor_data, motor_idx=1)
        assert result["output_range"] == pytest.approx(1000.0)

    def test_activity_level_between_0_and_1(self):
        motor_data = np.linspace(1000, 2000, 100)
        result = _analyze_motor(motor_data, motor_idx=0)
        assert 0.0 <= result["activity_level"] <= 1.0

    def test_constant_motor_output_zero_std(self):
        motor_data = np.full(100, 1500.0)
        result = _analyze_motor(motor_data, motor_idx=0)
        assert result["output_std"] == pytest.approx(0.0)

    def test_nan_values_filtered_out(self):
        motor_data = np.array([1000.0, np.nan, 2000.0, np.nan, 1500.0])
        result = _analyze_motor(motor_data, motor_idx=0)
        assert "error" not in result
        # mean of [1000, 2000, 1500] = 1500
        assert result["avg_output"] == pytest.approx(1500.0)

    def test_active_output_stats_present_when_active_data_exists(self):
        # Create data with clear idle and active regions
        idle = np.full(20, 1000.0)
        active = np.full(80, 1800.0)
        motor_data = np.concatenate([idle, active])
        result = _analyze_motor(motor_data, motor_idx=2)
        assert "active_output_stats" in result

    def test_minimum_viable_input(self):
        # Need at least 2 samples for derivative/percentile computation;
        # use 2 samples to confirm the function succeeds
        motor_data = np.array([1500.0, 1600.0])
        result = _analyze_motor(motor_data, motor_idx=0)
        assert "error" not in result
        assert result["avg_output"] == pytest.approx(1550.0)


# ---------------------------------------------------------------------------
# _analyze_overall_motors
# ---------------------------------------------------------------------------

class TestAnalyzeOverallMotors:
    def test_single_motor_returns_empty_dict(self):
        motor_data_list = [(0, np.array([1000.0, 1100.0, 1200.0]))]
        result = _analyze_overall_motors(motor_data_list)
        assert result == {}

    def test_two_motors_has_imbalance_pct(self):
        m0 = np.array([1000.0] * 100)
        m1 = np.array([1200.0] * 100)
        result = _analyze_overall_motors([(0, m0), (1, m1)])
        assert "imbalance_pct" in result
        assert result["imbalance_pct"] > 0

    def test_equal_motors_zero_imbalance(self):
        data = np.array([1500.0] * 100)
        result = _analyze_overall_motors([(0, data), (1, data), (2, data), (3, data)])
        assert result["imbalance_pct"] == pytest.approx(0.0, abs=1e-9)

    def test_four_motors_has_correlation(self):
        rng = np.random.default_rng(0)
        motors = [(i, rng.uniform(1000, 2000, 100)) for i in range(4)]
        result = _analyze_overall_motors(motors)
        assert "motor_correlation_mean" in result
        assert "motor_correlation_min" in result
        assert "motor_correlation_max" in result

    def test_two_motors_no_correlation_keys(self):
        m0 = np.linspace(1000, 2000, 100)
        m1 = np.linspace(1100, 1900, 100)
        result = _analyze_overall_motors([(0, m0), (1, m1)])
        assert "motor_correlation_mean" not in result

    def test_motor_deviations_present(self):
        m0 = np.full(100, 1000.0)
        m1 = np.full(100, 2000.0)
        result = _analyze_overall_motors([(0, m0), (1, m1)])
        assert "motor_deviations" in result
        assert len(result["motor_deviations"]) == 2

    def test_max_deviation_nonnegative(self):
        m0 = np.full(100, 1000.0)
        m1 = np.full(100, 1200.0)
        result = _analyze_overall_motors([(0, m0), (1, m1)])
        assert result["max_deviation"] >= 0.0

    def test_potential_resonance_peaks_is_list(self):
        m0 = np.random.default_rng(1).uniform(1000, 2000, 200)
        m1 = np.random.default_rng(2).uniform(1000, 2000, 200)
        result = _analyze_overall_motors([(0, m0), (1, m1)])
        assert isinstance(result.get("potential_resonance_peaks", []), list)

    def test_imbalance_zero_when_mean_is_zero(self):
        # If all motors have mean 0 (e.g., signed data with equal distribution)
        m0 = np.array([0.0] * 100)
        m1 = np.array([0.0] * 100)
        result = _analyze_overall_motors([(0, m0), (1, m1)])
        assert result["imbalance_pct"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _find_motor_resonances
# ---------------------------------------------------------------------------

class TestFindMotorResonances:
    def test_single_motor_returns_empty(self):
        motor_data_list = [(0, np.ones(100))]
        result = _find_motor_resonances(motor_data_list)
        assert result == []

    def test_short_motor_data_skipped(self):
        motor_data_list = [(0, np.ones(5)), (1, np.ones(5))]
        result = _find_motor_resonances(motor_data_list)
        assert isinstance(result, list)

    def test_returns_sorted_list(self):
        rng = np.random.default_rng(7)
        m0 = rng.uniform(0, 100, 200)
        m1 = rng.uniform(0, 100, 200)
        result = _find_motor_resonances([(0, m0), (1, m1)])
        assert result == sorted(result)

    def test_frequencies_in_valid_range(self):
        rng = np.random.default_rng(8)
        motors = [(i, rng.uniform(0, 100, 500)) for i in range(4)]
        result = _find_motor_resonances(motors, fs=8000)
        for freq in result:
            assert 10 <= freq <= 500


# ---------------------------------------------------------------------------
# analyze_motor_output
# ---------------------------------------------------------------------------

class TestAnalyzeMotorOutput:
    def test_no_motor_fields_returns_error(self):
        parser = MagicMock()
        parser.field_names = ["time", "gyroADC[0]"]
        result = analyze_motor_output(parser)
        assert "error" in result

    def test_single_motor_present(self):
        n = 100
        m0 = np.linspace(1000, 2000, n)
        parser = MagicMock()
        parser.field_names = ["motor[0]"]
        call_count = [0]

        def make_frames():
            for i in range(n):
                frame = MagicMock()
                frame.data = [m0[i]]
                yield frame

        parser.frames = MagicMock(side_effect=make_frames)
        result = analyze_motor_output(parser)
        assert "motors" in result
        assert "motor_0" in result["motors"]

    def test_four_motors_parsed_correctly(self):
        n = 100
        motors_data = [np.linspace(1000 + i * 100, 1900 + i * 100, n) for i in range(4)]
        field_names = ["motor[0]", "motor[1]", "motor[2]", "motor[3]"]
        parser = MagicMock()
        parser.field_names = field_names
        call_count = [0]

        def make_frames():
            for row_idx in range(n):
                frame = MagicMock()
                frame.data = [motors_data[mi][row_idx] for mi in range(4)]
                yield frame

        parser.frames = MagicMock(side_effect=make_frames)
        result = analyze_motor_output(parser)
        assert "motors" in result
        assert "overall" in result
        for i in range(4):
            assert f"motor_{i}" in result["motors"]

    def test_result_structure(self):
        n = 50
        m0 = np.ones(n) * 1500
        parser = MagicMock()
        parser.field_names = ["motor[0]"]

        def make_frames():
            for i in range(n):
                frame = MagicMock()
                frame.data = [m0[i]]
                yield frame

        parser.frames = MagicMock(side_effect=make_frames)
        result = analyze_motor_output(parser)
        assert isinstance(result, dict)
        assert "motors" in result

    def test_two_motors_produces_overall(self):
        n = 50
        field_names = ["motor[0]", "motor[1]"]
        parser = MagicMock()
        parser.field_names = field_names

        def make_frames():
            for i in range(n):
                frame = MagicMock()
                frame.data = [1500.0, 1600.0]
                yield frame

        parser.frames = MagicMock(side_effect=make_frames)
        result = analyze_motor_output(parser)
        assert "overall" in result
        assert "imbalance_pct" in result["overall"]