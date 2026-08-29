"""behavior_scripts/motor/stop.py"""

import common_hardware.motor as motor


def run(brain=None) -> bool:
    """Always executes — stop is never gated behind a halt check, since
    refusing to stop because the robot is halting would be backwards.
    brain is accepted only for API symmetry with the other motor wrappers.
    Always returns True."""
    motor.stop()
    return True
