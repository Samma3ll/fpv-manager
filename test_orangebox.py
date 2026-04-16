#!/usr/bin/env python3
"""Test script to inspect orangebox parsing of real blackbox log."""

import sys
sys.path.insert(0, '/app')

from orangebox import Parser

def test_parse():
    log_path = '/app/../btfl_001_clean.bbl'
    
    try:
        parser = Parser.load(log_path)
        print('✓ Successfully loaded blackbox log')
        
        # Get headers
        headers = parser.headers
        print(f'\nTotal headers: {len(headers)}')
        
        # Print key headers we care about
        print('\n=== FIRMWARE & CRAFT INFO ===')
        print(f'Firmware revision: {headers.get("Firmware revision", "N/A")}')
        print(f'Craft name: {headers.get("Craft name", "N/A")}')
        print(f'Product: {headers.get("Product", "N/A")}')
        print(f'Board name: {headers.get("Board name", "N/A")}')
        
        print('\n=== PID VALUES ===')
        roll_pid = headers.get("rollPID", "N/A")
        pitch_pid = headers.get("pitchPID", "N/A")
        yaw_pid = headers.get("yawPID", "N/A")
        print(f'rollPID: {roll_pid}')
        print(f'pitchPID: {pitch_pid}')
        print(f'yawPID: {yaw_pid}')
        
        if roll_pid != "N/A":
            print(f'  Roll P value: {roll_pid[0] if isinstance(roll_pid, (list, tuple)) else roll_pid}')
        
        print('\n=== OTHER KEY HEADERS ===')
        for key in ['looptime', 'minthrottle', 'maxthrottle', 'Data version', 'I interval', 'P interval']:
            print(f'{key}: {headers.get(key, "N/A")}')
        
        # Get frames info
        print(f'\n=== FRAME DATA ===')
        frames_list = list(parser.frames())
        print(f'Total frames: {len(frames_list)}')
        
        if len(frames_list) >= 2:
            first_frame = frames_list[0]
            last_frame = frames_list[-1]
            
            print(f'First frame type: {type(first_frame)}')
            print(f'First frame data type: {type(first_frame.data)}')
            
            # Print frame data structure
            if hasattr(first_frame.data, '__dict__'):
                print(f'First frame attributes: {list(first_frame.data.__dict__.keys())[:5]}')
            
            # Try to get time field - test multiple approaches
            first_time = None
            last_time = None
            
            # Approach 1: dict-like access
            if hasattr(first_frame.data, 'get'):
                first_time = first_frame.data.get('time')
                last_time = last_frame.data.get('time')
                print('✓ Accessing via .get()')
            
            # Approach 2: attribute access
            if first_time is None and hasattr(first_frame.data, 'time'):
                first_time = first_frame.data.time
                last_time = last_frame.data.time
                print('✓ Accessing via attribute')
            
            # Approach 3: index access
            if first_time is None:
                try:
                    first_time = first_frame.data['time']
                    last_time = last_frame.data['time']
                    print('✓ Accessing via index')
                except:
                    pass
            
            if first_time is not None:
                print(f'First time: {first_time}')
                print(f'Last time: {last_time}')
                
                if last_time > first_time:
                    duration_s = (last_time - first_time) / 1_000_000
                    print(f'Flight duration: {duration_s:.2f}s ({duration_s/60:.2f}m)')
        
        print(f'\n=== FIELD NAMES ===')
        print(f'Total fields: {len(parser.field_names)}')
        print(f'First 10 fields: {parser.field_names[:10]}')
        
        print('\n=== ALL HEADERS ===')
        for key in sorted(headers.keys())[:20]:
            val = headers[key]
            if isinstance(val, (list, tuple)):
                print(f'{key}: {val}')
            elif len(str(val)) < 80:
                print(f'{key}: {val}')
            else:
                print(f'{key}: {str(val)[:80]}...')
        
        return True
        
    except Exception as e:
        import traceback
        print(f'✗ Error: {e}')
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_parse()
    sys.exit(0 if success else 1)
