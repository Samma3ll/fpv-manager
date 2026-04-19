"""PID error tracking - measure control errors and PID performance."""

import logging
import numpy as np
from typing import Dict, Any, Optional

from .utils import extract_fields, calculate_stats, calculate_rms

logger = logging.getLogger(__name__)


def analyze_pid_error(parser) -> Dict[str, Any]:
    """
    Analyze PID control error for roll, pitch, and yaw axes.
    
    For each axis, computes the error between commanded rate (`setpoint[i]`) and measured rate (`gyroADC[i]`) and returns per-axis metrics such as RMS error, maximum absolute error, mean absolute error, error drift (trend), derivative-like RMS, percentile magnitudes (p50/p75/p90/p99), and additional summary statistics.
    
    Parameters:
        parser: Parser instance that provides time-series fields (must supply `setpoint[i]` and `gyroADC[i]`).
    
    Returns:
        A dict with keys "roll", "pitch", and "yaw". Each value is either a metrics dict containing the computed error statistics or an `{"error": "<message>"}` dict when data is missing or analysis failed.
    """
    result = {}
    
    requested_fields = []
    for axis_idx in range(3):
        requested_fields.append(f"gyroADC[{axis_idx}]")
        if f"setpoint[{axis_idx}]" in parser.field_names:
            requested_fields.append(f"setpoint[{axis_idx}]")
        if f"axisError[{axis_idx}]" in parser.field_names:
            requested_fields.append(f"axisError[{axis_idx}]")

    fields = extract_fields(parser, requested_fields)

    # Analyze each axis (roll=0, pitch=1, yaw=2)
    axes = [("roll", 0), ("pitch", 1), ("yaw", 2)]
    
    for axis_name, axis_idx in axes:
        # Use setpoint as the desired output (more stable than rcCommand)
        rate_field = f"setpoint[{axis_idx}]"
        gyro_field = f"gyroADC[{axis_idx}]"
        
        rate_cmd = fields.get(rate_field)
        gyro_data = fields.get(gyro_field)
        
        if gyro_data is None or rate_cmd is None:
            logger.warning(f"Missing data for {axis_name} axis")
            result[axis_name] = {"error": f"Missing {axis_name} data"}
            continue
        
        try:
            axis_error_field = f"axisError[{axis_idx}]"
            axis_error_data = fields.get(axis_error_field)

            min_len = min(len(gyro_data), len(rate_cmd))
            if axis_error_data is not None and len(axis_error_data) > 0:
                min_len = min(min_len, len(axis_error_data))
                error = axis_error_data[:min_len]
                error_source = axis_error_field
            else:
                # Fall back to setpoint - gyro if axisError is not logged.
                error = rate_cmd[:min_len] - gyro_data[:min_len]
                error_source = "setpoint_minus_gyro"
            
            axis_result = _analyze_axis_error(error, axis=axis_name)
            axis_result["error_source"] = error_source
            axis_result["error_vs_setpoint"] = _error_vs_setpoint(
                error,
                rate_cmd[:min_len],
            )
            result[axis_name] = axis_result
        except Exception as e:
            logger.error(f"Error analyzing {axis_name} PID error: {e}")
            result[axis_name] = {"error": str(e)}
    
    return result


def _analyze_axis_error(error: np.ndarray, axis: str = "unknown") -> Dict[str, Any]:
    """
    Compute a set of error metrics for a single control axis from a 1-D error signal.
    
    Parameters:
        error (np.ndarray): Array of error values (commanded - measured) for the axis; NaN values will be ignored.
        axis (str): Optional axis name used for context in results (e.g., "roll", "pitch", "yaw").
    
    Returns:
        Dict[str, Any]: Dictionary with computed metrics or an error entry when input is empty/invalid. When successful, the dictionary contains:
            - "rms_error" (float): Root-mean-square of the error signal.
            - "max_error" (float): Maximum absolute error.
            - "mean_abs_error" (float): Mean of the absolute error.
            - "error_stats" (dict): Additional summary statistics produced by calculate_stats for the raw error array.
            - "error_drift" (float): Trend slope of per-chunk mean absolute error (positive = increasing magnitude, negative = decreasing).
            - "error_derivative_rms" (float): RMS of the first difference of the error signal (derivative-like metric).
            - "error_percentiles" (dict): Absolute-error percentiles with keys "p50", "p75", "p90", and "p99" (all floats).
        If the input contains no samples or no valid (non-NaN) values, returns {"error": "No error data"} or {"error": "No valid error data"} respectively.
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


def _error_vs_setpoint(error: np.ndarray, setpoint: np.ndarray) -> Dict[str, Any]:
    """
    Produce bin-wise aggregation of absolute tracking error grouped by absolute setpoint magnitude.
    
    Parameters:
        error (np.ndarray): 1-D array of tracking errors aligned with `setpoint`.
        setpoint (np.ndarray): 1-D array of commanded rates; absolute values define bin membership.
    
    Returns:
        Dict[str, Any]: A dictionary with key `"bins"` containing a list of bin records. Each record has:
            - `setpoint_min` (float): lower bound of the bin (inclusive).
            - `setpoint_max` (float): upper bound of the bin (inclusive for the final bin, exclusive otherwise).
            - `mean_abs_error` (float): mean of absolute errors for samples in the bin.
            - `sample_count` (int): number of samples in the bin.
        Returns `{"bins": []}` when inputs are empty or when the maximum absolute setpoint is non-positive.
    """
    if len(error) == 0 or len(setpoint) == 0:
        return {"bins": []}

    n = min(len(error), len(setpoint))
    error_aligned = error[:n]
    setpoint_aligned = setpoint[:n]

    # Filter to finite samples only
    finite_mask = np.isfinite(error_aligned) & np.isfinite(setpoint_aligned)
    error_aligned = error_aligned[finite_mask]
    setpoint_aligned = setpoint_aligned[finite_mask]

    if len(error_aligned) == 0:
        return {"bins": []}

    n = len(error_aligned)
    abs_err = np.abs(error_aligned)
    abs_sp = np.abs(setpoint_aligned)

    max_sp = float(np.max(abs_sp)) if n > 0 else 0.0
    if max_sp <= 0:
        return {"bins": []}

    bin_count = 20
    edges = np.linspace(0.0, max_sp, bin_count + 1)
    bins = []
    for i in range(bin_count):
        lo = edges[i]
        hi = edges[i + 1]
        if i == bin_count - 1:
            mask = (abs_sp >= lo) & (abs_sp <= hi)
        else:
            mask = (abs_sp >= lo) & (abs_sp < hi)
        if not np.any(mask):
            continue
        bins.append(
            {
                "setpoint_min": float(lo),
                "setpoint_max": float(hi),
                "mean_abs_error": float(np.mean(abs_err[mask])),
                "sample_count": int(np.sum(mask)),
            }
        )

    return {"bins": bins}