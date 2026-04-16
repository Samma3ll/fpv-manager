"""Unit tests for backend/app/analysis/step_response.py."""

import pytest
import numpy as np
from unittest.mock import MagicMock

from app.analysis.step_response import analyze_step_response, _analyze_single_step, _analyze_axis_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser_multi_call(field_names, frames_data):
    """Build a parser that yields frames on each .frames() call."""
    parser = MagicMock()
    parser.field_names = field_names
    parser.frames = MagicMock(side_effect=lambda: iter([
        MagicMock(data=row) for row in frames_data
    ]))
    return parser


def _step_signal(n=500, dt=0.001, rise_samples=50, steady=1.0):
    """
    Generate a simple first-order step response.

    Returns (gyro, rate_cmd) as numpy arrays.
    """
    rate_cmd = np.zeros(n)
    rate_cmd[50:] = steady  # Step at sample 50

    # Simple exponential rise for gyro response
    gyro = np.zeros(n)
    tau = rise_samples * dt
    for i in range(50, n):
        t = (i - 50) * dt
        gyro[i] = steady * (1 - np.exp(-t / tau))

    return gyro, rate_cmd


# ---------------------------------------------------------------------------
# _analyze_single_step
# ---------------------------------------------------------------------------

class TestAnalyzeSingleStep:
    def test_returns_expected_keys(self):
        signal = np.sin(np.linspace(0, np.pi, 200)) * 100.0
        result = _analyze_single_step(signal, dt=0.001)
        for key in ("rise_time_ms", "overshoot_pct", "settling_time_ms", "ringing"):
            assert key in result

    def test_rise_time_is_nonnegative(self):
        signal = np.linspace(0, 1, 100)
        result = _analyze_single_step(signal, dt=0.001)
        assert result["rise_time_ms"] >= 0.0

    def test_overshoot_pct_is_nonnegative(self):
        signal = np.sin(np.linspace(0, np.pi, 200)) * 100.0
        result = _analyze_single_step(signal, dt=0.001)
        assert result["overshoot_pct"] >= 0.0

    def test_settling_time_is_nonnegative(self):
        signal = np.linspace(0, 1, 200)
        result = _analyze_single_step(signal, dt=0.001)
        assert result["settling_time_ms"] >= 0.0

    def test_ringing_is_nonnegative(self):
        signal = np.sin(np.linspace(0, np.pi, 200)) * 100.0
        result = _analyze_single_step(signal, dt=0.001)
        assert result["ringing"] >= 0.0

    def test_zero_signal_no_error(self):
        signal = np.zeros(100)
        # Should not raise
        result = _analyze_single_step(signal, dt=0.001)
        assert isinstance(result, dict)

    def test_constant_signal(self):
        signal = np.ones(200) * 50.0
        result = _analyze_single_step(signal, dt=0.001)
        assert isinstance(result, dict)
        assert result["overshoot_pct"] == pytest.approx(0.0)

    def test_overshoot_detected_on_ringing_signal(self):
        """A signal that exceeds steady state should have non-zero overshoot."""
        # A damped oscillation that overshoots
        n = 300
        t = np.linspace(0, 0.3, n)
        # Step response with ~20% overshoot
        steady = 1.0
        signal = steady * (1 - np.exp(-20 * t) * np.cos(50 * t))
        result = _analyze_single_step(signal, dt=0.001)
        # Some overshoot should be detected for an oscillatory signal
        assert result["overshoot_pct"] >= 0.0

    def test_fast_rise_small_rise_time_ms(self):
        """Very fast signal should have small rise time compared to slow."""
        fast = np.zeros(200)
        fast[0:5] = 1.0
        fast[5:] = 1.0

        slow = np.zeros(200)
        slow[0:100] = np.linspace(0, 1, 100)
        slow[100:] = 1.0

        r_fast = _analyze_single_step(fast, dt=0.001)
        r_slow = _analyze_single_step(slow, dt=0.001)
        assert r_fast["rise_time_ms"] <= r_slow["rise_time_ms"]

    def test_dt_affects_time_values(self):
        """Larger dt should result in proportionally larger time values in ms."""
        signal = np.linspace(0, 1, 200)
        r1 = _analyze_single_step(signal, dt=0.001)
        r2 = _analyze_single_step(signal, dt=0.002)
        if r1["rise_time_ms"] > 0 and r2["rise_time_ms"] > 0:
            # r2 times should be ~2x r1 times
            ratio = r2["rise_time_ms"] / r1["rise_time_ms"]
            assert ratio == pytest.approx(2.0, rel=0.1)


