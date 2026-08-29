"""behavior_scripts/motor/set_motors.py"""

import common_hardware.motor as motor
from behavior_scripts.utilities.check_halt import is_halted


def run(left: int, right: int, brain=None) -> bool:
    """
    Drive both tracks independently at raw duty values.
    left, right : -4095 to +4095 — see common_hardware/motor.py's
    set_motors() for the sign convention and safety passes (reversal
    settle, kickstart) applied underneath this.
    Returns True if the command was issued, False if skipped (halted).
    """
    if is_halted(brain):
        return False
    motor.set_motors(left, right)
    return True
