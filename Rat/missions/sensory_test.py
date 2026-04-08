"""
missions/sensory_test.py

Sensory test mission — placeholder for testing infrared and ultrasonic sensors.
Called each brain tick via run(brain). Returns False when done.
"""

import logging

logger = logging.getLogger(__name__)

_initialized = False


def run(brain) -> bool:
    global _initialized

    if not _initialized:
        _initialized = True
        logger.info("Sensory test mission started — not yet implemented")

    # TODO: implement sensor readout tests
    # e.g. read infrared line sensors, read ultrasonic distance, log results

    _initialized = False
    return False
