"""behavior_scripts/motor/turn_degree.py

Approximates a degree-based turn by spinning in place for a calculated
duration. Tune DEGREES_PER_SECOND for your surface + battery level.
"""

import time
import common_hardware.motor as motor
from behavior_scripts.utilities.check_halt import is_halted
import config


def run(degrees: int, speed: int = config.MOTOR_SPEED_NORMAL, brain=None) -> bool:
    """
    Spin in place.
    Positive degrees = right, negative degrees = left.
    Returns True if the turn ran to completion, False if it was cut short by
    a halt (either already halted on entry, or halted partway through).

    Not currently wired into any mission — see MOTOR_SENSORY_REWORK_2026-08-29.
    It blocks for the full turn duration (up to a few seconds), which would
    stall a per-tick mission's ~50ms loop and its HALT/command responsiveness
    along with it (the same hazard AI_controlled.py's threaded sensor reads
    were built to avoid). Wiring it in would need its own thread or a
    non-blocking redesign — left as a deliberate follow-up, not done here.
    """
    if is_halted(brain):
        return False

    duration = abs(degrees) / config.MOTOR_DEGREES_PER_SECOND
    end_time = time.time() + duration

    completed = True
    while time.time() < end_time:
        if is_halted(brain):
            completed = False
            break
        if degrees > 0:
            motor.spin_right(speed)
        else:
            motor.spin_left(speed)
        time.sleep(0.02)

    motor.stop()
    return completed
