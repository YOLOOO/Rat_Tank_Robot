"""
missions/sensory_test.py

Sensory test mission — continuously reads the ultrasonic and infrared
sensors and logs every reading to the brain log, so sensor health can be
verified directly without going through AI_CONTROLLED's strict pre-flight
gate (which aborts the whole mission on a single bad sensor instead of
just telling you what it saw).

Blocks inside a single run() call and polls is_halted(brain) directly,
same "hold until HALT" pattern as camera_test.py — see check_halt.py for
why that's required instead of returning True and waiting for the next
tick. Runs until HALT; also stops itself immediately if either sensor
fails to open at all (e.g. GPIO already claimed by a dead process).
"""

import logging
import time

from common_hardware.ultrasonic import Ultrasonic
from common_hardware.infrared import Infrared
from behavior_scripts.utilities.check_halt import is_halted

logger = logging.getLogger(__name__)

_LOG_INTERVAL_S = 0.5  # seconds between logged readings


def run(brain) -> bool:
    logger.info("=== SENSORY TEST: reading ultrasonic + infrared — HALT to stop ===")

    try:
        ultrasonic = Ultrasonic()
    except Exception:
        logger.exception("SENSORY TEST: failed to open ultrasonic sensor")
        return False

    try:
        infrared = Infrared()
    except Exception:
        logger.exception("SENSORY TEST: failed to open infrared sensor")
        ultrasonic.close()
        return False

    try:
        while not is_halted(brain):
            dist_cm  = ultrasonic.get_distance()
            dist_str = f"{dist_cm:.1f}cm" if dist_cm != -1 else "FAIL(-1)"

            try:
                ir_bits = infrared.read_all_infrared()
                ir1 = (ir_bits >> 2) & 1
                ir2 = (ir_bits >> 1) & 1
                ir3 = ir_bits & 1
                ir_str = f"[{ir1} {ir2} {ir3}] (raw={ir_bits})"
            except Exception as e:
                ir_str = f"FAIL({e!r})"

            logger.info(f"SENSORY TEST: ultrasonic={dist_str}  infrared[1,2,3]={ir_str}")
            time.sleep(_LOG_INTERVAL_S)
    except Exception:
        logger.exception("SENSORY TEST: error")
    finally:
        ultrasonic.close()
        infrared.close()

    logger.info("SENSORY TEST: stopped")
    return False
