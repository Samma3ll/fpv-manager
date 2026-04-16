"""Step response analysis - measure quad response to stick inputs."""

import logging
import numpy as np
from typing import Dict, Any, Optional, List
from scipy import signal as scipy_signal

from .utils import (
    extract_field_data, 
    get_time_array, 
    find_peaks, 
    normalize_signal,
    calculate_derivative,
    calculate_stats,
)

logger = logging.getLogger(__name__)


def analyze_step_response(parser) -> Dict[str, Any]:
    """
    Compute step-response metrics for roll, pitch, and yaw from the parser's time-series data.
    
    Validates the common time axis and sample interval, then for each axis extracts `gyroADC[index]` and `rcCommand[index]` to produce a per-axis analysis. Each axis entry contains averaged step metrics (e.g., `rise_time_ms`, `overshoot_pct`, `settling_time_ms`, `ringing`) and overall gyro statistics, or an `error`/`warning` entry when analysis cannot be performed.
    
    Parameters:
        parser: orangebox Parser instance supplying time, `gyroADC[...]`, and `rcCommand[...]` fields.
    
    Returns:
        result (Dict[str, Any]): Mapping of axis names ("roll", "pitch", "yaw") to their analysis dictionaries or error/warning payloads.
    """
    result = {}
    
    time_array = get_time_array(parser)
    if time_array is None or len(time_array) < 2:
        logger.warning("Cannot analyze step response: no valid time data")
        return {"error": "No valid time data"}
    
    dt = np.mean(np.diff(time_array))
    if dt <= 0:
        logger.warning("Invalid time step")
        return {"error": "Invalid time step"}
    
    # Analyze each axis (roll=0, pitch=1, yaw=2)
    axes = [("roll", 0), ("pitch", 1), ("yaw", 2)]
    
    for axis_name, axis_idx in axes:
        gyro_field = f"gyroADC[{axis_idx}]"
        rate_field = f"rcCommand[{axis_idx}]"
        
        gyro_data = extract_field_data(parser, gyro_field)
        rate_cmd = extract_field_data(parser, rate_field)
        
        if gyro_data is None or rate_cmd is None:
            logger.warning(f"Missing data for {axis_name} axis: gyro={gyro_data is not None}, rate_cmd={rate_cmd is not None}")
            result[axis_name] = {"error": f"Missing {axis_name} data"}
            continue
        
        # Analyze step response for this axis
        try:
            axis_result = _analyze_axis_response(
                gyro_data, 
                rate_cmd, 
                dt,
                axis=axis_name
            )
            result[axis_name] = axis_result
        except Exception as e:
            logger.error(f"Error analyzing {axis_name} step response: {e}")
            result[axis_name] = {"error": str(e)}
    
    return result


def _analyze_axis_response(
    gyro_data: np.ndarray,
    rate_cmd: np.ndarray,
    dt: float,
    axis: str = "unknown"
) -> Dict[str, Any]:
    """
    Detects stick-induced step inputs in the rate command and summarizes gyro step-response metrics for a single axis.
    
    Analyzes regions where the rate command changes abruptly, computes per-step metrics (rise time, overshoot, settling time, ringing) from corresponding gyro segments, and returns the averaged metrics together with the number of steps analyzed and overall gyro statistics. If no step inputs or no clear step responses are found, the result will contain a `warning` entry and overall gyro statistics.
    
    Parameters:
        gyro_data (np.ndarray): Time-series gyroscope measurements for the axis.
        rate_cmd (np.ndarray): Time-series rate command (stick) corresponding to the same time base as `gyro_data`.
        dt (float): Sample interval in seconds.
        axis (str): Human-readable axis name used for logging and messages.
    
    Returns:
        Dict[str, Any]: A dictionary containing either:
          - Averaged metrics:
              - `rise_time_ms` (float): Mean rise time to 90% of steady state across detected steps, in milliseconds.
              - `overshoot_pct` (float): Mean overshoot percentage relative to steady state.
              - `settling_time_ms` (float): Mean settling time within the 2% band, in milliseconds.
              - `ringing` (float): Mean count of post-settling peaks.
              - `steps_analyzed` (int): Number of step responses included in the averages.
              - `gyro_stats` (dict): Summary statistics of the provided gyro data.
          - Or, when no steps are found:
              - A dict containing a `warning` string and `gyro_stats`.
          - Or, when step inputs are not detected at all:
              - A dict containing a `warning` string indicating no step inputs detected.
    """
    # Find step input regions (where rate_cmd changes significantly)
    rate_cmd_derivative = calculate_derivative(rate_cmd, dt)
    rate_threshold = 0.3 * np.max(np.abs(rate_cmd_derivative))
    
    # Find indices where rate command changes
    step_indices = np.where(np.abs(rate_cmd_derivative) > rate_threshold)[0]
    
    if len(step_indices) == 0:
        logger.warning(f"{axis}: No step inputs detected")
        return {"warning": "No step inputs detected"}
    
    # Analyze multiple steps
    steps_analysis = []
    min_step_spacing = int(0.5 / dt)  # Minimum 0.5 seconds between steps
    
    i = 0
    while i < len(step_indices):
        start_idx = step_indices[i]
        
        # Find end of this step region
        end_idx = start_idx + int(1.0 / dt)  # Analyze 1 second after step
        end_idx = min(end_idx, len(gyro_data) - 1)
        
        if end_idx - start_idx < int(0.1 / dt):  # Need at least 0.1s of data
            i += 1
            continue
        
        # Analyze this step
        step_data = gyro_data[start_idx:end_idx]
        step_result = _analyze_single_step(step_data, dt)

        if step_result and "rise_time_ms" in step_result:
            steps_analysis.append(step_result)

        # Skip ahead to avoid overlapping steps
        threshold_idx = start_idx + min_step_spacing
        while i < len(step_indices) and step_indices[i] <= threshold_idx:
            i += 1
    
    if not steps_analysis:
        # Return overall statistics if no clear steps found
        return {"warning": "No clear step responses", **calculate_stats(gyro_data)}
    
    # Average results across all detected steps
    result = {
        "rise_time_ms": float(np.mean([s.get("rise_time_ms", 0) for s in steps_analysis])),
        "overshoot_pct": float(np.mean([s.get("overshoot_pct", 0) for s in steps_analysis])),
        "settling_time_ms": float(np.mean([s.get("settling_time_ms", 0) for s in steps_analysis])),
        "ringing": float(np.mean([s.get("ringing", 0) for s in steps_analysis])),
        "steps_analyzed": len(steps_analysis),
        "gyro_stats": calculate_stats(gyro_data),
    }
    
    return result


