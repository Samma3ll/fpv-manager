"""FFT noise analysis - identify resonance peaks and frequency content."""

import logging
import numpy as np
from typing import Dict, Any, Optional
from scipy import signal as scipy_signal

from .utils import extract_field_data, get_time_array, calculate_stats

logger = logging.getLogger(__name__)


def analyze_fft_noise(parser) -> Dict[str, Any]:
    """
    Analyze gyroscope time-series data with FFT to extract per-axis frequency spectra, resonance peaks, dominant frequency, noise floor, band energies, and basic statistics.
    
    Parameters:
        parser: Parser-like object providing time and gyro fields (accessed via get_time_array and extract_field_data).
    
    Returns:
        dict: Mapping each axis name ("roll", "pitch", "yaw") to either an analysis dict or an error dict.
            On success each axis dict contains:
                - "freqs": downsampled frequency bins (numpy array or list of floats)
                - "psd": downsampled power spectral density values (numpy array or list of floats)
                - "peaks": list of up to 10 peak dicts with keys "frequency_hz", "power", "power_db"
                - "dominant_frequency_hz": float
                - "noise_floor": float
                - "energy_bands": dict of band energies (e.g., "5-50", "50-100", "100-250", "250-500")
                - "gyro_stats": statistics produced by calculate_stats(gyro_data)
            If global prerequisites fail, returns {"error": "<message>"}. If an axis cannot be analyzed, that axis maps to {"error": "<message>"}.
    """
    result = {}
    
    time_array = get_time_array(parser)
    if time_array is None or len(time_array) < 2:
        logger.warning("Cannot analyze FFT: no valid time data")
        return {"error": "No valid time data"}
    
    # Calculate sampling frequency
    dt = np.mean(np.diff(time_array))
    fs = 1.0 / dt if dt > 0 else 0
    
    if fs <= 0:
        logger.warning("Invalid sampling frequency")
        return {"error": "Invalid sampling frequency"}
    
    # Analyze each axis (roll=0, pitch=1, yaw=2)
    axes = [("roll", 0), ("pitch", 1), ("yaw", 2)]
    
    for axis_name, axis_idx in axes:
        gyro_field = f"gyroADC[{axis_idx}]"
        gyro_data = extract_field_data(parser, gyro_field)
        
        if gyro_data is None:
            logger.warning(f"No gyro data for {axis_name} axis")
            result[axis_name] = {"error": f"No {axis_name} gyro data"}
            continue
        
        try:
            axis_result = _analyze_axis_fft(gyro_data, dt, axis=axis_name)
            result[axis_name] = axis_result
        except Exception as e:
            logger.error(f"Error analyzing {axis_name} FFT: {e}")
            result[axis_name] = {"error": str(e)}
    
    return result


def _analyze_axis_fft(gyro_data: np.ndarray, fs: float, axis: str = "unknown") -> Dict[str, Any]:
    """
    Analyze a single gyroscope axis using FFT to extract PSD, resonance peaks, dominant frequency, noise floor, and band energies.
    
    Parameters:
        gyro_data (np.ndarray): Time-series gyroscope samples for the axis.
        fs (float): Sampling frequency in Hz.
        axis (str): Human-readable axis name used for context (e.g., "roll", "pitch", "yaw").
    
    Returns:
        result (Dict[str, Any]): Analysis results. On success the dictionary contains:
            - "freqs": list[float] — downsampled frequency bins (Hz).
            - "psd": list[float] — downsampled power spectral density values.
            - "peaks": list[dict] — up to 10 resonance peak objects with
                "frequency_hz", "power", and "power_db".
            - "dominant_frequency_hz": float — frequency of the highest-power peak or 0.0 if none.
            - "noise_floor": float — median PSD below 50 Hz (or 0.0 if no bins).
            - "energy_bands": dict — summed PSD energy for predefined bands.
            - "gyro_stats": dict — summary statistics for the input gyro_data.
        If input is insufficient, returns {"error": "Insufficient data"}.
    """
    n = len(gyro_data)
    if n < 2:
        return {"error": "Insufficient data"}
    
    # Remove DC component and apply window
    gyro_mean_removed = gyro_data - np.mean(gyro_data)
    window = scipy_signal.windows.hann(n)
    gyro_windowed = gyro_mean_removed * window
    
    # Compute FFT
    fft_result = np.fft.rfft(gyro_windowed)
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    
    # Power spectral density (magnitude squared)
    psd = np.abs(fft_result) ** 2 / (fs * n)
    
    # Find peaks in PSD (resonances)
    # Use high threshold to find only significant peaks
    threshold_pct = 10  # Top 10% peaks
    threshold = np.percentile(psd, 100 - threshold_pct)
    
    peak_indices = np.where(psd > threshold)[0]
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
    
    # Calculate statistics
    # Identify dominant frequency (peak with highest power)
    dominant_freq = 0.0
    if len(peaks) > 0:
        dominant_freq = peaks[0]["frequency_hz"]
    
    # Calculate noise floor (median of lower frequencies)
    low_freq_mask = freqs < 50
    noise_floor = float(np.median(psd[low_freq_mask])) if np.any(low_freq_mask) else 0.0
    
    # Calculate total energy in different frequency bands
    bands = {
        "5_50_hz": _get_band_energy(freqs, psd, 5, 50),
        "50_100_hz": _get_band_energy(freqs, psd, 50, 100),
        "100_250_hz": _get_band_energy(freqs, psd, 100, 250),
        "250_500_hz": _get_band_energy(freqs, psd, 250, 500),
    }
    
    return {
        "freqs": freqs.tolist()[:len(freqs)//10],  # Downsample for storage
        "psd": psd.tolist()[:len(psd)//10],
        "peaks": peaks,
        "dominant_frequency_hz": dominant_freq,
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
