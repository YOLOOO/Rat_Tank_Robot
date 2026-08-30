"""
missions/camera_test.py

Camera subsystem test mission. Runs inside the brain like any other mission.
No streaming here - this camera is for AI support only, and rpicam-vid
--listen was locking up the system with nothing yet consuming the stream.

Steps:
    1. Detect camera via rpicam-hello --list-cameras
    2. Capture a still image, verify file exists.

Led signals:
    Step pass: steady LED_COLOR_CONNECTED (blue), held until the next signal.
    Step fail: LED_COLOR_CRITICAL (red) fast-blinks for LED_BLINK_DURATION_S,
               then settles solid so a failed final step stays visible.
"""

import os
import time
import logging
import subprocess

import config
from behavior_scripts.utilities.check_halt import is_halted
from behavior_scripts.led import patterns as led_patterns

logger = logging.getLogger(__name__)


def run(brain) -> bool:
    # --- Step 1: Detect camera ---
    logger.info("=== CAMERA TEST: Step 1 - Detect Camera ===")
    if is_halted(brain):
        return False

    try:
        result = subprocess.run(
            ["rpicam-hello", "--list-cameras"],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = (result.stdout + result.stderr).lower()
        if "no cameras available" in output or result.returncode != 0:
            logger.error("Step 1 FAIL - No camera detected")
            logger.error(f"Output: {result.stdout}{result.stderr}")
            _led_error()
        else:
            logger.info("Step 1 PASS - Camera Detected")
            logger.info(result.stdout.strip())
            _led_pass()
    except FileNotFoundError:
        logger.error("Step 1 FAIL - rpicam-hello not found, is libcamera installed?")
        _led_error()
    except subprocess.TimeoutExpired:
        logger.error("Step 1 FAIL - rpicam-hello --list-cameras timed out")
        _led_error()

    if is_halted(brain):
        return False
    time.sleep(1)

    # --- Step 2: Capture still image ---
    logger.info("=== CAMERA TEST: Step 2 - Capture still image ===")

    if is_halted(brain):
        return False

    os.makedirs(os.path.dirname(config.CAMERA_TEST_PHOTO), exist_ok=True)

    try:
        result = subprocess.run(
            ["rpicam-still", "--nopreview", "-o", config.CAMERA_TEST_PHOTO, "-t", "2000"],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode != 0 or not os.path.exists(config.CAMERA_TEST_PHOTO):
            logger.error("Step 2 FAIL - Image capture failed")
            logger.error(f"Output: {result.stdout}{result.stderr}")
            _led_error()
        else:
            size = os.path.getsize(config.CAMERA_TEST_PHOTO)
            logger.info(f"Step 2 PASS - Image saved to {config.CAMERA_TEST_PHOTO} ({size} bytes)")
            _led_pass()
    except FileNotFoundError:
        logger.error("Step 2 FAIL - rpicam-still not found")
        _led_error()
    except subprocess.TimeoutExpired:
        logger.error("Step 2 FAIL - rpicam-still timed out")
        _led_error()

    logger.info("Camera test mission ended")
    return False


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _led_pass():
    led_patterns.static(config.LED_COLOR_CONNECTED)


def _led_error():
    led_patterns.flash_alert(config.LED_COLOR_CRITICAL, config.LED_BLINK_ON_S,
                              config.LED_BLINK_OFF_S, config.LED_BLINK_DURATION_S)
