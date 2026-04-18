"""Gyro spectrogram analysis - time-frequency heatmap for filtered and unfiltered gyro."""

import logging
import numpy as np
from typing import Dict, Any, Optional
from scipy import signal as scipy_signal

from .utils import extract_fields

logger = logging.getLogger(__name__)

# Frequency ceiling for spectrogram output (Hz)
MAX_FREQ_HZ = 500
# Max matrix cells before we downsample (keeps JSON payload reasonable)
MAX_MATRIX_CELLS = 600_000


def _next_power_of_2(n: int) -> int:
    """Return the smallest power of 2 >= n."""
    return 1 << max(0, (n - 1).bit_length())


def analyze_gyro_spectrogram(parser) -> Dict[str, Any]:
    """
    Compute spectrograms for each gyro axis (roll, pitch, yaw) using the
    actual filtered (gyroADC) and unfiltered (gyroUnfilt) fields from the log.

    Parameters:
        parser: orangebox Parser instance.

    Returns:
        dict keyed by axis name, each containing 'unfiltered' and 'filtered'
        spectrogram data, plus an FFT spectrum for each.
    """
    # Check which gyro fields are available
    has_unfilt = "gyroUnfilt[0]" in parser.field_names
    has_filt = "gyroADC[0]" in parser.field_names

    if not has_filt and not has_unfilt:
        return {"error": "No gyro fields found in log"}

    # Check for throttle field (rcCommand[3])
    has_throttle = "rcCommand[3]" in parser.field_names

    # Build field list for single-pass extraction
    all_field_names = ["time"]
    if has_throttle:
        all_field_names.append("rcCommand[3]")
    for i in range(3):
        if has_filt:
            all_field_names.append(f"gyroADC[{i}]")
        if has_unfilt:
            all_field_names.append(f"gyroUnfilt[{i}]")

    fields = extract_fields(parser, all_field_names)

    time_data = fields.get("time")
    if time_data is None or len(time_data) < 256:
        return {"error": "Insufficient time data for spectrogram (need >= 256 samples)"}

    time_array = time_data / 1_000_000.0  # µs → s
    dt_arr = np.diff(time_array)
    dt = float(np.median(dt_arr))
    fs = 1.0 / dt if dt > 0 else 0
    if fs <= 0:
        return {"error": "Invalid sampling frequency"}

    # Remove frames at large time gaps (>3x median dt) so the spectrogram
    # only covers continuous flight segments.  Keep the longest segment.
    gap_threshold = dt * 3.0
    gap_indices = np.where(dt_arr > gap_threshold)[0] + 1  # indices after each gap
    segments = np.split(np.arange(len(time_array)), gap_indices)
    best_seg = max(segments, key=len)
    if len(best_seg) < 256:
        return {"error": "Longest continuous segment too short for spectrogram"}

    # Slice all field arrays to the longest continuous segment
    seg_slice = slice(best_seg[0], best_seg[-1] + 1)
    time_array = time_array[seg_slice]
    for key in list(fields.keys()):
        if fields[key] is not None:
            fields[key] = fields[key][seg_slice]

    total_duration = float(time_array[-1] - time_array[0])

    # Extract throttle data (normalized to 0-100%)
    throttle_data = fields.get("rcCommand[3]")
    if throttle_data is not None:
        # rcCommand[3] is typically 1000-2000, normalize to 0-100%
        thr_min, thr_max = float(np.min(throttle_data)), float(np.max(throttle_data))
        if thr_max > 100:
            # Looks like raw PWM (1000-2000 range)
            throttle_data = np.clip((throttle_data - 1000.0) / 10.0, 0, 100)
        else:
            throttle_data = np.clip(throttle_data, 0, 100)

    axes = [("roll", 0), ("pitch", 1), ("yaw", 2)]
    result: Dict[str, Any] = {
        "sample_rate_hz": float(fs),
        "duration_s": total_duration,
        "has_unfiltered": has_unfilt,
        "has_filtered": has_filt,
        "has_throttle": throttle_data is not None,
    }

    for axis_name, axis_idx in axes:
        try:
            unfilt_data = fields.get(f"gyroUnfilt[{axis_idx}]") if has_unfilt else None
            filt_data = fields.get(f"gyroADC[{axis_idx}]") if has_filt else None

            axis_result = _compute_axis(unfilt_data, filt_data, fs, throttle_data)
            result[axis_name] = axis_result
        except Exception as e:
            logger.error(f"Spectrogram error for {axis_name}: {e}")
            result[axis_name] = {"error": str(e)}

    return result


def _compute_axis(
    unfilt_data: Optional[np.ndarray],
    filt_data: Optional[np.ndarray],
    fs: float,
    throttle_data: Optional[np.ndarray],
) -> Dict[str, Any]:
    """Compute freq-vs-throttle heatmap + FFT for a single axis, for both data sources."""
    axis_result: Dict[str, Any] = {}

    for label, gyro_data in [("unfiltered", unfilt_data), ("filtered", filt_data)]:
        if gyro_data is None or len(gyro_data) < 256:
            axis_result[label] = {"error": f"No {label} gyro data"}
            continue

        # --- Freq vs Throttle heatmap ---
        spec = _freq_vs_throttle(gyro_data, fs, throttle_data)

        # --- Full-flight FFT (for the line chart) ---
        fft = _fft_spectrum(gyro_data, fs)

        axis_result[label] = {
            "spectrogram": spec,
            "fft": fft,
        }

    return axis_result


