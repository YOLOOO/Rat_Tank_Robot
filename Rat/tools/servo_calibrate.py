"""
tools/servo_calibrate.py

Interactive servo calibration — find safe angle limits for each channel.

Run from the Rat/ directory:
    python3 tools/servo_calibrate.py --channel 0

Controls:
    k / UP arrow     +1°
    j / DOWN arrow   -1°
    K (shift+k)      +10°
    J (shift+j)      -10°
    m                mark current angle as MIN
    x                mark current angle as MAX
    p                print current marks (copy into config.py)
    q                quit
"""

import sys
import argparse
import tty
import termios
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common_hardware.servo import HardwareServo

STEP_SMALL = 1
STEP_BIG   = 10
ANGLE_MIN  = 0
ANGLE_MAX  = 180


def read_key():
    """Read one keypress (handles multi-byte arrow sequences)."""
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1)
        if ch == b'\x1b':
            # Peek for escape sequence (arrow keys)
            try:
                ch2 = os.read(fd, 1)
                if ch2 == b'[':
                    ch3 = os.read(fd, 1)
                    return b'\x1b[' + ch3
            except Exception:
                pass
            return b'\x1b'
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def main():
    parser = argparse.ArgumentParser(description="Servo calibration tool")
    parser.add_argument("--channel", type=int, default=0,
                        help="Servo channel to calibrate (0, 1, 2)")
    parser.add_argument("--start", type=int, default=90,
                        help="Starting angle (default: 90)")
    args = parser.parse_args()

    ch_str     = str(args.channel)
    angle      = args.start
    marked_min = None
    marked_max = None

    servo = HardwareServo()
    servo.setServoPwm(ch_str, angle)

    print(f"\nServo calibration — channel {args.channel}")
    print("=" * 40)
    print("  k / UP      +1°      K   +10°")
    print("  j / DOWN    -1°      J   -10°")
    print("  m = mark MIN    x = mark MAX")
    print("  p = print marks     q = quit")
    print("=" * 40)
    print(f"  Angle: {angle}°\n")

    def move(delta):
        nonlocal angle
        angle = max(ANGLE_MIN, min(ANGLE_MAX, angle + delta))
        servo.setServoPwm(ch_str, angle)
        print(f"  Angle: {angle}°    ", end="\r")

    try:
        while True:
            key = read_key()

            if key == b'q':
                break
            elif key in (b'k', b'\x1b[A'):   # k or UP arrow
                move(+STEP_SMALL)
            elif key in (b'j', b'\x1b[B'):   # j or DOWN arrow
                move(-STEP_SMALL)
            elif key == b'K':
                move(+STEP_BIG)
            elif key == b'J':
                move(-STEP_BIG)
            elif key == b'm':
                marked_min = angle
                print(f"\n  [MIN marked] = {angle}°")
            elif key == b'x':
                marked_max = angle
                print(f"\n  [MAX marked] = {angle}°")
            elif key == b'p':
                print(f"\n  --- Copy into config.py ---")
                print(f"  SERVO_CH{args.channel}_MIN = {marked_min if marked_min is not None else '?'}")
                print(f"  SERVO_CH{args.channel}_MAX = {marked_max if marked_max is not None else '?'}")
                print()

    except KeyboardInterrupt:
        pass

    print(f"\n\nFinal marks for channel {args.channel}:")
    print(f"  SERVO_CH{args.channel}_MIN = {marked_min}")
    print(f"  SERVO_CH{args.channel}_MAX = {marked_max}")
    print("Update config.py with these values.\n")


if __name__ == "__main__":
    main()
