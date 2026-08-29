"""behavior_scripts/motor/spin_left.py"""

import common_hardware.motor as motor
from behavior_scripts.utilities.check_halt import is_halted


def run(speed: int = 2048, brain=None) -> bool:
    """Returns True if the command was issued, False if skipped (halted)."""
    if is_halted(brain):
        return False
    motor.spin_left(speed)
    return True