def _fft_spectrum(gyro_data: np.ndarray, fs: float) -> Dict[str, Any]:
    """Compute PSD via Welch's method (matches Blackbox Explorer noise plot)."""
    n = len(gyro_data)
    nperseg = min(4096, n // 2)

    freqs, psd = scipy_signal.welch(
        gyro_data,
        fs=fs,
        nperseg=nperseg,
        noverlap=nperseg // 2,
        window="hann",
        scaling="density",
    )

    # Clip to MAX_FREQ_HZ
    freq_mask = freqs <= MAX_FREQ_HZ
    freqs = freqs[freq_mask]
    psd = psd[freq_mask]

    # Downsample for storage
    target = min(len(freqs), 1000)
    if len(freqs) > target:
        indices = np.linspace(0, len(freqs) - 1, target, dtype=int)
        freqs = freqs[indices]
        psd = psd[indices]

    return {
        "freqs": freqs.tolist(),
        "psd": psd.tolist(),
    }


def _freq_vs_throttle(
    gyro_data: np.ndarray,
    fs: float,
    throttle_data: Optional[np.ndarray],
) -> Dict[str, Any]:
    """Compute frequency-vs-throttle heatmap matching BBX Explorer algorithm.

    Divides data into ~300ms FFT chunks with a sliding window (1/6 step),
    computes magnitude FFT per chunk, bins results into 100 throttle bins,
    and averages. Returns linear magnitude normalized to 0-100.
    """
    NUM_THROTTLE_BINS = 100
    CHUNK_TIME_MS = 300
    WINDOW_DIVISOR = 6

    n = len(gyro_data)
    chunk_len = max(64, int(round(fs * CHUNK_TIME_MS / 1000)))
    chunk_step = max(1, chunk_len // WINDOW_DIVISOR)
    fft_size = _next_power_of_2(chunk_len)
    mag_len = fft_size // 2  # one-sided spectrum

    # Accumulator: each row = throttle bin, each col = frequency bin
    matrix = np.zeros((NUM_THROTTLE_BINS, mag_len), dtype=np.float64)
    bin_counts = np.zeros(NUM_THROTTLE_BINS, dtype=np.int32)
    max_noise = 0.0

    # Hann window for the chunk length
    window = scipy_signal.windows.hann(chunk_len)

    for start in range(0, n - chunk_len, chunk_step):
        chunk = gyro_data[start:start + chunk_len].astype(np.float64)

        # Apply Hann window
        windowed = chunk * window

        # Zero-pad to power-of-2 size
        padded = np.zeros(fft_size)
        padded[:chunk_len] = windowed

        # FFT → magnitude (one-sided)
        fft_out = np.fft.rfft(padded)
        magnitudes = np.abs(fft_out[:mag_len])
        chunk_max = float(np.max(magnitudes))
        if chunk_max > max_noise:
            max_noise = chunk_max

        # Average throttle for this chunk → bin index
        if throttle_data is not None:
            avg_thr = float(np.mean(throttle_data[start:start + chunk_len]))
        else:
            # Fallback: use time position as pseudo-throttle (0-100%)
            avg_thr = (start + chunk_len / 2) / n * 100.0

        bin_idx = int(np.clip(np.round(avg_thr), 0, NUM_THROTTLE_BINS - 1))
        matrix[bin_idx] += magnitudes
        bin_counts[bin_idx] += 1

    # Average the bins that have data
    for i in range(NUM_THROTTLE_BINS):
        if bin_counts[i] > 1:
            matrix[i] /= bin_counts[i]

    # Clip to MAX_FREQ_HZ
    freq_resolution = fs / fft_size  # Hz per bin
    max_bin = min(mag_len, int(MAX_FREQ_HZ / freq_resolution) + 1)
    matrix = matrix[:, :max_bin]
    freqs = np.arange(max_bin) * freq_resolution

    # Normalize to 0-100 (BBX Explorer style: magnitude * scale, capped at 100)
    if max_noise > 0:
        scale = 100.0 / (max_noise * 1.1)  # BBX SCALE_HEATMAP = 1.1
    else:
        scale = 1.0
    matrix_norm = np.clip(matrix * scale, 0, 100)

    # matrix_norm shape: (100 throttle bins, n_freq)
    # Plotly heatmap: z[row][col] → row = Y, col = X
    # We want X=freq, Y=throttle → already correct orientation
    throttle_values = np.arange(NUM_THROTTLE_BINS).tolist()

    return {
        "freqs": freqs.tolist(),
        "throttle_pct": throttle_values,
        "power_norm": matrix_norm.tolist(),
        "zmin": 0,
        "zmax": 100,
    }
