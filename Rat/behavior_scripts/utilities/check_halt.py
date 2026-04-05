"""behavior_scripts/utilities/check_halt.py"""


def is_halted(brain=None) -> bool:
    """Returns True if the brain has issued a HALT, or if brain is None (safe default: False)."""
    if brain is None:
        return False
    return getattr(brain, "halt_flag", False)
