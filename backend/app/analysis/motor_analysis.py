"""Motor output analysis - analyze motor performance and balance."""

import logging
import numpy as np
from typing import Dict, Any, Optional, List

from .utils import extract_field_data, calculate_stats, calculate_rms, find_peaks

logger = logging.getLogger(__name__)


def analyze_motor_output(parser) -> Dict[str, Any]:
    """
    Analyze motor output characteristics to identify imbalance and resonance.
    
    This measures:
    - Average motor output for each motor
    - Min/max output range
    - Motor imbalance (deviation from ideal)
    - Resonance peaks in motor output
    - Motor output correlation
    
    Args:
        parser: orangebox Parser instance
        
    Returns:
        Analysis results dict
    """
    result = {
        "motors": {},
        "overall": {},
    }
    
    # Find motor outputs
    motor_fields = []
    for i in range(4):  # Typical 4-motor quad
        motor_field = f"motor[{i}]"
        if motor_field in parser.field_names:
            motor_fields.append((i, motor_field))
    
    if not motor_fields:
        logger.warning("No motor fields found")
        return {"error": "No motor data found"}
    
    # Analyze each motor
    motor_data_list = []
    
    for motor_idx, motor_field in motor_fields:
        motor_data = extract_field_data(parser, motor_field)
        
        if motor_data is None:
            logger.warning(f"Could not extract {motor_field}")
            continue
        
        motor_data_list.append((motor_idx, motor_data))
        
        try:
            motor_result = _analyze_motor(motor_data, motor_idx)
            result["motors"][f"motor_{motor_idx}"] = motor_result
        except Exception as e:
            logger.error(f"Error analyzing motor {motor_idx}: {e}")
            result["motors"][f"motor_{motor_idx}"] = {"error": str(e)}
    
    # Analyze overall characteristics
    if len(motor_data_list) >= 2:
        try:
            overall = _analyze_overall_motors(motor_data_list)
            result["overall"] = overall
        except Exception as e:
            logger.error(f"Error analyzing overall motors: {e}")
            result["overall"] = {"error": str(e)}
    
    return result


