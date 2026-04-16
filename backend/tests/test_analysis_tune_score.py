"""Unit tests for backend/app/analysis/tune_score.py."""

import pytest
from app.analysis.tune_score import (
    score_tune_quality,
    _score_step_response,
    _score_fft_noise,
    _score_pid_error,
    _get_motor_penalty,
)


# ---------------------------------------------------------------------------
# _score_step_response
# ---------------------------------------------------------------------------

class TestScoreStepResponse:
    def test_perfect_data_returns_high_score(self):
        data = {
            "rise_time_ms": 100.0,  # ideal 50-200ms
            "overshoot_pct": 0.0,
            "settling_time_ms": 200.0,  # < 500ms
            "ringing": 0.0,
        }
        score = _score_step_response(data)
        assert score > 90.0

    def test_error_key_returns_neutral_50(self):
        data = {"error": "Missing data"}
        score = _score_step_response(data)
        assert score == pytest.approx(50.0)

    def test_zero_rise_time_penalizes(self):
        no_penalty = _score_step_response({"rise_time_ms": 100.0})
        with_penalty = _score_step_response({"rise_time_ms": 0.0})
        assert with_penalty < no_penalty

    def test_slow_rise_time_penalizes(self):
        # rise_time > 200ms is penalized
        good = _score_step_response({"rise_time_ms": 150.0})
        slow = _score_step_response({"rise_time_ms": 500.0})
        assert slow < good

    def test_rise_time_in_ideal_range_no_penalty(self):
        score_at_50 = _score_step_response({"rise_time_ms": 50.0})
        score_at_100 = _score_step_response({"rise_time_ms": 100.0})
        score_at_200 = _score_step_response({"rise_time_ms": 200.0})
        # All in ideal range; only other fields matter (all 0)
        assert score_at_50 == pytest.approx(score_at_100) == pytest.approx(score_at_200)

    def test_high_overshoot_penalizes(self):
        low = _score_step_response({"overshoot_pct": 2.0})
        high = _score_step_response({"overshoot_pct": 60.0})
        assert high < low

    def test_overshoot_penalty_capped_at_30(self):
        # 60% overshoot → penalty = min(30, 60/2) = 30
        score = _score_step_response({"overshoot_pct": 60.0, "rise_time_ms": 100.0})
        # Perfect - 30 overshoot penalty = 70
        assert score == pytest.approx(70.0)

    def test_slow_settling_penalizes(self):
        good = _score_step_response({"settling_time_ms": 300.0})
        slow = _score_step_response({"settling_time_ms": 1500.0})
        assert slow < good

    def test_settling_below_500ms_no_penalty(self):
        score = _score_step_response({"settling_time_ms": 400.0, "rise_time_ms": 100.0})
        assert score == pytest.approx(100.0)

    def test_ringing_penalizes(self):
        none = _score_step_response({"ringing": 0.0})
        many = _score_step_response({"ringing": 5.0})
        assert many < none

    def test_ringing_penalty_capped_at_15(self):
        # ringing=3 → penalty = min(15, 3*5) = 15
        score = _score_step_response({"ringing": 10.0, "rise_time_ms": 100.0})
        # Perfect - 15 ringing penalty = 85
        assert score == pytest.approx(85.0)

    def test_score_clamped_to_0_100(self):
        # Worst possible data
        data = {
            "rise_time_ms": 1000.0,
            "overshoot_pct": 100.0,
            "settling_time_ms": 5000.0,
            "ringing": 100.0,
        }
        score = _score_step_response(data)
        assert 0.0 <= score <= 100.0

    def test_empty_dict_penalizes_for_zero_rise_time(self):
        # rise_time defaults to 0, which is < 50ms → penalty = (50-0)/50 * 10 = 10
        score = _score_step_response({})
        assert score == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# _score_fft_noise
# ---------------------------------------------------------------------------

