"""Flight-summary analysis - operational insights beyond tuning metrics."""

import logging
import numpy as np
from typing import Dict, Any, Optional

from .utils import extract_fields, calculate_stats

logger = logging.getLogger(__name__)


def analyze_flight_summary(parser) -> Dict[str, Any]:
    """
    Analyze flight operational characteristics: battery sag, current draw, GPS performance, and throttle profile.
    
    Extracts voltage, current, throttle, and GPS fields; computes battery sag (voltage drop),
    current draw statistics, GPS speed/altitude profiles correlated with throttle zones,
    and throttle distribution across low/medium/high zones.
    
    Parameters:
        parser: orangebox Parser instance with flight telemetry fields.
    
    Returns:
        dict: {
            "battery": {
                "min_voltage": float (mV),
                "max_voltage": float (mV),
                "sag_voltage": float (mV, max - min),
                "sag_pct": float (% drop),
                "cell_count": int (estimated),
            },
            "current": {
                "mean_amps": float,
                "max_amps": float,
                "min_amps": float,
                "total_charge_mah": float (integrated over flight),
            },
            "throttle_profile": {
                "mean_throttle_pct": float,
                "max_throttle_pct": float,
                "min_throttle_pct": float,
                "low_zone_pct": float (throttle 0-33%),
                "mid_zone_pct": float (throttle 33-66%),
                "high_zone_pct": float (throttle 66-100%),
            },
            "gps_profile": {
                "has_gps": bool,
                "max_speed_kmh": float,
                "mean_speed_kmh": float,
                "max_altitude_m": float,
                "min_altitude_m": float,
                "altitude_range_m": float,
                "max_climb_rate_ms": float (m/s, positive = climbing),
                "speed_vs_throttle_correlation": float (Pearson r),
                "altitude_vs_throttle_correlation": float (Pearson r),
            },
            "flight_duration": {
                "duration_seconds": float,
                "min_throttle_duration_pct": float (% time at < 20% throttle),
            },
            "error": str (optional, if analysis failed),
        }
    """
    result = {
        "battery": {},
        "current": {},
        "throttle_profile": {},
        "gps_profile": {},
        "flight_duration": {},
    }

    try:
        # Request all potentially available fields
        requested_fields = [
            "time",
            "vbatLatest",
            "amperageLatest",
            "rcCommand[3]",
            "GPS_speed",
            "GPS_altitude",
        ]
        fields = extract_fields(parser, requested_fields)

        time_array = fields.get("time")
        vbat_array = fields.get("vbatLatest")
        amps_array = fields.get("amperageLatest")
        throttle_array = fields.get("rcCommand[3]")
        gps_speed = fields.get("GPS_speed")
        gps_altitude = fields.get("GPS_altitude")

        # Ensure minimum valid data
        if time_array is None or len(time_array) < 10:
            result["error"] = "Insufficient time data"
            return result

        # Convert time from microseconds to seconds
        time_seconds = time_array / 1_000_000.0
        flight_duration = time_seconds[-1] - time_seconds[0]
        result["flight_duration"]["duration_seconds"] = float(flight_duration)

        # === BATTERY ANALYSIS ===
        if vbat_array is not None and len(vbat_array) > 0:
            vbat_valid = vbat_array[vbat_array > 0]  # Filter zero values
            if len(vbat_valid) > 0:
                min_volt = float(np.min(vbat_valid))
                max_volt = float(np.max(vbat_valid))
                sag = max_volt - min_volt
                sag_pct = (sag / max_volt * 100.0) if max_volt > 0 else 0.0

                # Estimate cell count (assuming 3-6S battery, typical cell voltage 3.0-4.2V)
                typical_cell_volt = (max_volt + min_volt) / 2.0 / 1000.0  # Convert mV to V
                estimated_cells = max(3, min(6, round(typical_cell_volt / 3.7)))

                result["battery"] = {
                    "min_voltage": min_volt,
                    "max_voltage": max_volt,
                    "sag_voltage": sag,
                    "sag_pct": float(sag_pct),
                    "cell_count": int(estimated_cells),
                }

        # === CURRENT ANALYSIS ===
        if amps_array is not None and len(amps_array) > 0:
            amps_valid = amps_array[amps_array >= 0]  # Filter negative/invalid values
            if len(amps_valid) > 0:
                mean_amps = float(np.mean(amps_valid))
                max_amps = float(np.max(amps_valid))
                min_amps = float(np.min(amps_valid))

                # Integrate current over time to estimate charge (simplified: use time deltas)
                # Charge = integral of current over time; approximation: sum of (I * dt)
                dt = np.diff(time_seconds)
                current_mid = (amps_array[:-1] + amps_array[1:]) / 2.0
                charge_coulombs = np.sum(current_mid * dt)
                charge_mah = charge_coulombs / 3.6  # Coulombs to mAh (3600 s/h / 1000)

                result["current"] = {
                    "mean_amps": mean_amps,
                    "max_amps": max_amps,
                    "min_amps": min_amps,
                    "total_charge_mah": float(charge_mah),
                }

        # === THROTTLE ANALYSIS ===
        if throttle_array is not None and len(throttle_array) > 0:
            # rcCommand[3] is typically 1000-2000 (0-100% maps to 1000-2000)
            throttle_normalized = np.clip((throttle_array - 1000.0) / 10.0, 0.0, 100.0)

            mean_throttle = float(np.mean(throttle_normalized))
            max_throttle = float(np.max(throttle_normalized))
            min_throttle = float(np.min(throttle_normalized))

            # Throttle zones
            low_zone = np.sum(throttle_normalized <= 33.0) / len(throttle_normalized) * 100.0
            mid_zone = np.sum((throttle_normalized > 33.0) & (throttle_normalized <= 66.0)) / len(throttle_normalized) * 100.0
            high_zone = np.sum(throttle_normalized > 66.0) / len(throttle_normalized) * 100.0

            result["throttle_profile"] = {
                "mean_throttle_pct": mean_throttle,
                "max_throttle_pct": max_throttle,
                "min_throttle_pct": min_throttle,
                "low_zone_pct": float(low_zone),
                "mid_zone_pct": float(mid_zone),
                "high_zone_pct": float(high_zone),
            }

            # Low-throttle hover time
            min_throttle_duration = np.sum(throttle_normalized < 20.0) / len(throttle_normalized) * 100.0
            result["flight_duration"]["min_throttle_duration_pct"] = float(min_throttle_duration)

        # === GPS PROFILE ===
        has_gps = False
        if gps_speed is not None and len(gps_speed) > 0:
            gps_speed_valid = gps_speed[gps_speed >= 0]  # Filter invalid (-1 or missing)
            if len(gps_speed_valid) > 0:
                has_gps = True
                max_speed_cms = float(np.max(gps_speed_valid))
                mean_speed_cms = float(np.mean(gps_speed_valid))
                max_speed_kmh = max_speed_cms / 100.0 * 3.6  # cm/s to km/h
                mean_speed_kmh = mean_speed_cms / 100.0 * 3.6

                result["gps_profile"]["has_gps"] = True
                result["gps_profile"]["max_speed_kmh"] = max_speed_kmh
                result["gps_profile"]["mean_speed_kmh"] = mean_speed_kmh

        if gps_altitude is not None and len(gps_altitude) > 0:
            gps_alt_valid = gps_altitude[gps_altitude >= 0]  # Filter invalid
            if len(gps_alt_valid) > 0:
                has_gps = True
                max_alt = float(np.max(gps_alt_valid))
                min_alt = float(np.min(gps_alt_valid))
                alt_range = max_alt - min_alt

                result["gps_profile"]["has_gps"] = True
                result["gps_profile"]["max_altitude_m"] = max_alt
                result["gps_profile"]["min_altitude_m"] = min_alt
                result["gps_profile"]["altitude_range_m"] = alt_range

                # Climb rate: dAlt/dt (positive = climbing)
                # Note: GPS updates are typically sparse and have jumps
                # Calculate average climb rate from overall altitude change
                if len(gps_altitude) > 10:
                    alt_change = gps_altitude[-1] - gps_altitude[0]
                    if alt_change != 0:
                        avg_climb_rate = alt_change / flight_duration
                        result["gps_profile"]["max_climb_rate_ms"] = float(avg_climb_rate)

        result["gps_profile"]["has_gps"] = has_gps

        # === CORRELATIONS: Speed/Alt vs Throttle ===
        if throttle_array is not None and len(throttle_array) > 0:
            if gps_speed is not None and len(gps_speed) > 0:
                # Align arrays and compute correlation
                min_len = min(len(throttle_normalized), len(gps_speed))
                throttle_trunc = throttle_normalized[:min_len]
                speed_trunc = gps_speed[:min_len]
                speed_valid_idx = speed_trunc >= 0
                if np.sum(speed_valid_idx) > 2:
                    corr_speed = float(np.corrcoef(throttle_trunc[speed_valid_idx], speed_trunc[speed_valid_idx])[0, 1])
                    result["gps_profile"]["speed_vs_throttle_correlation"] = corr_speed

            if gps_altitude is not None and len(gps_altitude) > 0:
                min_len = min(len(throttle_normalized), len(gps_altitude))
                throttle_trunc = throttle_normalized[:min_len]
                alt_trunc = gps_altitude[:min_len]
                alt_valid_idx = alt_trunc >= 0
                if np.sum(alt_valid_idx) > 2:
                    corr_alt = float(np.corrcoef(throttle_trunc[alt_valid_idx], alt_trunc[alt_valid_idx])[0, 1])
                    result["gps_profile"]["altitude_vs_throttle_correlation"] = corr_alt

    except Exception as e:
        logger.error(f"Error analyzing flight summary: {e}")
        result["error"] = str(e)

    return result
