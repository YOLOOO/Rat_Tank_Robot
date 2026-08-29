"""behavior_scripts/utilities/check_halt.py"""


def is_halted(brain=None) -> bool:
    """Returns True if a HALT has been received, or if brain is None (safe default: False).

    Reads brain.command_server.halt_flag rather than brain.halt_flag: the
    command_server flag is set the instant HALT arrives on the receiver
    thread (see control_receiver_server.py), while RatBrain.halt_flag only
    exists transiently inside the main loop's own _process_halt() — never
    observable from inside a running mission's run() call, and never set at
    all while a mission is blocked inside a single run() (e.g. camera_test's
    "hold until HALT" stream loop). See MOTOR_SENSORY_REWORK_2026-08-29.
    """
    if brain is None:
        return False
    command_server = getattr(brain, "command_server", None)
    if command_server is None:
        return False
    return getattr(command_server, "halt_flag", False)