class TestScoreFftNoise:
    def test_error_key_returns_neutral_50(self):
        score = _score_fft_noise({"error": "No data"})
        assert score == pytest.approx(50.0)

    def test_no_peaks_gives_perfect_score(self):
        score = _score_fft_noise({"peaks": [], "noise_floor": 0.0})
        assert score == pytest.approx(100.0)

    def test_peaks_below_minus60db_not_penalized(self):
        # Peaks below -60dB produce no penalty (formula gives non-positive value)
        score = _score_fft_noise({
            "peaks": [{"frequency_hz": 100.0, "power": 0.0001, "power_db": -80.0}]
        })
        assert score == pytest.approx(100.0)

    def test_no_peaks_scores_100(self):
        score_no_peaks = _score_fft_noise({"peaks": []})
        assert score_no_peaks == pytest.approx(100.0)

    def test_peaks_penalty_capped(self):
        # Many very loud peaks should be capped at 30
        peaks = [
            {"frequency_hz": float(f), "power": 100.0, "power_db": 20.0}
            for f in range(100, 600, 100)
        ]
        score = _score_fft_noise({"peaks": peaks})
        assert score >= 0.0
        assert score <= 100.0

    def test_high_noise_floor_penalizes(self):
        clean = _score_fft_noise({"noise_floor": 0.0})
        noisy = _score_fft_noise({"noise_floor": 0.5})
        assert noisy < clean

    def test_high_frequency_energy_ratio_penalizes(self):
        # high_energy >> low_energy should lower score
        bad = _score_fft_noise({
            "energy_bands": {"5_50_hz": 1.0, "250_500_hz": 10.0}
        })
        good = _score_fft_noise({
            "energy_bands": {"5_50_hz": 10.0, "250_500_hz": 0.1}
        })
        assert bad < good

    def test_score_clamped_to_0_100(self):
        noisy = _score_fft_noise({
            "peaks": [{"frequency_hz": 100.0, "power": 1000.0, "power_db": 30.0}] * 10,
            "noise_floor": 10.0,
            "energy_bands": {"5_50_hz": 1.0, "250_500_hz": 100.0},
        })
        assert 0.0 <= noisy <= 100.0

    def test_empty_dict_returns_100(self):
        score = _score_fft_noise({})
        assert score == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# _score_pid_error
# ---------------------------------------------------------------------------

class TestScorePidError:
    def test_error_key_returns_neutral_50(self):
        score = _score_pid_error({"error": "Missing data"})
        assert score == pytest.approx(50.0)

    def test_low_rms_no_penalty(self):
        score = _score_pid_error({"rms_error": 1.0})
        assert score == pytest.approx(100.0)

    def test_high_rms_penalizes(self):
        low = _score_pid_error({"rms_error": 2.0})
        high = _score_pid_error({"rms_error": 50.0})
        assert high < low

    def test_rms_penalty_capped_at_30(self):
        # rms=65 → penalty = min(30, (65-5)/2) = 30
        score = _score_pid_error({"rms_error": 65.0})
        assert score == pytest.approx(70.0)

    def test_low_max_error_no_penalty(self):
        score = _score_pid_error({"max_error": 10.0})
        assert score == pytest.approx(100.0)

    def test_high_max_error_penalizes(self):
        low = _score_pid_error({"max_error": 15.0})
        high = _score_pid_error({"max_error": 100.0})
        assert high < low

    def test_max_error_penalty_capped_at_20(self):
        # max_error=120 → penalty = min(20, (120-20)/5) = 20
        score = _score_pid_error({"max_error": 120.0})
        assert score == pytest.approx(80.0)

    def test_small_drift_no_penalty(self):
        score_pos = _score_pid_error({"error_drift": 0.05})
        score_neg = _score_pid_error({"error_drift": -0.05})
        assert score_pos == pytest.approx(100.0)
        assert score_neg == pytest.approx(100.0)

    def test_large_drift_penalizes(self):
        no_drift = _score_pid_error({"error_drift": 0.0})
        with_drift = _score_pid_error({"error_drift": 1.0})
        assert with_drift < no_drift

    def test_score_clamped_to_0_100(self):
        score = _score_pid_error({
            "rms_error": 1000.0,
            "max_error": 1000.0,
            "error_drift": 100.0,
        })
        assert 0.0 <= score <= 100.0

    def test_empty_dict_perfect_score(self):
        score = _score_pid_error({})
        assert score == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# _get_motor_penalty
# ---------------------------------------------------------------------------

class TestGetMotorPenalty:
    def test_low_imbalance_no_penalty(self):
        analysis = {"overall": {"imbalance_pct": 3.0}}
        penalty = _get_motor_penalty(analysis)
        assert penalty == pytest.approx(0.0)

    def test_exactly_5_pct_no_penalty(self):
        analysis = {"overall": {"imbalance_pct": 5.0}}
        penalty = _get_motor_penalty(analysis)
        assert penalty == pytest.approx(0.0)

    def test_above_20_pct_max_penalty(self):
        analysis = {"overall": {"imbalance_pct": 25.0}}
        penalty = _get_motor_penalty(analysis)
        assert penalty == pytest.approx(0.2)

    def test_mid_imbalance_partial_penalty(self):
        # imbalance=10 → (10-5)/75 * 0.2
        expected = (10 - 5) / 75 * 0.2
        analysis = {"overall": {"imbalance_pct": 10.0}}
        penalty = _get_motor_penalty(analysis)
        assert penalty == pytest.approx(expected)

    def test_missing_overall_key_returns_zero(self):
        penalty = _get_motor_penalty({})
        assert penalty == pytest.approx(0.0)

    def test_missing_imbalance_key_returns_zero(self):
        penalty = _get_motor_penalty({"overall": {}})
        assert penalty == pytest.approx(0.0)

    def test_penalty_between_0_and_0_2(self):
        for imbalance in [0, 5, 10, 15, 20, 25, 100]:
            analysis = {"overall": {"imbalance_pct": imbalance}}
            p = _get_motor_penalty(analysis)
            assert 0.0 <= p <= 0.2


