"""Common utilities for log analysis."""

import logging
from typing import Dict, Any, List, Tuple, Optional
from io import BytesIO
import numpy as np
import tempfile
import os

logger = logging.getLogger(__name__)


def load_parser_from_file_content(file_content: bytes):
    """
    Load an orangebox Parser from file content.
    
    Args:
        file_content: Binary file content from MinIO
        
    Returns:
        Parser object
        
    Raises:
        ImportError: If orangebox is not available
        Exception: If parsing fails
    """
    from orangebox import Parser
    
    # Parser.load() expects a file path, not BytesIO, so write to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bbl') as tmp:
        tmp.write(file_content)
        temp_path = tmp.name
    
    try:
        parser = Parser.load(temp_path)
        return parser
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_path}: {e}")


def extract_field_data(parser, field_name: str) -> Optional[np.ndarray]:
    """
    Extract a field as a numpy array from parser.
    
    Args:
        parser: orangebox Parser instance
        field_name: Name of the field to extract
        
    Returns:
        Numpy array of field values, or None if field not found
    """
    if field_name not in parser.field_names:
        logger.warning(f"Field '{field_name}' not found in parser")
        return None
    
    field_idx = parser.field_names.index(field_name)
    data = []
    
    try:
        for frame in parser.frames():
            data.append(frame.data[field_idx])
        return np.array(data, dtype=np.float64)
    except Exception as e:
        logger.error(f"Error extracting field '{field_name}': {e}")
        return None


def get_time_array(parser) -> Optional[np.ndarray]:
    """
    Get time array in seconds from parser.
    
    Args:
        parser: orangebox Parser instance
        
    Returns:
        Time array in seconds, or None if not available
    """
    time_data = extract_field_data(parser, "time")
    if time_data is None:
        return None
    
    # Convert microseconds to seconds
    return time_data / 1_000_000.0


def calculate_derivative(signal: np.ndarray, dt: float = 1.0) -> np.ndarray:
    """
    Calculate numerical derivative of a signal.
    
    Args:
        signal: Input signal array
        dt: Time step between samples
        
    Returns:
        Derivative array (same length as input, with 0 at first point)
    """
    if len(signal) < 2:
        return np.zeros_like(signal)
    
    derivative = np.zeros_like(signal)
    derivative[1:] = np.diff(signal) / dt
    return derivative


def find_peaks(signal: np.ndarray, threshold: float = 0.1) -> List[int]:
    """
    Find local peaks in a signal.
    
    Args:
        signal: Input signal array
        threshold: Minimum height of peak (as fraction of signal range)
        
    Returns:
        Indices of peaks
    """
    from scipy.signal import find_peaks as scipy_find_peaks
    
    sig_range = np.max(signal) - np.min(signal)
    height_threshold = np.min(signal) + threshold * sig_range
    
    peaks, _ = scipy_find_peaks(signal, height=height_threshold)
    return peaks.tolist()


def normalize_signal(signal: np.ndarray) -> np.ndarray:
    """
    Normalize signal to [-1, 1] range.
    
    Args:
        signal: Input signal
        
    Returns:
        Normalized signal
    """
    sig_max = np.max(np.abs(signal))
    if sig_max == 0:
        return signal
    return signal / sig_max


def calculate_rms(signal: np.ndarray) -> float:
    """Calculate RMS (root mean square) of signal."""
    return float(np.sqrt(np.mean(signal ** 2)))


def calculate_stats(signal: np.ndarray) -> Dict[str, float]:
    """
    Calculate basic statistics for a signal.
    
    Returns:
        Dict with keys: mean, std, min, max, rms, peak
    """
    return {
        "mean": float(np.mean(signal)),
        "std": float(np.std(signal)),
        "min": float(np.min(signal)),
        "max": float(np.max(signal)),
        "rms": calculate_rms(signal),
        "peak": float(np.max(np.abs(signal))),
    }
