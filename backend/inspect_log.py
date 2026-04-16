from orangebox import Parser

parser = Parser.load("/app/btfl_001_clean.bbl")
headers = parser.headers

print("=== FIRMWARE & CRAFT ===")
print(f"Firmware: {headers.get('Firmware revision', 'N/A')}")
print(f"Craft: {headers.get('Craft name', 'N/A')}")

print("\n=== PID VALUES ===")
print(f"Roll PID: {headers.get('rollPID', 'N/A')}")
print(f"Pitch PID: {headers.get('pitchPID', 'N/A')}")
print(f"Yaw PID: {headers.get('yawPID', 'N/A')}")

print("\n=== FRAMES ===")
frames = list(parser.frames())
print(f"Total: {len(frames)}")
print(f"Frame type: {type(frames[0])}")

# Find time field index
time_idx = None
for i, field in enumerate(parser.field_names):
    if field == 'time':
        time_idx = i
        print(f"Time field index: {i}")
        break

if time_idx is not None and len(frames) >= 2:
    t_first = frames[0].data[time_idx]
    t_last = frames[-1].data[time_idx]
    print(f"First time: {t_first}")
    print(f"Last time: {t_last}")
    
    if isinstance(t_last, (int, float)) and isinstance(t_first, (int, float)):
        duration = (t_last - t_first) / 1_000_000
        print(f"Duration: {duration:.2f}s ({duration/60:.2f}m)")

print("\n=== ALL HEADERS ===")
for k, v in sorted(headers.items()):
    if isinstance(v, (list, tuple)):
        print(f"{k}: {v}")
    elif len(str(v)) < 100:
        print(f"{k}: {v}")
    else:
        print(f"{k}: {str(v)[:100]}...")
