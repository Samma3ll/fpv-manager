"""FFT noise analysis - identify resonance peaks and frequency content."""

import logging
import numpy as np
from typing import Dict, Any, Optional
from scipy import signal as scipy_signal

from .utils import extract_fields, calculate_stats

logger = logging.getLogger(__name__)


def analyze_fft_noise(parser) -> Dict[str, Any]:
    """
    Analyze gyroscope time-series and produce per-axis frequency analysis including PSD, resonance peaks, dominant frequency, noise floor, band energies, and basic statistics.
    
    Parameters:
        parser: Object providing a time array (in microseconds) and per-axis gyro sample arrays named "gyroADC[0]", "gyroADC[1]", and "gyroADC[2]".
    
    Returns:
        dict: Mapping each axis name ("roll", "pitch", "yaw") to either an analysis dict or an error dict.
            On success each axis dict contains:
                - freqs: downsampled frequency bins (list of floats)
                - psd: downsampled power spectral density values (list of floats)
                - peaks: list of up to 10 peak dicts with keys "frequency_hz", "power", "power_db"
                - dominant_frequency_hz: float
                - max_noise_frequency_hz: float (frequency of maximum PSD in the high-frequency region)
                - noise_floor: float (median PSD in the 3–50 Hz range when available)
                - energy_bands: dict of band energies keyed by band name (e.g., "5_50_hz", "50_100_hz", "100_250_hz", "250_500_hz")
                - gyro_stats: summary statistics produced from the raw gyro samples
            If global prerequisites fail, returns {"error": "<message>"}. If an axis cannot be analyzed, that axis maps to {"error": "<message>"}.
    """
    result = {}
    
    field_names = ["time", "gyroADC[0]", "gyroADC[1]", "gyroADC[2]"]
    fields = extract_fields(parser, field_names)
    time_data = fields.get("time")
    time_array = time_data / 1_000_000.0 if time_data is not None else None
    if time_array is None or len(time_array) < 2:
        logger.warning("Cannot analyze FFT: no valid time data")
        return {"error": "No valid time data"}
    
    dt_arr = np.diff(time_array)
    dt_arr = dt_arr[dt_arr > 0]
    if dt_arr.size == 0:
        logger.warning("Cannot analyze FFT: invalid time deltas")
        return {"error": "Invalid time deltas"}

    # Use median timestep and remove large time-gap regions.
    dt = float(np.median(dt_arr))
    gap_indices = np.where(np.diff(time_array) > dt * 3.0)[0] + 1
    segments = np.split(np.arange(len(time_array)), gap_indices)
    best_segment = max(segments, key=len)

    fs = 1.0 / dt if dt > 0 else 0
    
    if fs <= 0:
        logger.warning("Invalid sampling frequency")
        return {"error": "Invalid sampling frequency"}
    
    # Analyze each axis (roll=0, pitch=1, yaw=2)
    axes = [("roll", 0), ("pitch", 1), ("yaw", 2)]
    
    for axis_name, axis_idx in axes:
        gyro_field = f"gyroADC[{axis_idx}]"
        gyro_data = fields.get(gyro_field)
        
        if gyro_data is None:
            logger.warning(f"No gyro data for {axis_name} axis")
            result[axis_name] = {"error": f"No {axis_name} gyro data"}
            continue

        gyro_data = gyro_data[best_segment]
        
        try:
            axis_result = _analyze_axis_fft(gyro_data, fs, axis=axis_name)
            result[axis_name] = axis_result
        except Exception as e:
            logger.error(f"Error analyzing {axis_name} FFT: {e}")
            result[axis_name] = {"error": str(e)}
    
    return result


