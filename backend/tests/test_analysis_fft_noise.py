"""Unit tests for backend/app/analysis/fft_noise.py."""

import pytest
import numpy as np
from unittest.mock import MagicMock

from app.analysis.fft_noise import analyze_fft_noise, _analyze_axis_fft, _get_band_energy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_parser_multi_call(field_names, frames_data):
    """Build a parser that can be iterated multiple times (one call per axis)."""
    parser = MagicMock()
    parser.field_names = field_names
    parser.frames = MagicMock(side_effect=lambda: iter([
        MagicMock(data=row) for row in frames_data
    ]))
    return parser


def _make_sine_signal(freq_hz, fs, duration_s):
    """Generate a pure sine wave signal."""
    t = np.arange(0, duration_s, 1.0 / fs)
    return np.sin(2 * np.pi * freq_hz * t)


# ---------------------------------------------------------------------------
# _get_band_energy
# ---------------------------------------------------------------------------

class TestGetBandEnergy:
    def test_energy_in_band(self):
        freqs = np.array([10.0, 30.0, 75.0, 150.0])
        psd = np.array([1.0, 2.0, 3.0, 4.0])
        # Band 5-50 Hz includes freqs[0]=10 and freqs[1]=30
        energy = _get_band_energy(freqs, psd, 5.0, 50.0)
        assert energy == pytest.approx(3.0)  # 1 + 2

    def test_empty_band_returns_zero(self):
        freqs = np.array([200.0, 300.0])
        psd = np.array([1.0, 2.0])
        # No frequencies in 5-50 Hz band
        energy = _get_band_energy(freqs, psd, 5.0, 50.0)
        assert energy == pytest.approx(0.0)

    def test_lower_boundary_included(self):
        freqs = np.array([5.0, 10.0, 50.0])
        psd = np.array([1.0, 2.0, 3.0])
        # f_min=5 is included, f_max=50 is NOT (mask is freqs < f_max)
        energy = _get_band_energy(freqs, psd, 5.0, 50.0)
        # 5 Hz (included) + 10 Hz (included); 50 Hz excluded
        assert energy == pytest.approx(3.0)  # 1 + 2

    def test_upper_boundary_excluded(self):
        freqs = np.array([50.0, 100.0])
        psd = np.array([5.0, 10.0])
        energy = _get_band_energy(freqs, psd, 50.0, 100.0)
        # 50 Hz is >= 50 (included), 100 Hz is NOT < 100
        assert energy == pytest.approx(5.0)

    def test_all_zeros_psd(self):
        freqs = np.arange(0.0, 100.0)
        psd = np.zeros(100)
        energy = _get_band_energy(freqs, psd, 5.0, 50.0)
        assert energy == pytest.approx(0.0)

    def test_returns_float(self):
        freqs = np.array([10.0, 20.0])
        psd = np.array([1.0, 2.0])
        result = _get_band_energy(freqs, psd, 0.0, 50.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# _analyze_axis_fft
# ---------------------------------------------------------------------------

class TestAnalyzeAxisFft:
    def test_returns_expected_keys(self):
        gyro = np.random.RandomState(0).normal(0, 10, 1000)
        result = _analyze_axis_fft(gyro, fs=1.0/0.001)
        for key in ("freqs", "psd", "peaks", "dominant_frequency_hz", "noise_floor", "energy_bands", "gyro_stats"):
            assert key in result

    def test_insufficient_data_returns_error(self):
        gyro = np.array([1.0])
        result = _analyze_axis_fft(gyro, fs=1000.0)
        assert "error" in result

    def test_empty_array_returns_error(self):
        gyro = np.array([])
        result = _analyze_axis_fft(gyro, fs=1000.0)
        assert "error" in result

    def test_peaks_are_sorted_by_power_descending(self):
        gyro = np.random.RandomState(0).normal(0, 5, 2000)
        result = _analyze_axis_fft(gyro, fs=1000.0)
        peaks = result["peaks"]
        if len(peaks) >= 2:
            for i in range(len(peaks) - 1):
                assert peaks[i]["power"] >= peaks[i + 1]["power"]

    def test_peaks_have_required_fields(self):
        gyro = np.random.RandomState(0).normal(0, 5, 2000)
        result = _analyze_axis_fft(gyro, fs=1000.0)
        for peak in result["peaks"]:
            assert "frequency_hz" in peak
            assert "power" in peak
            assert "power_db" in peak

    def test_peaks_filtered_above_5hz(self):
        gyro = np.random.RandomState(0).normal(0, 5, 2000)
        result = _analyze_axis_fft(gyro, fs=1000.0)
        for peak in result["peaks"]:
            assert peak["frequency_hz"] > 5.0

    def test_max_10_peaks_returned(self):
        gyro = np.random.RandomState(0).normal(0, 5, 5000)
        result = _analyze_axis_fft(gyro, fs=1000.0)
        assert len(result["peaks"]) <= 10

    def test_energy_bands_have_expected_keys(self):
        gyro = np.random.RandomState(0).normal(0, 5, 2000)
        result = _analyze_axis_fft(gyro, fs=1000.0)
        for band in ("5_50_hz", "50_100_hz", "100_250_hz", "250_500_hz"):
            assert band in result["energy_bands"]

    def test_energy_bands_nonnegative(self):
        gyro = np.random.RandomState(0).normal(0, 5, 2000)
        result = _analyze_axis_fft(gyro, fs=1000.0)
        for v in result["energy_bands"].values():
            assert v >= 0.0

    def test_noise_floor_nonnegative(self):
        gyro = np.random.RandomState(0).normal(0, 5, 2000)
        result = _analyze_axis_fft(gyro, fs=1000.0)
        assert result["noise_floor"] >= 0.0

    def test_dominant_frequency_nonnegative(self):
        gyro = np.random.RandomState(0).normal(0, 5, 2000)
        result = _analyze_axis_fft(gyro, fs=1000.0)
        assert result["dominant_frequency_hz"] >= 0.0

    def test_dominant_frequency_matches_first_peak(self):
        gyro = np.random.RandomState(0).normal(0, 5, 2000)
        result = _analyze_axis_fft(gyro, fs=1000.0)
        peaks = result["peaks"]
        if peaks:
            assert result["dominant_frequency_hz"] == pytest.approx(peaks[0]["frequency_hz"])
        else:
            assert result["dominant_frequency_hz"] == pytest.approx(0.0)

    def test_sine_signal_returns_valid_structure(self):
        """A sine wave signal should return a valid result dict without raising."""
        # The 'fs' parameter in _analyze_axis_fft is the dt (time step),
        # matching how analyze_fft_noise calls it: _analyze_axis_fft(data, dt)
        dt = 1.0 / 2000.0  # 2 kHz sampling
        t = np.arange(0, 1.0, dt)
        gyro = np.sin(2 * np.pi * 100.0 * t) * 100.0
        result = _analyze_axis_fft(gyro, fs=dt)
        # Should return a valid result (not an error dict)
        assert "error" not in result
        assert "peaks" in result
        assert isinstance(result["peaks"], list)

    def test_gyro_stats_present(self):
        gyro = np.random.RandomState(0).normal(0, 5, 500)
        result = _analyze_axis_fft(gyro, fs=0.001)
        assert "gyro_stats" in result
        for key in ("mean", "std", "min", "max", "rms", "peak"):
            assert key in result["gyro_stats"]


# ---------------------------------------------------------------------------
# analyze_fft_noise (parser-level)
# ---------------------------------------------------------------------------

class TestAnalyzeFftNoise:
    def _make_valid_parser(self, n=500, fs=1000):
        """Parser with time + gyroADC fields."""
        dt_us = int(1_000_000 / fs)
        field_names = ["time", "gyroADC[0]", "gyroADC[1]", "gyroADC[2]"]
        rng = np.random.RandomState(42)
        rows = []
        for i in range(n):
            t = i * dt_us
            gyros = rng.normal(0, 10, 3).tolist()
            rows.append([t] + gyros)
        return _make_parser_multi_call(field_names, rows)

    def test_returns_roll_pitch_yaw(self):
        parser = self._make_valid_parser()
        result = analyze_fft_noise(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert axis in result

    def test_no_time_field_returns_error(self):
        parser = _make_parser_multi_call(["gyroADC[0]"], [[100]] * 100)
        result = analyze_fft_noise(parser)
        assert "error" in result

    def test_only_one_time_sample_returns_error(self):
        parser = _make_parser_multi_call(["time"], [[0]])
        result = analyze_fft_noise(parser)
        assert "error" in result

    def test_missing_gyro_axis_returns_axis_error(self):
        """If gyroADC[0] is missing, roll should have error key."""
        n = 200
        dt_us = 1000
        field_names = ["time", "gyroADC[1]", "gyroADC[2]"]  # no gyroADC[0]
        rows = [[i * dt_us, 10.0, 10.0] for i in range(n)]
        parser = _make_parser_multi_call(field_names, rows)
        result = analyze_fft_noise(parser)
        assert "error" in result["roll"]

    def test_valid_data_no_error_keys(self):
        parser = self._make_valid_parser()
        result = analyze_fft_noise(parser)
        for axis in ("roll", "pitch", "yaw"):
            assert "error" not in result[axis]