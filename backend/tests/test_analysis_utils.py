"""Unit tests for backend/app/analysis/utils.py."""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from app.analysis.utils import (
    extract_field_data,
    get_time_array,
    calculate_derivative,
    find_peaks,
    normalize_signal,
    calculate_rms,
    calculate_stats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser(field_names, frames_data):
    """Build a minimal mock parser with given field names and frame data rows."""
    mock_parser = MagicMock()
    mock_parser.field_names = field_names

    frames = []
    for row in frames_data:
        frame = MagicMock()
        frame.data = row
        frames.append(frame)

    mock_parser.frames = MagicMock(return_value=iter(frames))
    return mock_parser


# ---------------------------------------------------------------------------
# extract_field_data
# ---------------------------------------------------------------------------

class TestExtractFieldData:
    def test_returns_none_for_missing_field(self):
        parser = _make_parser(["time", "gyroADC[0]"], [])
        result = extract_field_data(parser, "nonexistent")
        assert result is None

    def test_extracts_field_as_float64_array(self):
        parser = _make_parser(
            ["time", "gyroADC[0]"],
            [[1000, 10.0], [2000, 20.0], [3000, 30.0]],
        )
        result = extract_field_data(parser, "gyroADC[0]")
        assert result is not None
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float64
        np.testing.assert_array_equal(result, [10.0, 20.0, 30.0])

    def test_extracts_time_field(self):
        parser = _make_parser(
            ["time"],
            [[0], [1_000_000], [2_000_000]],
        )
        result = extract_field_data(parser, "time")
        assert result is not None
        np.testing.assert_array_equal(result, [0.0, 1_000_000.0, 2_000_000.0])

    def test_empty_frames_returns_empty_array(self):
        parser = _make_parser(["time"], [])
        result = extract_field_data(parser, "time")
        assert result is not None
        assert len(result) == 0

    def test_returns_none_on_frame_exception(self):
        mock_parser = MagicMock()
        mock_parser.field_names = ["bad_field"]
        mock_parser.frames = MagicMock(side_effect=RuntimeError("io error"))
        result = extract_field_data(mock_parser, "bad_field")
        assert result is None


# ---------------------------------------------------------------------------
# get_time_array
# ---------------------------------------------------------------------------

class TestGetTimeArray:
    def test_returns_none_when_no_time_field(self):
        parser = _make_parser(["gyroADC[0]"], [])
        result = get_time_array(parser)
        assert result is None

    def test_converts_microseconds_to_seconds(self):
        parser = _make_parser(
            ["time"],
            [[0], [1_000_000], [2_000_000]],
        )
        result = get_time_array(parser)
        assert result is not None
        np.testing.assert_allclose(result, [0.0, 1.0, 2.0])

    def test_fractional_seconds(self):
        parser = _make_parser(
            ["time"],
            [[500_000], [1_500_000]],
        )
        result = get_time_array(parser)
        np.testing.assert_allclose(result, [0.5, 1.5])


# ---------------------------------------------------------------------------
# calculate_derivative
# ---------------------------------------------------------------------------

class TestCalculateDerivative:
    def test_single_element_returns_zeros(self):
        signal = np.array([5.0])
        result = calculate_derivative(signal, dt=1.0)
        np.testing.assert_array_equal(result, [0.0])

    def test_first_element_is_zero(self):
        signal = np.array([1.0, 2.0, 4.0])
        result = calculate_derivative(signal, dt=1.0)
        assert result[0] == 0.0

    def test_constant_signal_gives_zero_derivative(self):
        signal = np.array([3.0, 3.0, 3.0, 3.0])
        result = calculate_derivative(signal, dt=1.0)
        np.testing.assert_array_equal(result, [0.0, 0.0, 0.0, 0.0])

    def test_linear_signal_constant_derivative(self):
        signal = np.array([0.0, 1.0, 2.0, 3.0])
        result = calculate_derivative(signal, dt=1.0)
        # First element 0, rest 1.0
        np.testing.assert_allclose(result[1:], [1.0, 1.0, 1.0])

    def test_dt_scaling(self):
        signal = np.array([0.0, 2.0, 4.0])
        result = calculate_derivative(signal, dt=2.0)
        # diff/dt = 2/2 = 1.0
        np.testing.assert_allclose(result[1:], [1.0, 1.0])

    def test_output_same_shape_as_input(self):
        signal = np.array([1.0, 2.0, 5.0, 7.0])
        result = calculate_derivative(signal, dt=0.001)
        assert result.shape == signal.shape


# ---------------------------------------------------------------------------
# find_peaks
# ---------------------------------------------------------------------------

class TestFindPeaks:
    def test_finds_obvious_peak(self):
        # Single clear peak in the middle
        signal = np.array([0.0, 0.1, 0.5, 1.0, 0.5, 0.1, 0.0])
        peaks = find_peaks(signal, threshold=0.5)
        assert len(peaks) >= 1
        assert 3 in peaks  # index 3 is the peak

    def test_flat_signal_no_peaks(self):
        signal = np.ones(20)
        peaks = find_peaks(signal, threshold=0.5)
        assert len(peaks) == 0

    def test_multiple_peaks(self):
        signal = np.array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        peaks = find_peaks(signal, threshold=0.3)
        assert len(peaks) >= 2

    def test_returns_list_of_ints(self):
        signal = np.array([0.0, 1.0, 0.0])
        peaks = find_peaks(signal)
        assert isinstance(peaks, list)
        for p in peaks:
            assert isinstance(p, (int, np.integer))


# ---------------------------------------------------------------------------
# normalize_signal
# ---------------------------------------------------------------------------

class TestNormalizeSignal:
    def test_max_abs_is_one(self):
        signal = np.array([2.0, -4.0, 3.0])
        result = normalize_signal(signal)
        assert np.max(np.abs(result)) == pytest.approx(1.0)

    def test_zero_signal_returns_unchanged(self):
        signal = np.zeros(5)
        result = normalize_signal(signal)
        np.testing.assert_array_equal(result, signal)

    def test_positive_signal_normalized(self):
        signal = np.array([1.0, 2.0, 4.0])
        result = normalize_signal(signal)
        np.testing.assert_allclose(result, [0.25, 0.5, 1.0])

    def test_negative_signal_normalized(self):
        signal = np.array([-5.0, -2.5])
        result = normalize_signal(signal)
        np.testing.assert_allclose(result, [-1.0, -0.5])

    def test_mixed_signal(self):
        signal = np.array([-3.0, 0.0, 6.0])
        result = normalize_signal(signal)
        np.testing.assert_allclose(result, [-0.5, 0.0, 1.0])


# ---------------------------------------------------------------------------
# calculate_rms
# ---------------------------------------------------------------------------

class TestCalculateRms:
    def test_constant_signal_rms_equals_value(self):
        signal = np.array([3.0, 3.0, 3.0])
        assert calculate_rms(signal) == pytest.approx(3.0)

    def test_zero_signal_rms_is_zero(self):
        signal = np.zeros(10)
        assert calculate_rms(signal) == pytest.approx(0.0)

    def test_known_rms_value(self):
        # RMS of [3, 4] = sqrt((9+16)/2) = sqrt(12.5)
        signal = np.array([3.0, 4.0])
        expected = np.sqrt(12.5)
        assert calculate_rms(signal) == pytest.approx(expected)

    def test_returns_float(self):
        signal = np.array([1.0, 2.0])
        assert isinstance(calculate_rms(signal), float)

    def test_single_element(self):
        signal = np.array([7.0])
        assert calculate_rms(signal) == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# calculate_stats
# ---------------------------------------------------------------------------

class TestCalculateStats:
    def test_returns_all_required_keys(self):
        signal = np.array([1.0, 2.0, 3.0, 4.0])
        stats = calculate_stats(signal)
        for key in ("mean", "std", "min", "max", "rms", "peak"):
            assert key in stats

    def test_known_values(self):
        signal = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        stats = calculate_stats(signal)
        assert stats["mean"] == pytest.approx(3.0)
        assert stats["min"] == pytest.approx(1.0)
        assert stats["max"] == pytest.approx(5.0)
        assert stats["peak"] == pytest.approx(5.0)

    def test_all_values_are_floats(self):
        signal = np.array([1.0, -2.0, 3.0])
        stats = calculate_stats(signal)
        for v in stats.values():
            assert isinstance(v, float)

    def test_peak_is_max_abs(self):
        signal = np.array([2.0, -5.0, 3.0])
        stats = calculate_stats(signal)
        assert stats["peak"] == pytest.approx(5.0)

    def test_negative_values(self):
        signal = np.array([-3.0, -1.0, -2.0])
        stats = calculate_stats(signal)
        assert stats["min"] == pytest.approx(-3.0)
        assert stats["max"] == pytest.approx(-1.0)
        assert stats["mean"] == pytest.approx(-2.0)
        assert stats["peak"] == pytest.approx(3.0)

    def test_std_known(self):
        signal = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        stats = calculate_stats(signal)
        assert stats["std"] == pytest.approx(float(np.std(signal)))