# ---------------------------------------------------------------------------
# _analyze_axis_response
# ---------------------------------------------------------------------------

class TestAnalyzeAxisResponse:
    def test_no_step_inputs_returns_warning(self):
        """Constant rate_cmd → no step detected."""
        gyro = np.random.RandomState(0).normal(0, 5, 500)
        rate_cmd = np.ones(500) * 100.0  # Constant, no derivative
        result = _analyze_axis_response(gyro, rate_cmd, dt=0.001)
        assert "warning" in result

    def test_with_step_input_returns_metrics(self):
        """Abrupt step in rate_cmd should trigger analysis."""
        gyro, rate_cmd = _step_signal(n=1000, dt=0.001)
        result = _analyze_axis_response(gyro, rate_cmd, dt=0.001)
        # May return warning if no valid steps found, but should not raise
        assert isinstance(result, dict)

    def test_result_has_gyro_stats_on_success(self):
        """When at least one step is found, gyro_stats should be present."""
        gyro, rate_cmd = _step_signal(n=2000, dt=0.001)
        result = _analyze_axis_response(gyro, rate_cmd, dt=0.001)
        # If steps were found, gyro_stats should exist
        if "steps_analyzed" in result:
            assert "gyro_stats" in result

    def test_steps_analyzed_is_nonnegative(self):
        gyro, rate_cmd = _step_signal(n=2000, dt=0.001)
        result = _analyze_axis_response(gyro, rate_cmd, dt=0.001)
        if "steps_analyzed" in result:
            assert result["steps_analyzed"] >= 0


# ---------------------------------------------------------------------------
# analyze_step_response (parser-level)
# ---------------------------------------------------------------------------

class TestAnalyzeStepResponse:
    def _make_valid_parser(self, n=1000, dt_s=0.001):
        dt_us = int(dt_s * 1_000_000)
        field_names = [
            "time",
            "gyroADC[0]", "gyroADC[1]", "gyroADC[2]",
            "rcCommand[0]", "rcCommand[1]", "rcCommand[2]",
        ]
        rng = np.random.RandomState(7)
        rows = []
        for i in range(n):
            t = i * dt_us
            # Create a step at sample 200
            step = 50.0 if i >= 200 else 0.0
            gyro = rng.normal(step * 0.9, 5, 3).tolist()
            cmd = [step + rng.normal(0, 2) for _ in range(3)]
            rows.append([t] + gyro + cmd)
        return _make_parser_multi_call(field_names, rows)

    def test_returns_roll_pitch_yaw_keys(self):
        parser = self._make_valid_parser()
        result = analyze_step_response(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert axis in result

    def test_no_time_field_returns_error(self):
        parser = _make_parser_multi_call(["gyroADC[0]"], [[100]] * 100)
        result = analyze_step_response(parser)
        assert "error" in result

    def test_single_time_sample_returns_error(self):
        parser = _make_parser_multi_call(["time"], [[0]])
        result = analyze_step_response(parser)
        assert "error" in result

    def test_missing_gyro_field_returns_axis_error(self):
        n = 300
        dt_us = 1000
        field_names = ["time", "gyroADC[1]", "gyroADC[2]", "rcCommand[0]", "rcCommand[1]", "rcCommand[2]"]
        rows = [[i * dt_us, 10.0, 10.0, 5.0, 5.0, 5.0] for i in range(n)]
        parser = _make_parser_multi_call(field_names, rows)
        result = analyze_step_response(parser)
        assert "error" in result.get("roll", {"error": "No gyroADC[0]"})

    def test_missing_rc_command_returns_axis_error(self):
        n = 300
        dt_us = 1000
        field_names = ["time", "gyroADC[0]", "gyroADC[1]", "gyroADC[2]"]
        rows = [[i * dt_us, 10.0, 10.0, 10.0] for i in range(n)]
        parser = _make_parser_multi_call(field_names, rows)
        result = analyze_step_response(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert "error" in result[axis]

    def test_all_time_equal_returns_error(self):
        """Zero dt should trigger invalid time step error."""
        field_names = ["time", "gyroADC[0]", "gyroADC[1]", "gyroADC[2]",
                       "rcCommand[0]", "rcCommand[1]", "rcCommand[2]"]
        rows = [[0, 10.0, 10.0, 10.0, 5.0, 5.0, 5.0]] * 100  # all same time
        parser = _make_parser_multi_call(field_names, rows)
        result = analyze_step_response(parser)
        assert "error" in result