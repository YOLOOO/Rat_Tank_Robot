"""behavior_scripts/motor/backward.py"""

import common_hardware.motor as motor
from behavior_scripts.utilities.check_halt import is_halted


def run(speed: int = 2048, brain=None):
    if is_halted(brain):
        return
    motor.backward(speed)