def _analyze_axis_fft(gyro_data: np.ndarray, fs: float, axis: str = "unknown") -> Dict[str, Any]:
    """
    Compute the power spectral density and related noise/peak metrics for a single gyroscope axis.
    
    Parameters:
        gyro_data (np.ndarray): Time-series gyroscope samples for the axis.
        fs (float): Sampling frequency in Hz.
        axis (str): Human-readable axis name for context (e.g., "roll", "pitch", "yaw").
    
    Returns:
        dict: Analysis results or an error dictionary.
            On success, the dictionary contains:
                - "freqs": list[float] — downsampled frequency bin centers in Hz.
                - "psd": list[float] — downsampled power spectral density values.
                - "peaks": list[dict] — up to 10 peak objects with keys:
                    "frequency_hz" (float), "power" (float), "power_db" (float).
                - "dominant_frequency_hz": float — frequency of the highest-power peak or 0.0.
                - "max_noise_frequency_hz": float — frequency of maximum PSD in the high-frequency band or 0.0.
                - "noise_floor": float — median PSD in 3–50 Hz or 0.0 if unavailable.
                - "energy_bands": dict — summed PSD energy for predefined bands ("5_50_hz", "50_100_hz", "100_250_hz", "250_500_hz").
                - "gyro_stats": dict — summary statistics for the input gyro_data.
            If input length is insufficient, returns {"error": "Insufficient data"}.
    """
    n = len(gyro_data)
    if n < 2:
        return {"error": "Insufficient data"}
    
    gyro_mean_removed = gyro_data - np.mean(gyro_data)

    # Welch PSD is closer to the Blackbox analyser output than a single FFT.
    nperseg = int(min(4096, max(256, n // 4)))
    nperseg = min(nperseg, n)
    nperseg = max(nperseg, 2)
    noverlap = nperseg // 2
    freqs, psd = scipy_signal.welch(
        gyro_mean_removed,
        fs=fs,
        nperseg=nperseg,
        noverlap=noverlap,
        window="hann",
        scaling="density",
    )
    
    analysis_mask = freqs > 5
    if np.any(analysis_mask):
        threshold = np.percentile(psd[analysis_mask], 95)
        peak_indices = np.where((psd >= threshold) & analysis_mask)[0]
    else:
        threshold = np.percentile(psd, 95)
        peak_indices = np.where(psd >= threshold)[0]
    peaks = []
    
    for idx in peak_indices:
        # Filter out DC and very low frequencies (< 5 Hz)
        if freqs[idx] > 5:
            peaks.append({
                "frequency_hz": float(freqs[idx]),
                "power": float(psd[idx]),
                "power_db": float(10 * np.log10(psd[idx]) if psd[idx] > 0 else -120),
            })
    
    # Sort by power
    peaks = sorted(peaks, key=lambda x: x["power"], reverse=True)[:10]  # Top 10 peaks
    
    # Identify dominant frequency (peak with highest power)
    dominant_freq = 0.0
    if len(peaks) > 0:
        dominant_freq = peaks[0]["frequency_hz"]

    # Match BB viewer behavior: ignore low frequencies when looking for max noise.
    high_freq_mask = freqs >= 100
    if not np.any(high_freq_mask):
        high_freq_mask = freqs >= 3
    max_noise_frequency_hz = 0.0
    if np.any(high_freq_mask):
        local_idx = int(np.argmax(psd[high_freq_mask]))
        high_freqs = freqs[high_freq_mask]
        max_noise_frequency_hz = float(high_freqs[local_idx])

    # Noise floor based on lower frequencies.
    low_freq_mask = (freqs >= 3) & (freqs < 50)
    noise_floor = float(np.median(psd[low_freq_mask])) if np.any(low_freq_mask) else 0.0
    
    # Calculate total energy in different frequency bands
    bands = {
        "5_50_hz": _get_band_energy(freqs, psd, 5, 50),
        "50_100_hz": _get_band_energy(freqs, psd, 50, 100),
        "100_250_hz": _get_band_energy(freqs, psd, 100, 250),
        "250_500_hz": _get_band_energy(freqs, psd, 250, 500),
    }
    
    # Evenly downsample for storage; avoid keeping only the lowest frequencies.
    target = min(len(freqs), 1000)
    if len(freqs) > target:
        ds_idx = np.linspace(0, len(freqs) - 1, target, dtype=int)
        freqs_out = freqs[ds_idx]
        psd_out = psd[ds_idx]
    else:
        freqs_out = freqs
        psd_out = psd

    return {
        "freqs": freqs_out.tolist(),
        "psd": psd_out.tolist(),
        "peaks": peaks,
        "dominant_frequency_hz": dominant_freq,
        "max_noise_frequency_hz": max_noise_frequency_hz,
        "noise_floor": noise_floor,
        "energy_bands": bands,
        "gyro_stats": calculate_stats(gyro_data),
    }


def _get_band_energy(freqs: np.ndarray, psd: np.ndarray, f_min: float, f_max: float) -> float:
    """
    Compute the total power spectral density (PSD) energy within the half-open frequency band [f_min, f_max).
    
    Parameters:
        freqs (np.ndarray): Array of frequency bin centers.
        psd (np.ndarray): PSD values corresponding to `freqs`.
        f_min (float): Inclusive lower bound of the frequency band (Hz).
        f_max (float): Exclusive upper bound of the frequency band (Hz).
    
    Returns:
        float: Sum of `psd` values for bins where `f_min <= freq < f_max`. Returns 0.0 if no bins fall in the band.
    """
    mask = (freqs >= f_min) & (freqs < f_max)
    if not np.any(mask):
        return 0.0
    return float(np.sum(psd[mask]))