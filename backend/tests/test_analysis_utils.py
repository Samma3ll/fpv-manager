"""Unit tests for backend/app/analysis/utils.py."""

import sys
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from app.analysis.utils import (
    calculate_rms,
    calculate_stats,
    calculate_derivative,
    find_peaks,
    normalize_signal,
    extract_field_data,
    get_time_array,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser(field_names, frame_rows):
    """
    Build a minimal mock parser.

    field_names: list of field name strings.
    frame_rows: list of lists where each inner list is one frame's data values.
    """
    parser = MagicMock()
    parser.field_names = field_names

    frames = []
    for row in frame_rows:
        frame = MagicMock()
        frame.data = row
        frames.append(frame)

    parser.frames = MagicMock(return_value=iter(frames))
    return parser


# ---------------------------------------------------------------------------
# calculate_rms
# ---------------------------------------------------------------------------

class TestCalculateRms:
    def test_all_ones_returns_one(self):
        signal = np.ones(10)
        assert calculate_rms(signal) == pytest.approx(1.0)

    def test_known_values(self):
        # RMS of [3, 4] = sqrt((9+16)/2) = sqrt(12.5)
        signal = np.array([3.0, 4.0])
        assert calculate_rms(signal) == pytest.approx(np.sqrt(12.5))

    def test_zeros_returns_zero(self):
        signal = np.zeros(5)
        assert calculate_rms(signal) == pytest.approx(0.0)

    def test_single_value(self):
        signal = np.array([5.0])
        assert calculate_rms(signal) == pytest.approx(5.0)

    def test_negative_values(self):
        # RMS ignores sign
        signal = np.array([-3.0, -4.0])
        assert calculate_rms(signal) == pytest.approx(np.sqrt(12.5))

    def test_returns_float(self):
        signal = np.array([1.0, 2.0, 3.0])
        result = calculate_rms(signal)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_stats
# ---------------------------------------------------------------------------

class TestCalculateStats:
    def test_returns_all_keys(self):
        signal = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        stats = calculate_stats(signal)
        for key in ("mean", "std", "min", "max", "rms", "peak"):
            assert key in stats

    def test_mean_value(self):
        signal = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert calculate_stats(signal)["mean"] == pytest.approx(3.0)

    def test_min_max_values(self):
        signal = np.array([10.0, -5.0, 3.0])
        stats = calculate_stats(signal)
        assert stats["min"] == pytest.approx(-5.0)
        assert stats["max"] == pytest.approx(10.0)

    def test_peak_is_max_absolute(self):
        signal = np.array([3.0, -8.0, 5.0])
        assert calculate_stats(signal)["peak"] == pytest.approx(8.0)

    def test_std_value(self):
        signal = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        stats = calculate_stats(signal)
        assert stats["std"] == pytest.approx(np.std(signal))

    def test_rms_matches_calculate_rms(self):
        signal = np.array([3.0, 4.0, 5.0])
        stats = calculate_stats(signal)
        assert stats["rms"] == pytest.approx(calculate_rms(signal))

    def test_all_values_are_floats(self):
        signal = np.array([1, 2, 3], dtype=np.int32)
        stats = calculate_stats(signal)
        for v in stats.values():
            assert isinstance(v, float)

    def test_single_element(self):
        signal = np.array([7.0])
        stats = calculate_stats(signal)
        assert stats["mean"] == pytest.approx(7.0)
        assert stats["min"] == pytest.approx(7.0)
        assert stats["max"] == pytest.approx(7.0)
        assert stats["peak"] == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# calculate_derivative
# ---------------------------------------------------------------------------

class TestCalculateDerivative:
    def test_constant_signal_has_zero_derivative(self):
        signal = np.ones(10) * 5.0
        deriv = calculate_derivative(signal, dt=1.0)
        assert np.allclose(deriv[1:], 0.0)

    def test_first_element_is_zero(self):
        signal = np.array([1.0, 2.0, 3.0])
        deriv = calculate_derivative(signal, dt=1.0)
        assert deriv[0] == pytest.approx(0.0)

    def test_linear_signal_constant_derivative(self):
        signal = np.arange(0.0, 10.0)
        deriv = calculate_derivative(signal, dt=1.0)
        # All non-zero differences should be 1.0
        assert np.allclose(deriv[1:], 1.0)

    def test_dt_scaling(self):
        signal = np.array([0.0, 2.0, 4.0, 6.0])
        deriv = calculate_derivative(signal, dt=2.0)
        # diff / dt = 2 / 2 = 1.0
        assert np.allclose(deriv[1:], 1.0)

    def test_single_element_returns_zero(self):
        signal = np.array([42.0])
        deriv = calculate_derivative(signal, dt=1.0)
        assert np.allclose(deriv, 0.0)

    def test_output_same_length_as_input(self):
        signal = np.array([1.0, 2.0, 5.0, 3.0])
        deriv = calculate_derivative(signal, dt=1.0)
        assert len(deriv) == len(signal)

    def test_empty_like_empty_input(self):
        signal = np.array([])
        deriv = calculate_derivative(signal, dt=1.0)
        assert len(deriv) == 0


# ---------------------------------------------------------------------------
# normalize_signal
# ---------------------------------------------------------------------------

class TestNormalizeSignal:
    def test_positive_signal_normalized_to_one(self):
        signal = np.array([0.0, 2.0, 4.0, 10.0])
        normed = normalize_signal(signal)
        assert np.max(np.abs(normed)) == pytest.approx(1.0)

    def test_max_abs_is_one(self):
        signal = np.array([-5.0, 3.0, 1.0])
        normed = normalize_signal(signal)
        assert np.max(np.abs(normed)) == pytest.approx(1.0)

    def test_zero_signal_returns_unchanged(self):
        signal = np.zeros(5)
        normed = normalize_signal(signal)
        assert np.allclose(normed, 0.0)

    def test_single_positive_value(self):
        signal = np.array([4.0])
        normed = normalize_signal(signal)
        assert normed[0] == pytest.approx(1.0)

    def test_sign_preserved(self):
        signal = np.array([-4.0, 2.0])
        normed = normalize_signal(signal)
        assert normed[0] == pytest.approx(-1.0)
        assert normed[1] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# find_peaks
# ---------------------------------------------------------------------------

class TestFindPeaks:
    def test_single_clear_peak(self):
        signal = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        peaks = find_peaks(signal, threshold=0.5)
        assert 3 in peaks

    def test_multiple_peaks(self):
        signal = np.array([0.0, 1.0, 0.0, 1.0, 0.0])
        peaks = find_peaks(signal, threshold=0.5)
        assert len(peaks) >= 2

    def test_flat_signal_no_peaks(self):
        signal = np.ones(10)
        peaks = find_peaks(signal, threshold=0.5)
        assert len(peaks) == 0

    def test_returns_list(self):
        signal = np.array([0.0, 1.0, 0.0])
        result = find_peaks(signal, threshold=0.1)
        assert isinstance(result, list)

    def test_high_threshold_filters_small_peaks(self):
        signal = np.array([0.0, 0.1, 0.0, 1.0, 0.0])
        # threshold=0.5 means min height = 0 + 0.5*(1-0) = 0.5
        peaks_strict = find_peaks(signal, threshold=0.5)
        peaks_loose = find_peaks(signal, threshold=0.05)
        assert len(peaks_strict) <= len(peaks_loose)


# ---------------------------------------------------------------------------
# extract_field_data
# ---------------------------------------------------------------------------

class TestExtractFieldData:
    def test_returns_array_for_valid_field(self):
        parser = _make_parser(["time", "gyroADC[0]"], [[0, 100], [1, 200], [2, 300]])
        result = extract_field_data(parser, "gyroADC[0]")
        assert result is not None
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_equal(result, [100.0, 200.0, 300.0])

    def test_returns_none_for_missing_field(self):
        parser = _make_parser(["time"], [[0], [1]])
        result = extract_field_data(parser, "nonexistent_field")
        assert result is None

    def test_dtype_is_float64(self):
        parser = _make_parser(["time"], [[1000], [2000], [3000]])
        result = extract_field_data(parser, "time")
        assert result.dtype == np.float64

    def test_extracts_correct_field_index(self):
        parser = _make_parser(
            ["fieldA", "fieldB", "fieldC"],
            [[10, 20, 30], [11, 21, 31]],
        )
        result = extract_field_data(parser, "fieldC")
        np.testing.assert_array_equal(result, [30.0, 31.0])

    def test_returns_none_on_frame_iteration_error(self):
        parser = MagicMock()
        parser.field_names = ["time"]
        parser.frames = MagicMock(side_effect=RuntimeError("read error"))
        result = extract_field_data(parser, "time")
        assert result is None


# ---------------------------------------------------------------------------
# get_time_array
# ---------------------------------------------------------------------------

class TestGetTimeArray:
    def test_converts_microseconds_to_seconds(self):
        # 2 seconds worth of frames at 0 and 2,000,000 microseconds
        parser = _make_parser(["time"], [[0], [1_000_000], [2_000_000]])
        result = get_time_array(parser)
        assert result is not None
        np.testing.assert_allclose(result, [0.0, 1.0, 2.0])

    def test_returns_none_when_no_time_field(self):
        parser = _make_parser(["gyroADC[0]"], [[100], [200]])
        result = get_time_array(parser)
        assert result is None

    def test_result_is_numpy_array(self):
        parser = _make_parser(["time"], [[0], [500_000]])
        result = get_time_array(parser)
        assert isinstance(result, np.ndarray)

    def test_single_frame_returns_array(self):
        parser = _make_parser(["time"], [[5_000_000]])
        result = get_time_array(parser)
        assert result is not None
        assert result[0] == pytest.approx(5.0)