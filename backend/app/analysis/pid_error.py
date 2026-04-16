"""PID error tracking - measure control errors and PID performance."""

import logging
import numpy as np
from typing import Dict, Any, Optional

from .utils import extract_field_data, calculate_stats, calculate_rms

logger = logging.getLogger(__name__)


def analyze_pid_error(parser) -> Dict[str, Any]:
    """
    Analyze PID control error for each axis.
    
    This measures:
    - RMS error: Root mean square of error signal
    - Max error: Maximum error magnitude
    - Mean absolute error: Average absolute error
    - Error drift: Trend in error over time
    
    Args:
        parser: orangebox Parser instance
        
    Returns:
        Dict with keys for each axis: {
            "roll": {"rms_error": ..., "max_error": ..., "mean_abs_error": ...},
            "pitch": {...},
            "yaw": {...}
        }
    """
    result = {}
    
    # Analyze each axis (roll=0, pitch=1, yaw=2)
    axes = [("roll", 0), ("pitch", 1), ("yaw", 2)]
    
    for axis_name, axis_idx in axes:
        # Use setpoint as the desired output (more stable than rcCommand)
        rate_field = f"setpoint[{axis_idx}]"
        gyro_field = f"gyroADC[{axis_idx}]"
        
        rate_cmd = extract_field_data(parser, rate_field)
        gyro_data = extract_field_data(parser, gyro_field)
        
        if gyro_data is None or rate_cmd is None:
            logger.warning(f"Missing data for {axis_name} axis")
            result[axis_name] = {"error": f"Missing {axis_name} data"}
            continue
        
        try:
            # Calculate error as difference between commanded and actual
            # Need to ensure arrays are same length
            min_len = min(len(gyro_data), len(rate_cmd))
            error = rate_cmd[:min_len] - gyro_data[:min_len]
            
            axis_result = _analyze_axis_error(error, axis=axis_name)
            result[axis_name] = axis_result
        except Exception as e:
            logger.error(f"Error analyzing {axis_name} PID error: {e}")
            result[axis_name] = {"error": str(e)}
    
    return result


def _analyze_axis_error(error: np.ndarray, axis: str = "unknown") -> Dict[str, Any]:
    """
    Analyze error characteristics for a single axis.
    
    Args:
        error: Error array (command - actual)
        axis: Axis name for logging
        
    Returns:
        Analysis results dict
    """
    if len(error) < 1:
        return {"error": "No error data"}
    
    # Remove any NaN values
    error_clean = error[~np.isnan(error)]
    
    if len(error_clean) < 1:
        return {"error": "No valid error data"}
    
    # Calculate metrics
    rms_error = calculate_rms(error_clean)
    max_error = float(np.max(np.abs(error_clean)))
    mean_abs_error = float(np.mean(np.abs(error_clean)))
    
    # Error statistics
    error_stats = calculate_stats(error_clean)
    
    # Calculate error drift (trend over time)
    # Divide signal into 10 chunks and check if error is increasing/decreasing
    chunk_size = len(error_clean) // 10
    drift = 0.0
    
    if chunk_size > 1:
        chunk_means = []
        for i in range(10):
            start = i * chunk_size
            end = (i + 1) * chunk_size if i < 9 else len(error_clean)
            if start < end:
                chunk_means.append(np.mean(np.abs(error_clean[start:end])))
        
        if len(chunk_means) > 1:
            # Calculate trend using linear fit
            x = np.arange(len(chunk_means))
            z = np.polyfit(x, chunk_means, 1)
            drift = float(z[0])  # Slope of trend
    
    # Proportional/Integral/Derivative-like error breakdown
    error_deriv = np.diff(error_clean)
    
    result = {
        "rms_error": rms_error,
        "max_error": max_error,
        "mean_abs_error": mean_abs_error,
        "error_stats": error_stats,
        "error_drift": drift,  # Positive = increasing error, negative = decreasing
        "error_derivative_rms": calculate_rms(error_deriv) if len(error_deriv) > 0 else 0.0,
    }
    
    # Calculate error percentiles
    result["error_percentiles"] = {
        "p50": float(np.percentile(np.abs(error_clean), 50)),
        "p75": float(np.percentile(np.abs(error_clean), 75)),
        "p90": float(np.percentile(np.abs(error_clean), 90)),
        "p99": float(np.percentile(np.abs(error_clean), 99)),
    }
    
    return result
