"""Unit tests for backend/app/analysis/step_response.py."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from app.analysis.step_response import (
    analyze_step_response,
    _analyze_axis_response,
    _analyze_single_step,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser(field_names, frame_rows_fn):
    """
    Build a mock parser.

    frame_rows_fn: callable returning an iterable of rows each time frames() is called.
    """
    parser = MagicMock()
    parser.field_names = field_names
    parser.frames = MagicMock(side_effect=lambda: iter(
        [type("F", (), {"data": row})() for row in frame_rows_fn()]
    ))
    return parser


def _make_full_parser(n=200, dt_us=1000):
    """Parser with time, gyroADC[0-2], rcCommand[0-2]."""
    field_names = [
        "time",
        "gyroADC[0]", "gyroADC[1]", "gyroADC[2]",
        "rcCommand[0]", "rcCommand[1]", "rcCommand[2]",
    ]

    def gen_rows():
        for i in range(n):
            time = i * dt_us
            gyro = [float(np.sin(2 * np.pi * i / 50) * 100)] * 3
            # Create a step: ramp up in first 30%, flat after
            if i < n * 0.3:
                rc = [float(i * 5)] * 3
            else:
                rc = [float(n * 0.3 * 5)] * 3
            yield [time] + gyro + rc

    return _make_parser(field_names, gen_rows)


# ---------------------------------------------------------------------------
# _analyze_single_step
# ---------------------------------------------------------------------------

class TestAnalyzeSingleStep:
    def test_returns_required_keys(self):
        # Simple ramp then flat signal
        n = 100
        step = np.concatenate([np.linspace(0, 1, 50), np.ones(50)])
        result = _analyze_single_step(step, dt=0.001)
        for key in ("rise_time_ms", "overshoot_pct", "settling_time_ms", "ringing"):
            assert key in result

    def test_overshoot_nonnegative(self):
        step = np.concatenate([np.linspace(0, 1.2, 40), np.ones(60)])
        result = _analyze_single_step(step, dt=0.001)
        assert result["overshoot_pct"] >= 0.0

    def test_no_overshoot_for_clean_step(self):
        # Perfect ramp to exact steady state
        n = 100
        signal = np.concatenate([np.linspace(0, 1, 50), np.ones(50)])
        result = _analyze_single_step(signal, dt=0.001)
        # Max should be 1.0, steady state ~1.0, so no overshoot
        assert result["overshoot_pct"] == pytest.approx(0.0, abs=1e-9)

    def test_rise_time_is_finite(self):
        step = np.concatenate([np.linspace(0, 1, 50), np.ones(50)])
        result = _analyze_single_step(step, dt=0.001)
        assert np.isfinite(result["rise_time_ms"])

    def test_settling_time_nonnegative(self):
        step = np.concatenate([np.linspace(0, 1, 50), np.ones(50)])
        result = _analyze_single_step(step, dt=0.001)
        assert result["settling_time_ms"] >= 0.0

    def test_ringing_nonnegative(self):
        step = np.concatenate([np.linspace(0, 1, 50), np.ones(50)])
        result = _analyze_single_step(step, dt=0.001)
        assert result["ringing"] >= 0.0

    def test_all_zeros_signal(self):
        # Zero signal: normalize_signal returns zeros, steady_state=0
        signal = np.zeros(100)
        result = _analyze_single_step(signal, dt=0.001)
        # Should run without error
        assert "rise_time_ms" in result

    def test_noisy_step_with_ringing(self):
        # Signal that overshoots and oscillates
        n = 200
        t = np.arange(n) * 0.001
        step = np.where(t < 0.05, t / 0.05, 1.0)
        # Add some oscillation after step
        oscillation = np.where(t >= 0.05, 0.3 * np.sin(2 * np.pi * 50 * t), 0.0)
        signal = step + oscillation
        result = _analyze_single_step(signal, dt=0.001)
        assert result["overshoot_pct"] >= 0.0


# ---------------------------------------------------------------------------
# _analyze_axis_response
# ---------------------------------------------------------------------------

class TestAnalyzeAxisResponse:
    def test_no_step_inputs_returns_warning(self):
        # Constant rate_cmd → no steps detected
        n = 200
        gyro_data = np.ones(n) * 50.0
        rate_cmd = np.ones(n) * 100.0  # Flat: no derivative
        result = _analyze_axis_response(gyro_data, rate_cmd, dt=0.001, axis="roll")
        assert "warning" in result

    def test_step_input_analyzed(self):
        # rate_cmd has a clear step
        n = 500
        dt = 0.001
        t = np.arange(n) * dt
        # Step at t=0.2s
        rate_cmd = np.where(t < 0.2, 0.0, 500.0)
        gyro_data = np.where(t < 0.2, 0.0, 400.0)
        result = _analyze_axis_response(gyro_data, rate_cmd, dt=dt, axis="roll")
        # Should produce step metrics or warning, not error
        assert "error" not in result

    def test_returns_gyro_stats_when_no_clear_steps(self):
        n = 200
        gyro_data = np.ones(n) * 50.0
        rate_cmd = np.ones(n) * 100.0
        result = _analyze_axis_response(gyro_data, rate_cmd, dt=0.001, axis="roll")
        # When no steps, returns warning with gyro stats or empty warning
        assert "warning" in result or "gyro_stats" in result


# ---------------------------------------------------------------------------
# analyze_step_response
# ---------------------------------------------------------------------------

class TestAnalyzeStepResponse:
    def test_no_time_data_returns_error(self):
        parser = MagicMock()
        parser.field_names = ["gyroADC[0]"]
        result = analyze_step_response(parser)
        assert "error" in result

    def test_single_time_sample_returns_error(self):
        field_names = ["time", "gyroADC[0]", "rcCommand[0]"]
        parser = _make_parser(field_names, lambda: [[1000, 0.0, 0.0]])
        result = analyze_step_response(parser)
        assert "error" in result

    def test_missing_gyro_per_axis_error(self):
        # Only time provided, no gyro or rc fields
        field_names = ["time"]
        rows = [[i * 1000] for i in range(100)]
        parser = _make_parser(field_names, lambda: rows)
        result = analyze_step_response(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert axis in result
            assert "error" in result[axis]

    def test_all_axes_present_in_result(self):
        parser = _make_full_parser(n=300)
        result = analyze_step_response(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert axis in result

    def test_returns_dict(self):
        parser = _make_full_parser(n=300)
        result = analyze_step_response(parser)
        assert isinstance(result, dict)

    def test_invalid_time_step_returns_error(self):
        # All times identical → dt = 0 → invalid
        field_names = ["time", "gyroADC[0]", "rcCommand[0]",
                       "gyroADC[1]", "rcCommand[1]",
                       "gyroADC[2]", "rcCommand[2]"]
        rows = [[1000, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]] * 100
        parser = _make_parser(field_names, lambda: rows)
        result = analyze_step_response(parser)
        assert "error" in result

    def test_missing_rccommand_produces_axis_error(self):
        # Has gyro but not rcCommand fields
        n = 100
        field_names = ["time", "gyroADC[0]", "gyroADC[1]", "gyroADC[2]"]

        def gen_rows():
            for i in range(n):
                yield [i * 1000, float(i), float(i), float(i)]

        parser = _make_parser(field_names, gen_rows)
        result = analyze_step_response(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert "error" in result.get(axis, {"error": "missing"})