def _analyze_single_step(step_signal: np.ndarray, dt: float) -> Dict[str, Any]:
    """
    Measure rise time, overshoot, settling time, and ringing of a single gyro step-response segment.
    
    Parameters:
        step_signal (np.ndarray): Gyro signal for the step-response window.
        dt (float): Sample interval in seconds.
    
    Returns:
        dict: Analysis metrics with the following keys:
            - rise_time_ms (float): Time in milliseconds to first reach 90% of the estimated steady-state.
            - overshoot_pct (float): Percent overshoot relative to the steady-state (0.0 if steady-state is zero or no overshoot).
            - settling_time_ms (float): Time in milliseconds to first enter and remain within a ±2% band around steady-state after the initial 10% of the window (0.0 if not settled).
            - ringing (float): Count of detected peaks after settling (0.0 if none or not settled).
    """
    # Normalize to get response characteristics
    signal_normalized = normalize_signal(step_signal)

    # Find steady-state value (last 20% of signal)
    steady_state = np.mean(signal_normalized[-int(0.2 * len(signal_normalized)):])

    # Rise time: time to reach 90% of steady state (sign-aware)
    target_90 = 0.9 * steady_state
    if steady_state >= 0:
        rise_indices = np.where(signal_normalized >= target_90)[0]
    else:
        rise_indices = np.where(signal_normalized <= target_90)[0]
    rise_time_ms = float(rise_indices[0] * dt * 1000) if len(rise_indices) > 0 else 0.0

    # Overshoot: peak value minus steady state (protect against near-zero steady state)
    peak_value = np.max(signal_normalized)
    if abs(steady_state) < 1e-8:
        overshoot_pct = 0.0
    else:
        overshoot_pct = max(0.0, (peak_value - steady_state) / abs(steady_state) * 100)

    # Settling time: time to settle within 2% of steady state
    settling_band = 0.02 * abs(steady_state)
    settled_indices = np.where(np.abs(signal_normalized - steady_state) < settling_band)[0]
    
    settling_time_ms = 0.0
    if len(settled_indices) > 0:
        # Find first index where signal settles
        for idx in settled_indices:
            if idx > int(0.1 * len(signal_normalized)):  # After 10% of window
                settling_time_ms = float(idx * dt * 1000)
                break
    
    # Ringing: count peaks after settling
    ringing = 0.0
    if settling_time_ms > 0:
        settling_idx = int(settling_time_ms / (dt * 1000))
        post_settle_signal = signal_normalized[settling_idx:]
        if len(post_settle_signal) > 0:
            peaks = find_peaks(post_settle_signal, threshold=0.1)
            ringing = float(len(peaks))
    
    return {
        "rise_time_ms": rise_time_ms,
        "overshoot_pct": float(overshoot_pct),
        "settling_time_ms": settling_time_ms,
        "ringing": ringing,
    }