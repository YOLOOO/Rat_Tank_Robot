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

Led signals:
    Running, both sensors healthy: LED_COLOR_SENSORY_TEST blinks at the
        LED_ACTIVITY_BLINK_* cadence.
    Running, either sensor faulty this reading: solid LED_COLOR_CRITICAL.
    Fails to open a sensor at all (mission aborts before the loop starts):
        flash_alert() on LED_COLOR_CRITICAL, then the brain takes the LED
        back for its mission-select flash.
"""

import logging
import time

from common_hardware.ultrasonic import Ultrasonic
from common_hardware.infrared import Infrared
from behavior_scripts.utilities.check_halt import is_halted
from behavior_scripts.led import patterns as led_patterns
import config

logger = logging.getLogger(__name__)

_LOG_INTERVAL_S = 0.5  # seconds between logged readings


def run(brain) -> bool:
    logger.info("=== SENSORY TEST: reading ultrasonic + infrared — HALT to stop ===")

    try:
        ultrasonic = Ultrasonic()
    except Exception:
        logger.exception("SENSORY TEST: failed to open ultrasonic sensor")
        led_patterns.flash_alert(config.LED_COLOR_CRITICAL, config.LED_BLINK_ON_S,
                                  config.LED_BLINK_OFF_S, config.LED_BLINK_DURATION_S)
        return False

    try:
        infrared = Infrared()
    except Exception:
        logger.exception("SENSORY TEST: failed to open infrared sensor")
        ultrasonic.close()
        led_patterns.flash_alert(config.LED_COLOR_CRITICAL, config.LED_BLINK_ON_S,
                                  config.LED_BLINK_OFF_S, config.LED_BLINK_DURATION_S)
        return False

    blink_start = time.time()

    try:
        while not is_halted(brain):
            dist_cm       = ultrasonic.get_distance()
            dist_str      = f"{dist_cm:.1f}cm" if dist_cm != -1 else "FAIL(-1)"
            ultrasonic_ok = dist_cm != -1

            infrared_ok = True
            try:
                ir_bits = infrared.read_all_infrared()
                ir1 = (ir_bits >> 2) & 1
                ir2 = (ir_bits >> 1) & 1
                ir3 = ir_bits & 1
                ir_str = f"[{ir1} {ir2} {ir3}] (raw={ir_bits})"
            except Exception as e:
                ir_str = f"FAIL({e!r})"
                infrared_ok = False

            logger.info(f"SENSORY TEST: ultrasonic={dist_str}  infrared[1,2,3]={ir_str}")

            if ultrasonic_ok and infrared_ok:
                led_patterns.step_blink(config.LED_COLOR_SENSORY_TEST, config.LED_ACTIVITY_BLINK_ON_S,
                                         config.LED_ACTIVITY_BLINK_OFF_S, blink_start)
            else:
                led_patterns.static(config.LED_COLOR_CRITICAL)

            time.sleep(_LOG_INTERVAL_S)
    except Exception:
        logger.exception("SENSORY TEST: error")
    finally:
        ultrasonic.close()
        infrared.close()

    logger.info("SENSORY TEST: stopped")
    return False
