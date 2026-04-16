"""Common utilities for log analysis."""

import logging
from typing import Dict, Any, List, Tuple, Optional
from io import BytesIO
import numpy as np
import tempfile
import os

logger = logging.getLogger(__name__)


class ParserContextManager:
    """
    Context manager for loading an orangebox.Parser from file content.

    The parser reads frames lazily, so the temporary file must remain available
    during the entire analysis. This context manager ensures the temp file is
    deleted only after the parser is no longer needed.
    """

    def __init__(self, file_content: bytes):
        self.file_content = file_content
        self.temp_path = None
        self.parser = None

    def __enter__(self):
        from orangebox import Parser

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bbl') as tmp:
            tmp.write(self.file_content)
            self.temp_path = tmp.name

        # Load parser (lazily reads frames)
        self.parser = Parser.load(self.temp_path)
        return self.parser

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up temporary file
        if self.temp_path and os.path.exists(self.temp_path):
            try:
                os.remove(self.temp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {self.temp_path}: {e}")
        return False


def load_parser_from_file_content(file_content: bytes):
    """
    Load an orangebox.Parser from binary .bbl file content.

    WARNING: The returned parser reads frames lazily. To ensure the temporary
    file remains available during analysis, use ParserContextManager instead:

        with ParserContextManager(file_content) as parser:
            # Use parser here
            analyze_step_response(parser)

    This legacy function is kept for backward compatibility but may cause
    issues if the parser is used after the temp file is deleted.

    Parameters:
        file_content (bytes): Binary content of a .bbl file.

    Returns:
        Parser: Loaded Parser instance.
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


def extract_fields(parser, field_names: List[str]) -> Dict[str, Optional[np.ndarray]]:
    """
    Extract multiple fields from a parser in a single pass over frames.

    Parameters:
        parser: Parser-like object exposing `field_names` (iterable of names) and `frames()` yielding frames with a `data` sequence.
        field_names (List[str]): List of field names to extract.

    Returns:
        Dict[str, Optional[np.ndarray]]: Mapping from field name to array of values (or None if field not found or extraction failed).
    """
    result = {}

    # Find indices for all requested fields
    field_indices = {}
    for field_name in field_names:
        if field_name in parser.field_names:
            field_indices[field_name] = parser.field_names.index(field_name)
        else:
            logger.warning(f"Field '{field_name}' not found in parser")
            result[field_name] = None

    if not field_indices:
        return result

    # Initialize data lists
    data_lists = {field_name: [] for field_name in field_indices.keys()}

    try:
        # Single pass over frames
        for frame in parser.frames():
            for field_name, field_idx in field_indices.items():
                data_lists[field_name].append(frame.data[field_idx])

        # Convert to numpy arrays
        for field_name, data_list in data_lists.items():
            result[field_name] = np.array(data_list, dtype=np.float64)

    except Exception as e:
        logger.error(f"Error extracting fields: {e}")
        for field_name in field_indices.keys():
            if field_name not in result:
                result[field_name] = None

    return result


def extract_field_data(parser, field_name: str) -> Optional[np.ndarray]:
    """
    Extract a named field from a parser and return its values as a NumPy array.

    Note: For extracting multiple fields, prefer extract_fields() which does
    a single pass over frames instead of multiple passes.

    Parameters:
        parser: Parser-like object exposing `field_names` (iterable of names) and `frames()` yielding frames with a `data` sequence.
        field_name (str): Name of the field to extract.

    Returns:
        np.ndarray: Array of the field values with dtype `float64`, or `None` if the field is not present or extraction fails.
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
    Return the time values from the parser converted to seconds.
    
    Parameters:
        parser: An `orangebox` Parser instance containing a `time` field in microseconds.
    
    Returns:
        `np.ndarray`: Time values in seconds, or `None` if the parser has no `time` field or extraction fails.
    """
    time_data = extract_field_data(parser, "time")
    if time_data is None:
        return None
    
    # Convert microseconds to seconds
    return time_data / 1_000_000.0


def calculate_derivative(signal: np.ndarray, dt: float = 1.0) -> np.ndarray:
    """
    Compute the first-order discrete derivative of a 1-D signal.
    
    Parameters:
        signal (np.ndarray): Input signal samples.
        dt (float): Time interval between consecutive samples.
    
    Returns:
        np.ndarray: Array with the same shape as `signal` where the first element is 0 and each subsequent element is the difference between adjacent samples divided by `dt`.
    """
    if len(signal) < 2:
        return np.zeros_like(signal)
    
    derivative = np.zeros_like(signal)
    derivative[1:] = np.diff(signal) / dt
    return derivative


def find_peaks(signal: np.ndarray, threshold: float = 0.1) -> List[int]:
    """
    Detect local peaks in a numeric signal array.
    
    Parameters:
        signal (np.ndarray): 1-D array containing the signal samples.
        threshold (float): Fraction of the signal range above the minimum that a sample
            must exceed to be considered a peak (value between 0 and 1).
    
    Returns:
        List[int]: Indices of samples identified as peaks.
    """
    from scipy.signal import find_peaks as scipy_find_peaks
    
    sig_range = np.max(signal) - np.min(signal)
    height_threshold = np.min(signal) + threshold * sig_range
    
    peaks, _ = scipy_find_peaks(signal, height=height_threshold)
    return peaks.tolist()


def normalize_signal(signal: np.ndarray) -> np.ndarray:
    """
    Scale an array so its values fall within the range [-1, 1] by dividing by the maximum absolute value.
    
    Parameters:
        signal (np.ndarray): Input signal array.
    
    Returns:
        np.ndarray: Array with values scaled to lie between -1 and 1. If all elements are zero, the input array is returned unchanged.
    """
    sig_max = np.max(np.abs(signal))
    if sig_max == 0:
        return signal
    return signal / sig_max


def calculate_rms(signal: np.ndarray) -> float:
    """
    Compute the root mean square (RMS) of a numeric signal.
    
    Parameters:
        signal (np.ndarray): Array of sample values.
    
    Returns:
        float: RMS value of the input signal (sqrt(mean(signal ** 2))).
    """
    return float(np.sqrt(np.mean(signal ** 2)))


def calculate_stats(signal: np.ndarray) -> Dict[str, float]:
    """
    Compute basic descriptive statistics for a numeric signal.
    
    Returns:
        dict: Mapping with keys:
            - `mean`: arithmetic mean of the signal.
            - `std`: standard deviation of the signal.
            - `min`: minimum value in the signal.
            - `max`: maximum value in the signal.
            - `rms`: root-mean-square value of the signal.
            - `peak`: maximum absolute value in the signal.
    """
    return {
        "mean": float(np.mean(signal)),
        "std": float(np.std(signal)),
        "min": float(np.min(signal)),
        "max": float(np.max(signal)),
        "rms": calculate_rms(signal),
        "peak": float(np.max(np.abs(signal))),
    }