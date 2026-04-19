"""LogAnalysis model - stores analysis results for a blackbox log."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class LogAnalysis(Base):
    """
    LogAnalysis model storing computed analysis results for a blackbox log.
    
    Attributes:
        id: Unique identifier
        log_id: Foreign key to BlackboxLog
        module: Analysis module name (e.g., "step_response", "fft_noise", "pid_error", "motor_analysis", "gyro_spectrogram", "flight_summary", "tune_score")
        result_json: JSON-serialized analysis results (structure depends on module)
        created_at: Timestamp of analysis
    
    The result_json structure varies by module:
    - step_response: {roll: {trace: [...], rise_time_ms, overshoot_pct, settling_time_ms, ringing}, pitch: {...}, yaw: {...}}
    - fft_noise: {roll: {freqs: [...], psd: [...], peaks: [...]}, pitch: {...}, yaw: {...}}
    - pid_error: {roll: {rms_error, max_error, mean_abs_error, error_vs_setpoint: [...]}, pitch: {...}, yaw: {...}}
    - motor_analysis: {motors: {...}, overall: {imbalance_pct, motor_correlation_mean, throttle_correlation, resonance_peaks: [...]}}
    - gyro_spectrogram: {roll: [...], pitch: [...], yaw: [...]} (2D spectrogram data)
    - flight_summary: {battery: {min_voltage, max_voltage, sag_voltage, sag_pct, cell_count}, current: {mean_amps, max_amps, total_charge_mah}, throttle_profile: {...}, gps_profile: {...}, flight_duration: {...}}
    - tune_score: {roll_score, pitch_score, yaw_score, overall_score, motor_penalty, details}
    """

    __tablename__ = "log_analyses"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(Integer, ForeignKey("blackbox_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    module = Column(String(100), nullable=False, index=True)
    result_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    log = relationship("BlackboxLog", back_populates="analyses")

    def __repr__(self) -> str:
        return f"<LogAnalysis(id={self.id}, log_id={self.log_id}, module='{self.module}')>"