# ---------------------------------------------------------------------------
# score_tune_quality
# ---------------------------------------------------------------------------

class TestScoreTuneQuality:
    def _make_good_step_response(self):
        axis = {"rise_time_ms": 100.0, "overshoot_pct": 2.0, "settling_time_ms": 200.0, "ringing": 0.0}
        return {"roll": axis, "pitch": axis, "yaw": axis}

    def _make_good_fft(self):
        axis = {"peaks": [], "noise_floor": 0.0}
        return {"roll": axis, "pitch": axis, "yaw": axis}

    def _make_good_pid_error(self):
        axis = {"rms_error": 1.0, "max_error": 5.0, "error_drift": 0.0}
        return {"roll": axis, "pitch": axis, "yaw": axis}

    def _make_balanced_motors(self):
        return {"overall": {"imbalance_pct": 0.0}}

    def test_result_has_expected_keys(self):
        result = score_tune_quality(
            self._make_good_step_response(),
            self._make_good_fft(),
            self._make_good_pid_error(),
            self._make_balanced_motors(),
        )
        for key in ("roll_score", "pitch_score", "yaw_score", "overall_score", "details"):
            assert key in result

    def test_good_tune_high_score(self):
        result = score_tune_quality(
            self._make_good_step_response(),
            self._make_good_fft(),
            self._make_good_pid_error(),
            self._make_balanced_motors(),
        )
        assert result["overall_score"] > 80.0

    def test_overall_score_clamped_to_0_100(self):
        # Worst-case inputs
        bad_step = {"roll": {"error": "x"}, "pitch": {"error": "x"}, "yaw": {"error": "x"}}
        bad_fft = {"roll": {"error": "x"}, "pitch": {"error": "x"}, "yaw": {"error": "x"}}
        bad_pid = {
            "roll": {"rms_error": 1000.0, "max_error": 1000.0, "error_drift": 100.0},
            "pitch": {"rms_error": 1000.0, "max_error": 1000.0, "error_drift": 100.0},
            "yaw": {"rms_error": 1000.0, "max_error": 1000.0, "error_drift": 100.0},
        }
        result = score_tune_quality(bad_step, bad_fft, bad_pid, {"overall": {"imbalance_pct": 100.0}})
        assert 0.0 <= result["overall_score"] <= 100.0

    def test_motor_imbalance_reduces_overall_score(self):
        balanced = score_tune_quality(
            self._make_good_step_response(),
            self._make_good_fft(),
            self._make_good_pid_error(),
            {"overall": {"imbalance_pct": 0.0}},
        )
        imbalanced = score_tune_quality(
            self._make_good_step_response(),
            self._make_good_fft(),
            self._make_good_pid_error(),
            {"overall": {"imbalance_pct": 25.0}},  # max penalty = 20%
        )
        assert imbalanced["overall_score"] < balanced["overall_score"]

    def test_motor_penalty_included_in_result(self):
        result = score_tune_quality(
            self._make_good_step_response(),
            self._make_good_fft(),
            self._make_good_pid_error(),
            {"overall": {"imbalance_pct": 10.0}},
        )
        assert "motor_penalty" in result

    def test_details_contains_all_axes(self):
        result = score_tune_quality(
            self._make_good_step_response(),
            self._make_good_fft(),
            self._make_good_pid_error(),
            self._make_balanced_motors(),
        )
        for axis in ("roll", "pitch", "yaw"):
            assert axis in result["details"]

    def test_axis_details_have_score_and_components(self):
        result = score_tune_quality(
            self._make_good_step_response(),
            self._make_good_fft(),
            self._make_good_pid_error(),
            self._make_balanced_motors(),
        )
        for axis in ("roll", "pitch", "yaw"):
            assert "score" in result["details"][axis]
            assert "components" in result["details"][axis]

    def test_empty_inputs_still_returns_structure(self):
        result = score_tune_quality({}, {}, {}, {})
        assert "overall_score" in result
        assert 0.0 <= result["overall_score"] <= 100.0

    def test_axis_scores_are_average_of_axes(self):
        """overall_score (before motor penalty) should be mean of roll/pitch/yaw scores."""
        result = score_tune_quality(
            self._make_good_step_response(),
            self._make_good_fft(),
            self._make_good_pid_error(),
            self._make_balanced_motors(),
        )
        expected = (result["roll_score"] + result["pitch_score"] + result["yaw_score"]) / 3.0
        # Motor penalty of 0 means overall = mean
        assert result["overall_score"] == pytest.approx(expected)