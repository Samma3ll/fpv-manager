"""Tune quality scoring - overall assessment of PID tuning quality."""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def score_tune_quality(
    step_response: Dict[str, Any],
    fft_noise: Dict[str, Any],
    pid_error: Dict[str, Any],
    motor_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate an overall tune quality score based on all analyses.
    
    Scoring criteria:
    - Step Response: Lower is better for overshoot, settling time. Higher is better for rise time.
    - FFT Noise: Lower resonance peaks indicate cleaner tuning
    - PID Error: Lower error indicates better control
    - Motor Analysis: Lower imbalance indicates better motor balance
    
    Args:
        step_response: Step response analysis results
        fft_noise: FFT noise analysis results
        pid_error: PID error analysis results
        motor_analysis: Motor output analysis results
        
    Returns:
        Dict with scores for each axis and overall score
    """
    result = {
        "roll_score": 0.0,
        "pitch_score": 0.0,
        "yaw_score": 0.0,
        "overall_score": 0.0,
        "details": {},
    }
    
    try:
        # Score each axis
        for axis in ["roll", "pitch", "yaw"]:
            axis_score = _score_axis(
                axis,
                step_response.get(axis, {}),
                fft_noise.get(axis, {}),
                pid_error.get(axis, {}),
            )
            result[f"{axis}_score"] = axis_score["score"]
            result["details"][axis] = axis_score
        
        # Overall score (average + motor balance penalty)
        axis_scores = [
            result["roll_score"],
            result["pitch_score"],
            result["yaw_score"],
        ]
        overall = sum(axis_scores) / len(axis_scores) if axis_scores else 0.0
        
        # Apply motor balance penalty
        motor_penalty = _get_motor_penalty(motor_analysis)
        overall = overall * (1.0 - motor_penalty)
        
        # Clamp to 0-100
        result["overall_score"] = max(0.0, min(100.0, overall))
        result["motor_penalty"] = motor_penalty
        
    except Exception as e:
        logger.error(f"Error scoring tune quality: {e}")
        result["error"] = str(e)
    
    return result


def _score_axis(
    axis: str,
    step_response: Dict[str, Any],
    fft_noise: Dict[str, Any],
    pid_error: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Score a single axis based on all analyses.
    
    Returns score from 0-100 where 100 is excellent.
    """
    score = 100.0
    components = {}
    
    # Step response scoring
    sr_score = _score_step_response(step_response)
    components["step_response"] = sr_score
    score -= (100 - sr_score) * 0.35  # 35% weight
    
    # FFT noise scoring
    fft_score = _score_fft_noise(fft_noise)
    components["fft_noise"] = fft_score
    score -= (100 - fft_score) * 0.25  # 25% weight
    
    # PID error scoring
    error_score = _score_pid_error(pid_error)
    components["pid_error"] = error_score
    score -= (100 - error_score) * 0.40  # 40% weight
    
    # Clamp to 0-100
    score = max(0.0, min(100.0, score))
    
    return {
        "score": score,
        "components": components,
    }


def _score_step_response(step_response: Dict[str, Any]) -> float:
    """Score step response characteristics."""
    if "error" in step_response:
        return 50.0  # Neutral score if data unavailable
    
    score = 100.0
    
    # Rise time: ideal 50-200ms
    rise_time = step_response.get("rise_time_ms", 0)
    if rise_time < 50:
        rise_penalty = (50 - rise_time) / 50 * 10  # Too fast
    elif rise_time > 200:
        rise_penalty = min(20, (rise_time - 200) / 100 * 20)  # Too slow
    else:
        rise_penalty = 0  # Ideal range
    score -= rise_penalty
    
    # Overshoot: ideal < 5%
    overshoot = step_response.get("overshoot_pct", 0)
    overshoot_penalty = min(30, overshoot / 2)  # Each 2% = 1 point
    score -= overshoot_penalty
    
    # Settling time: ideal < 500ms
    settling = step_response.get("settling_time_ms", 0)
    if settling > 500:
        settling_penalty = min(20, (settling - 500) / 100 * 20)
    else:
        settling_penalty = 0
    score -= settling_penalty
    
    # Ringing: ideal 0-1 oscillations
    ringing = step_response.get("ringing", 0)
    ringing_penalty = min(15, ringing * 5)  # Each oscillation = 5 points
    score -= ringing_penalty
    
    return max(0.0, min(100.0, score))


def _score_fft_noise(fft_noise: Dict[str, Any]) -> float:
    """Score frequency domain characteristics."""
    if "error" in fft_noise:
        return 50.0  # Neutral score
    
    score = 100.0
    
    # Check for resonance peaks
    peaks = fft_noise.get("peaks", [])
    
    if peaks:
        # Score based on number and amplitude of peaks
        peak_penalty = 0.0
        
        for peak in peaks[:5]:  # Consider only top 5 peaks
            power_db = peak.get("power_db", -120)
            
            # Peaks above -60dB are concerning
            if power_db > -60:
                peak_penalty += min(20, (-60 - power_db) / 5)
        
        score -= min(30, peak_penalty)
    
    # Check noise floor
    noise_floor = fft_noise.get("noise_floor", 0)
    if noise_floor > 0.1:  # High noise floor is bad
        noise_penalty = min(15, noise_floor * 50)
        score -= noise_penalty
    
    # Check energy distribution
    bands = fft_noise.get("energy_bands", {})
    if bands:
        # Ideal: most energy in low frequencies, less in high
        low_energy = bands.get("5_50_hz", 0)
        high_energy = bands.get("250_500_hz", 0)
        
        if low_energy > 0 and high_energy > 0:
            ratio = high_energy / low_energy
            if ratio > 0.5:  # Too much high-frequency energy
                ratio_penalty = min(20, (ratio - 0.5) * 20)
                score -= ratio_penalty
    
    return max(0.0, min(100.0, score))


def _score_pid_error(pid_error: Dict[str, Any]) -> float:
    """Score PID control error."""
    if "error" in pid_error:
        return 50.0  # Neutral score
    
    score = 100.0
    
    # RMS error: lower is better
    rms = pid_error.get("rms_error", 0)
    # Ideal RMS < 5 degrees/sec
    if rms > 5:
        rms_penalty = min(30, (rms - 5) / 2)  # Each 2 deg/s = 1 point
    else:
        rms_penalty = 0
    score -= rms_penalty
    
    # Max error: lower is better
    max_error = pid_error.get("max_error", 0)
    # Ideal max < 20 degrees/sec
    if max_error > 20:
        max_penalty = min(20, (max_error - 20) / 5)  # Each 5 deg/s = 1 point
    else:
        max_penalty = 0
    score -= max_penalty
    
    # Error drift: smaller is better
    drift = pid_error.get("error_drift", 0)
    if abs(drift) > 0.1:
        drift_penalty = min(15, abs(drift) * 30)
    else:
        drift_penalty = 0
    score -= drift_penalty
    
    return max(0.0, min(100.0, score))


def _get_motor_penalty(motor_analysis: Dict[str, Any]) -> float:
    """Get penalty for motor imbalance (0 = no penalty, 1 = full penalty)."""
    try:
        overall = motor_analysis.get("overall", {})
        imbalance = overall.get("imbalance_pct", 0)
        
        # Ideal: imbalance < 5%
        if imbalance < 5:
            return 0.0
        elif imbalance > 20:
            return 0.2  # Maximum 20% penalty
        else:
            return (imbalance - 5) / 75 * 0.2
    except Exception as e:
        logger.warning(f"Could not calculate motor penalty: {e}")
        return 0.0
