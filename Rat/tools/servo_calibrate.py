"""
tools/servo_calibrate.py

Interactive servo calibration — find safe angle limits for each channel.

Run directly on the Pi:
    python3 tools/servo_calibrate.py --channel 0

Controls:
    UP / k     +1°
    DOWN / j   -1°
    SHIFT+UP   +10°
    SHIFT+DOWN -10°
    m          mark current angle as MIN
    x          mark current angle as MAX
    p          print current marks (copy into config.py)
    q          quit
"""

import sys
import argparse
import tty
import termios

sys.path.insert(0, ".")   # run from Rat/ directory

from common_hardware.servo import HardwareServo

STEP_SMALL = 1
STEP_BIG   = 10
ANGLE_MIN  = 0
ANGLE_MAX  = 180


def getch():
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.buffer.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def main():
    parser = argparse.ArgumentParser(description="Servo calibration tool")
    parser.add_argument("--channel", type=int, default=0,
                        help="Servo channel to calibrate (0, 1, 2)")
    parser.add_argument("--start", type=int, default=90,
                        help="Starting angle (default 90)")
    args = parser.parse_args()

    ch      = str(args.channel)
    angle   = args.start
    marked_min = None
    marked_max = None

    servo = HardwareServo()
    servo.setServoPwm(ch, angle)

    print(f"\nServo calibration — channel {ch}")
    print("=" * 40)
    print("  UP/k     +1°     SHIFT+UP   +10°")
    print("  DOWN/j   -1°     SHIFT+DOWN -10°")
    print("  m = mark MIN    x = mark MAX")
    print("  p = print marks   q = quit")
    print("=" * 40)
    print(f"  Current angle: {angle}°\n")

    def move(delta):
        nonlocal angle
        angle = max(ANGLE_MIN, min(ANGLE_MAX, angle + delta))
        servo.setServoPwm(ch, angle)
        print(f"  Angle: {angle}°", end="\r")

    try:
        while True:
            ch_in = getch()

            if ch_in == b'q':
                break
            elif ch_in == b'k' or ch_in == b'\x1b':
                # arrow keys send ESC [ A/B
                if ch_in == b'\x1b':
                    seq = sys.stdin.buffer.read(2) if sys.stdin.buffer.read(1) == b'[' else b''
                    if seq == b'A':       move(+STEP_SMALL)   # UP
                    elif seq == b'B':     move(-STEP_SMALL)   # DOWN
                    elif seq == b'1;2A':  move(+STEP_BIG)     # SHIFT+UP
                    elif seq == b'1;2B':  move(-STEP_BIG)     # SHIFT+DOWN
                else:
                    move(+STEP_SMALL)
            elif ch_in == b'j':
                move(-STEP_SMALL)
            elif ch_in == b'm':
                marked_min = angle
                print(f"\n  [MIN marked] = {angle}°")
            elif ch_in == b'x':
                marked_max = angle
                print(f"\n  [MAX marked] = {angle}°")
            elif ch_in == b'p':
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
