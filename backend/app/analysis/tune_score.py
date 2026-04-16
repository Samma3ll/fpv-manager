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
    Compute a 0–100 tune quality score for each axis and an aggregated overall score.
    
    Produces per-axis scores for roll, pitch, and yaw based on provided analyses, averages the three axis scores, applies a motor imbalance penalty to the average, clamps the final overall score to the range 0–100, and returns detailed component breakdowns. On internal failure the returned dict will include an "error" string and any partially computed results.
    
    Parameters:
        step_response (Dict[str, Any]): Per-axis step response analysis results.
        fft_noise (Dict[str, Any]): Per-axis FFT noise analysis results.
        pid_error (Dict[str, Any]): Per-axis PID error analysis results.
        motor_analysis (Dict[str, Any]): Motor balance/imbalance analysis used to compute a motor penalty.
    
    Returns:
        Dict[str, Any]: A dictionary containing:
            - "roll_score", "pitch_score", "yaw_score" (float): Per-axis scores in 0–100.
            - "overall_score" (float): Aggregated score after motor penalty, clamped to 0–100.
            - "motor_penalty" (float): Applied penalty fraction (0.0–0.2).
            - "details" (dict): Per-axis detailed scoring components and intermediate values.
            - "error" (str, optional): Error message if scoring failed.
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
    Compute an aggregate quality score for a single control axis using step response, FFT noise, and PID error analyses.
    
    The function combines per-component scores into a final score and clamps the result to the range 0.0–100.0.
    
    Returns:
        result (dict): A dictionary containing:
            - score (float): Aggregate axis score between 0.0 and 100.0.
            - components (dict): Per-component scores with keys
              'step_response', 'fft_noise', and 'pid_error' (each a float 0.0–100.0).
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
    """
    Compute a 0–100 quality score for a step response based on rise time, overshoot, settling time, and ringing.

    Evaluates the provided step_response metrics to deduct penalties from an initial perfect score. If step_response contains an "error" or "warning" key, a neutral score of 50.0 is returned. The following properties influence the score:
    - rise_time_ms: penalizes responses that are too fast or too slow relative to an ideal range.
    - overshoot_pct: penalizes excessive overshoot.
    - settling_time_ms: penalizes long settling times.
    - ringing: penalizes sustained oscillations.
    The final score is clamped to the range 0.0–100.0.

    Parameters:
        step_response (Dict[str, Any]): Step response metrics dictionary containing optional keys
            "rise_time_ms", "overshoot_pct", "settling_time_ms", "ringing", or an "error"/"warning" key.

    Returns:
        float: Quality score between 0.0 and 100.0; `50.0` if `step_response` contains an "error" or "warning" key.
    """
    if "error" in step_response or "warning" in step_response:
        return 50.0  # Neutral score if data unavailable

    score = 100.0

    # Rise time: ideal 50-200ms
    rise_time = step_response.get("rise_time_ms", 0)
    if rise_time > 0:
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
    """
    Evaluate frequency-domain noise characteristics and produce a 0–100 quality score for FFT-based analysis.

    Parameters:
        fft_noise (Dict[str, Any]): Frequency-domain analysis data. Expected keys:
            - "error" or "warning": optional; if present, a neutral score is returned.
            - "peaks": optional list of peak dicts with "power_db".
            - "noise_floor": optional numeric noise floor.
            - "energy_bands": optional dict with keys like "5_50_hz" and "250_500_hz" for low/high band energies.

    Returns:
        float: A score between 0.0 and 100.0 where higher values indicate cleaner frequency-domain characteristics; returns 50.0 if `fft_noise` contains an "error" or "warning" key.
    """
    if "error" in fft_noise or "warning" in fft_noise:
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
    """
    Compute a 0–100 quality score describing PID tracking error for a single axis.

    Parameters:
        pid_error (Dict[str, Any]): Analysis data for the axis. Recognized keys:
            - `rms_error` (float): root-mean-square of the control error (degrees/sec).
            - `max_error` (float): maximum observed error (degrees/sec).
            - `error_drift` (float): steady drift of the error.
            If the dictionary contains an `"error"` or `"warning"` key, a neutral score is returned.

    Returns:
        float: Score between 0.0 and 100.0 where higher is better. `50.0` is returned when `pid_error` contains an `"error"` or `"warning"` key.
    """
    if "error" in pid_error or "warning" in pid_error:
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
    """
    Compute a motor-balance penalty to reduce the overall tune score.
    
    The function reads motor_analysis["overall"]["imbalance_pct"] (percentage) and maps it to a penalty: returns 0.0 if imbalance < 5, 0.2 if imbalance > 20, and a linear value between 0.0 and 0.2 for values in [5, 20].
    
    Parameters:
        motor_analysis (Dict[str, Any]): Mapping expected to contain an "overall" dict with an "imbalance_pct" numeric percentage.
    
    Returns:
        float: Penalty value between 0.0 and 0.2 to be multiplied with the overall score reduction.
    """
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