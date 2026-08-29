"""behavior_scripts/motor/curve_turn.py"""

import common_hardware.motor as motor
from behavior_scripts.utilities.check_halt import is_halted


def run(left: int, right: int, brain=None) -> bool:
    """
    Curve by giving each track a different speed/direction.
    left, right : -4095 to +4095
    Returns True if the command was issued, False if skipped (halted).
    """
    if is_halted(brain):
        return False
    motor.curve(left, right)
    return True