def _analyze_motor(motor_data: np.ndarray, motor_idx: int) -> Dict[str, Any]:
    """
    Analyze a single motor output.
    
    Args:
        motor_data: Motor output values
        motor_idx: Motor index
        
    Returns:
        Analysis results dict
    """
    # Remove invalid data
    motor_clean = motor_data[~np.isnan(motor_data)]
    
    if len(motor_clean) < 1:
        return {"error": "No valid motor data"}
    
    # Basic statistics
    stats = calculate_stats(motor_clean)
    
    # Determine idle throttle and active range
    # Assume first 100 samples are relatively stable (idle or low throttle)
    sample_window = min(100, len(motor_clean) // 10)
    if sample_window > 0:
        idle_estimate = np.mean(motor_clean[:sample_window])
    else:
        idle_estimate = np.min(motor_clean)
    
    # Active output (above idle)
    active_threshold = idle_estimate + 0.1 * (np.max(motor_clean) - idle_estimate)
    active_data = motor_clean[motor_clean > active_threshold]
    
    active_stats = {}
    if len(active_data) > 0:
        active_stats = calculate_stats(active_data)
    
    # Find throttle spikes/changes (indicating input)
    throttle_derivative = np.abs(np.diff(motor_clean))
    spike_threshold = np.percentile(throttle_derivative, 90)
    spikes = np.where(throttle_derivative > spike_threshold)[0]
    
    result = {
        "avg_output": stats["mean"],
        "min_output": stats["min"],
        "max_output": stats["max"],
        "output_range": stats["max"] - stats["min"],
        "rms_output": stats["rms"],
        "output_std": stats["std"],
        "idle_estimate": float(idle_estimate),
        "activity_level": float(len(active_data) / len(motor_clean)) if len(motor_clean) > 0 else 0.0,
        "throttle_changes": len(spikes),
    }
    
    if len(active_data) > 0:
        result["active_output_stats"] = active_stats
    
    return result


def _analyze_overall_motors(motor_data_list: List[tuple]) -> Dict[str, Any]:
    """
    Analyze overall motor characteristics and balance.
    
    Args:
        motor_data_list: List of (motor_idx, motor_data) tuples
        
    Returns:
        Analysis results dict
    """
    result = {}
    
    if len(motor_data_list) < 2:
        return result
    
    # Calculate average output across all motors for each sample
    min_len = min(len(data) for _, data in motor_data_list)
    motor_means = np.array([np.mean(data[:min_len]) for _, data in motor_data_list])
    motor_stds = np.array([np.std(data[:min_len]) for _, data in motor_data_list])
    
    # Motor imbalance: coefficient of variation
    overall_mean = np.mean(motor_means)
    if overall_mean > 0:
        imbalance = float(np.std(motor_means) / overall_mean * 100)
    else:
        imbalance = 0.0
    
    result["imbalance_pct"] = imbalance
    
    # Check for motor synchronization
    # Calculate correlation between motor outputs
    if len(motor_data_list) == 4:
        correlations = []
        for i in range(4):
            for j in range(i + 1, 4):
                _, data_i = motor_data_list[i]
                _, data_j = motor_data_list[j]
                
                min_len = min(len(data_i), len(data_j))
                if min_len > 0:
                    corr = float(np.corrcoef(data_i[:min_len], data_j[:min_len])[0, 1])
                    correlations.append(corr)
        
        if correlations:
            result["motor_correlation_mean"] = float(np.mean(correlations))
            result["motor_correlation_min"] = float(np.min(correlations))
            result["motor_correlation_max"] = float(np.max(correlations))
    
    # Output deviation from ideal
    # Ideal: all motors at same level
    deviations = []
    for _, motor_data in motor_data_list:
        min_len = min(len(motor_data), min_len)
        deviation = np.mean(motor_data[:min_len]) - overall_mean
        deviations.append(deviation)
    
    result["motor_deviations"] = [float(d) for d in deviations]
    result["max_deviation"] = float(max(np.abs(deviations)))
    
    # Resonance in motor outputs
    # Check if there are common frequency peaks across motors
    resonance_peaks = _find_motor_resonances(motor_data_list)
    result["potential_resonance_peaks"] = resonance_peaks
    
    return result


def _find_motor_resonances(motor_data_list: List[tuple], fs: float = 8000) -> List[float]:
    """
    Find common resonance peaks across motor outputs.
    
    Args:
        motor_data_list: List of (motor_idx, motor_data) tuples
        fs: Sampling frequency in Hz (approximate)
        
    Returns:
        List of resonant frequencies
    """
    try:
        from scipy import signal as scipy_signal
        
        resonances = []
        
        if len(motor_data_list) < 2:
            return resonances
        
        # Get FFT for each motor
        peak_freqs_all = []
        
        for _, motor_data in motor_data_list:
            if len(motor_data) < 10:
                continue
            
            # FFT
            fft_result = np.fft.rfft(motor_data - np.mean(motor_data))
            freqs = np.fft.rfftfreq(len(motor_data), 1.0 / fs)
            psd = np.abs(fft_result) ** 2
            
            # Find peaks
            peak_threshold = np.percentile(psd, 90)
            peak_indices = np.where(psd > peak_threshold)[0]
            peak_freqs = freqs[peak_indices]
            peak_freqs = peak_freqs[(peak_freqs > 10) & (peak_freqs < 500)]  # Reasonable range
            
            peak_freqs_all.append(peak_freqs)
        
        # Find common peaks (frequencies that appear in multiple motors)
        if len(peak_freqs_all) >= 2:
            # Use histogram to find common frequencies
            all_peaks = np.concatenate(peak_freqs_all)
            hist, bin_edges = np.histogram(all_peaks, bins=50)
            
            # Find bins with peaks from multiple motors
            for i in range(len(hist)):
                if hist[i] >= len(peak_freqs_all) // 2:  # At least half the motors
                    freq = (bin_edges[i] + bin_edges[i + 1]) / 2
                    resonances.append(float(freq))
        
        return sorted(resonances)
    
    except Exception as e:
        logger.warning(f"Could not analyze motor resonances: {e}")
        return []
