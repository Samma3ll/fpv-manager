#!/usr/bin/env python3
"""Inspect available fields in a blackbox log file."""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from orangebox import Parser

def inspect_log(log_path):
    """Inspect and print all available fields in a blackbox log."""
    print(f"\n📋 Inspecting: {log_path}\n")
    
    parser = Parser.load(log_path)
    
    # Print headers
    print("=" * 80)
    print("HEADERS")
    print("=" * 80)
    headers = parser.headers
    for key in sorted(headers.keys()):
        val = headers[key]
        if isinstance(val, (list, tuple)) and len(val) > 0:
            print(f"  {key}: {val}")
        elif isinstance(val, str) and len(val) < 100:
            print(f"  {key}: {val}")
    
    # Print available fields
    print("\n" + "=" * 80)
    print("AVAILABLE FIELDS")
    print("=" * 80)
    fields = parser.field_names
    print(f"Total fields: {len(fields)}\n")
    for i, field in enumerate(fields):
        print(f"  [{i:3d}] {field}")
    
    # Check for specific fields we need
    print("\n" + "=" * 80)
    print("REQUIRED FIELDS STATUS")
    print("=" * 80)
    
    required_fields = {
        'time': 'Flight duration',
        'rcRate[0]': 'Roll rate command',
        'rcRate[1]': 'Pitch rate command',
        'rcRate[2]': 'Yaw rate command',
        'gyroADC[0]': 'Roll gyro',
        'gyroADC[1]': 'Pitch gyro',
        'gyroADC[2]': 'Yaw gyro',
        'motor[0]': 'Motor 0 output',
        'motor[1]': 'Motor 1 output',
        'motor[2]': 'Motor 2 output',
        'motor[3]': 'Motor 3 output',
        'axisError[0]': 'Roll error',
        'axisError[1]': 'Pitch error',
        'axisError[2]': 'Yaw error',
    }
    
    for field, description in required_fields.items():
        exists = "✓" if field in fields else "✗"
        print(f"  {exists} {field:20s} - {description}")
    
    # Get frame count
    frame_count = 0
    for _ in parser.frames():
        frame_count += 1
    
    print(f"\n📊 Total frames: {frame_count}")
    
    # Try to extract time range
    if 'time' in fields:
        time_idx = fields.index('time')
        times = []
        for i, frame in enumerate(parser.frames()):
            times.append(frame.data[time_idx])
            if i >= 100:  # Just sample first 100
                break
        if times:
            duration_s = (times[-1] - times[0]) / 1_000_000
            print(f"⏱️  Sample duration: {duration_s:.2f}s")

if __name__ == '__main__':
    log_path = 'btfl_001_clean.bbl'
    if len(sys.argv) > 1:
        log_path = sys.argv[1]
    
    inspect_log(log_path)
