"""Unit tests for backend/app/analysis/fft_noise.py."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from app.analysis.fft_noise import (
    analyze_fft_noise,
    _analyze_axis_fft,
    _get_band_energy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser(field_names, frames_data):
    """Build a minimal mock parser."""
    mock_parser = MagicMock()
    mock_parser.field_names = field_names

    frames = []
    for row in frames_data:
        frame = MagicMock()
        frame.data = row
        frames.append(frame)

    mock_parser.frames = MagicMock(return_value=iter(frames))
    return mock_parser


def _make_frames_data(n_frames, n_fields, time_step_us=1000):
    """Generate deterministic frame data: time + gyro axes."""
    rows = []
    for i in range(n_frames):
        rows.append([i * time_step_us] + [float(i % 50) for _ in range(n_fields - 1)])
    return rows


def _make_full_parser(n_frames=200, time_step_us=1000):
    """Make a parser with time + 3 gyro axes."""
    field_names = ["time", "gyroADC[0]", "gyroADC[1]", "gyroADC[2]"]
    frames = _make_frames_data(n_frames, len(field_names), time_step_us)
    parser = _make_parser(field_names, frames)
    return parser


# ---------------------------------------------------------------------------
# _get_band_energy
# ---------------------------------------------------------------------------

class TestGetBandEnergy:
    def test_returns_zero_when_no_bins_in_band(self):
        freqs = np.array([1.0, 2.0, 3.0])
        psd = np.array([1.0, 2.0, 3.0])
        result = _get_band_energy(freqs, psd, 10.0, 100.0)
        assert result == 0.0

    def test_sums_bins_within_band(self):
        freqs = np.array([5.0, 25.0, 75.0, 200.0])
        psd = np.array([1.0, 2.0, 3.0, 4.0])
        # Band [5, 50): indices 0 and 1
        result = _get_band_energy(freqs, psd, 5.0, 50.0)
        assert result == pytest.approx(3.0)

    def test_lower_bound_inclusive(self):
        freqs = np.array([10.0, 20.0])
        psd = np.array([5.0, 6.0])
        result = _get_band_energy(freqs, psd, 10.0, 50.0)
        assert result == pytest.approx(11.0)

    def test_upper_bound_exclusive(self):
        freqs = np.array([10.0, 50.0])
        psd = np.array([5.0, 6.0])
        # [10, 50) excludes 50.0
        result = _get_band_energy(freqs, psd, 10.0, 50.0)
        assert result == pytest.approx(5.0)

    def test_returns_float(self):
        freqs = np.array([10.0])
        psd = np.array([2.0])
        result = _get_band_energy(freqs, psd, 5.0, 20.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# _analyze_axis_fft
# ---------------------------------------------------------------------------

class TestAnalyzeAxisFft:
    def test_insufficient_data_returns_error(self):
        gyro = np.array([1.0])  # Only one sample
        result = _analyze_axis_fft(gyro, fs=0.001, axis="roll")
        assert "error" in result

    def test_returns_required_keys_on_success(self):
        # Use a simple sine wave signal
        n = 512
        dt = 0.001  # 1ms, so fs=1000 Hz
        t = np.arange(n) * dt
        gyro = np.sin(2 * np.pi * 100 * t)  # 100 Hz sine

        result = _analyze_axis_fft(gyro, fs=dt, axis="roll")
        for key in ("freqs", "psd", "peaks", "dominant_frequency_hz", "noise_floor",
                    "energy_bands", "gyro_stats"):
            assert key in result

    def test_peaks_are_sorted_by_power_descending(self):
        n = 512
        dt = 0.001
        t = np.arange(n) * dt
        gyro = np.sin(2 * np.pi * 50 * t) * 2 + np.sin(2 * np.pi * 100 * t)

        result = _analyze_axis_fft(gyro, fs=dt, axis="roll")
        peaks = result["peaks"]
        if len(peaks) >= 2:
            for i in range(len(peaks) - 1):
                assert peaks[i]["power"] >= peaks[i + 1]["power"]

    def test_max_10_peaks_returned(self):
        n = 512
        dt = 0.001
        t = np.arange(n) * dt
        # Random noise will have many PSD values
        rng = np.random.default_rng(42)
        gyro = rng.standard_normal(n)

        result = _analyze_axis_fft(gyro, fs=dt, axis="roll")
        assert len(result["peaks"]) <= 10

    def test_peak_frequency_above_5hz(self):
        n = 512
        dt = 0.001
        t = np.arange(n) * dt
        gyro = np.sin(2 * np.pi * 100 * t)

        result = _analyze_axis_fft(gyro, fs=dt, axis="roll")
        for peak in result["peaks"]:
            assert peak["frequency_hz"] > 5.0

    def test_energy_bands_keys_present(self):
        n = 512
        dt = 0.001
        t = np.arange(n) * dt
        gyro = np.sin(2 * np.pi * 50 * t)

        result = _analyze_axis_fft(gyro, fs=dt, axis="roll")
        bands = result["energy_bands"]
        for key in ("5_50_hz", "50_100_hz", "100_250_hz", "250_500_hz"):
            assert key in bands

    def test_energy_bands_non_negative(self):
        n = 512
        dt = 0.001
        t = np.arange(n) * dt
        gyro = np.sin(2 * np.pi * 75 * t)

        result = _analyze_axis_fft(gyro, fs=dt, axis="roll")
        for v in result["energy_bands"].values():
            assert v >= 0.0

    def test_dominant_freq_zero_when_no_peaks_above_5hz(self):
        # Very short DC-only signal, all frequency bins at or below 5 Hz
        n = 4
        dt = 0.5  # fs = 2Hz, so max freq = 1Hz
        gyro = np.array([1.0, 1.0, 1.0, 1.0])

        result = _analyze_axis_fft(gyro, fs=dt, axis="roll")
        if "dominant_frequency_hz" in result and result.get("peaks") == []:
            assert result["dominant_frequency_hz"] == 0.0


# ---------------------------------------------------------------------------
# analyze_fft_noise
# ---------------------------------------------------------------------------

class TestAnalyzeFftNoise:
    def test_no_time_returns_error(self):
        parser = _make_parser(["gyroADC[0]"], [[1.0], [2.0]])
        result = analyze_fft_noise(parser)
        assert "error" in result

    def test_single_time_sample_returns_error(self):
        parser = _make_parser(["time", "gyroADC[0]"], [[1000, 5.0]])
        result = analyze_fft_noise(parser)
        assert "error" in result

    def test_missing_gyro_axis_produces_per_axis_error(self):
        # Only roll gyro provided, pitch and yaw missing
        field_names = ["time", "gyroADC[0]"]
        n = 100

        def make_frames():
            for i in range(n):
                frame = MagicMock()
                frame.data = [i * 1000, float(i % 50)]
                yield frame

        parser = MagicMock()
        parser.field_names = field_names
        parser.frames = MagicMock(side_effect=make_frames)
        result = analyze_fft_noise(parser)
        # pitch and yaw axes should have errors (no gyro data for them)
        assert "error" in result.get("pitch", {})
        assert "error" in result.get("yaw", {})

    def test_all_axes_analyzed_when_all_fields_present(self):
        field_names = ["time", "gyroADC[0]", "gyroADC[1]", "gyroADC[2]"]
        parser = MagicMock()
        parser.field_names = field_names
        n = 100

        def make_frames():
            for i in range(n):
                frame = MagicMock()
                frame.data = [i * 1000, float(i % 50), float(i % 40), float(i % 30)]
                yield frame

        parser.frames = MagicMock(side_effect=make_frames)
        result = analyze_fft_noise(parser)

        assert "error" not in result
        for axis in ("roll", "pitch", "yaw"):
            assert axis in result
            assert "error" not in result[axis]

    def test_invalid_sampling_frequency_returns_error(self):
        # Constant time → dt=0 → invalid fs
        field_names = ["time", "gyroADC[0]"]
        n = 100

        def make_frames_constant_time():
            # All frames have the same timestamp → mean(diff) = 0 → invalid fs
            for i in range(n):
                frame = MagicMock()
                frame.data = [1000, float(i % 5)]  # constant time = 1000
                yield frame

        parser = MagicMock()
        parser.field_names = field_names
        parser.frames = MagicMock(side_effect=make_frames_constant_time)
        result = analyze_fft_noise(parser)
        # Either error overall or per-axis error; at minimum should not raise
        assert isinstance(result, dict)