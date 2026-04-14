"""
tools/probe_mnt.py
==================
Standalone diagnostic — lists all input devices and dumps every event
from the MNT trackball so you can see exactly what each button sends.

Run on the DEV PC (Linux):
    python tools/probe_mnt.py

Press each button and roll the ball. Ctrl-C to quit.
"""

import sys

try:
    import evdev
    from evdev import ecodes
except ImportError:
    print("evdev not installed. Run: pip install evdev")
    sys.exit(1)

# ------------------------------------------------------------------
# List all available input devices
# ------------------------------------------------------------------
print("\nAvailable input devices:")
print("-" * 50)
devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
for d in devices:
    print(f"  {d.path:20s}  {d.name}")
print("-" * 50)

# ------------------------------------------------------------------
# Find the MNT trackball (or let user pick)
# ------------------------------------------------------------------
TARGET = "mnt"  # case-insensitive substring match

matches = [d for d in devices if TARGET in d.name.lower()]

if not matches:
    print(f"\nNo device matching '{TARGET}' found.")
    print("Choose a device by number:")
    for i, d in enumerate(devices):
        print(f"  [{i}] {d.name}")
    idx = int(input("Enter number: "))
    dev = devices[idx]
else:
    dev = matches[0]
    print(f"\nUsing: {dev.name}  ({dev.path})")

# ------------------------------------------------------------------
# Dump all events
# ------------------------------------------------------------------
print("\nListening for events — press buttons and roll the ball. Ctrl-C to quit.\n")

for event in dev.read_loop():
    if event.type == ecodes.EV_SYN:
        continue  # skip sync noise

    type_name = ecodes.EV.get(event.type, f"type={event.type}")

    if event.type == ecodes.EV_KEY:
        key_name = ecodes.KEY.get(event.code, f"code={event.code}")
        state    = {1: "DOWN", 0: "UP", 2: "REPEAT"}.get(event.value, event.value)
        print(f"  {type_name:8s}  {key_name:20s}  {state}")

    elif event.type == ecodes.EV_REL:
        rel_name = ecodes.REL.get(event.code, f"code={event.code}")
        print(f"  {type_name:8s}  {rel_name:20s}  {event.value:+d}")

    else:
        print(f"  {type_name:8s}  code={event.code:4d}  value={event.value}")
