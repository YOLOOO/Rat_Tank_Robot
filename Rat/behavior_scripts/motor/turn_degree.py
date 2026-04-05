"""behavior_scripts/motor/turn_degree.py

Approximates a degree-based turn by spinning in place for a calculated
duration. Tune DEGREES_PER_SECOND for your surface + battery level.
"""

import time
import common_hardware.motor as motor
from behavior_scripts.utilities.check_halt import is_halted
import config


def run(degrees: int, speed: int = config.MOTOR_SPEED_NORMAL, brain=None):
    """
    Spin in place.
    Positive degrees = right, negative degrees = left.
    """
    if is_halted(brain):
        return

    duration = abs(degrees) / config.MOTOR_DEGREES_PER_SECOND
    end_time = time.time() + duration

    while time.time() < end_time:
        if is_halted(brain):
            break
        if degrees > 0:
            motor.spin_right(speed)
        else:
            motor.spin_left(speed)
        time.sleep(0.02)

    motor.stop()
