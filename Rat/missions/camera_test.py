"""
mission/cmaera_test.py

Camera subsystem test mission. Runs inside the brain like any other mission.
Halting at any point (halt command) shuts down cleanly including any
running stream process.

Steps:
    1. Detect camera via rpicam-hello --list-cameras
    2. Capture a still image, verrify file exist.
    3. Start TCP stream, log address, hold until HALT.

Led signals:
    Step pass: Led 2 steady blue.
    Step fail: Led 2 fast red blink.
"""

import os
import time
import socket
import logging
import subprocess

import config
from behavior_scripts.utilities.check_halt import is_halted

logger = logging.getLogger(__name__)

#stream process held at module level so cleanup() can always reach it.
_stream_proc = None


def run(brain) -> bool:
        global _stream_proc

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
        
        #Ensure directory exists
        os.makedirs(os.path.dirname(config.CAMERA_TEST_PHOTO), exist_ok=True)

        try:
                result = subprocess.run(
                        ["rpicam-still", "--nopreview", "-o", config.CAMERA_TEST_PHOTO, "-t", "2000"],
                        capture_output=True,
                        text=True,
                        timeout=15
                )
                if result.returncode != 0 or not os.path.exists(config.CAMERA_TEST_PHOTO):
                        logger.error("Step 2  FAIL - Image capture failed")
                        logger.error(f"Output: {result.stdout}{result.stderr}")
                        _led_error()
                else:
                        size = os.path.getsize(config.CAMERA_TEST_PHOTO)
                        logger.info(f"Step 2 PASS - Image saved to {config.CAMERA_TEST_PHOTO} ({size} bytes)")
                        _led_pass()
        except FileNotFoundError:
                logger.error("Step 2 FAILED - rpicam-still not found")
                _led_error()
        except subprocess.TimeoutExpired:
                logger.error("Step 2 FAIL - rpicam-still timed out")
                _led_error()

        if is_halted(brain):
                return False
        time.sleep(1)

        # --- Step 3: Start stream ---
        logger.info("=== CAMERA TEST: Step 3 - Starting stream ===")

        if is_halted(brain):
                return False
        
        stream_url = (
                f"tcp://{config.CAMERA_STREAM_HOST}:{config.CAMERA_STREAM_PORT}"
        )

        try:
                _stream_proc = subprocess.Popen(
                        [
                                "rpicam-vid",
                                "-t", "0",
                                "--inline",
                                "--listen",
                                "-o", stream_url
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                )

                robot_ip = _get_local_ip()
                viewer_url = f"tcp/h264://{robot_ip}:{config.CAMERA_STREAM_PORT}"

                logger.info(f"Step 3 - Stream started (PID {_stream_proc.pid})")
                logger.info("=" * 55)
                logger.info(" Open in VLC on your dev PC:")
                logger.info(f" Media -> Open Network Stream -> {viewer_url}")
                logger.info(" Send HALT to stop the stream and end this mission")
                logger.info("=" * 55)
                _led_pass()

        except FileNotFoundError:
                logger.error("Step 3 FAIL - rpicam-vid not found")
                _led_error()
                return False
        
        #Hold here until HALT - poll slowly to avoid busy loop
        while not is_halted(brain):
                #Check if stream process died unexpectedly
                if _stream_proc and _stream_proc.poll() is not None:
                        logger.error("Stream process died unexpectedly")
                        _led_error()
                        break
                time.sleep(0.5)
        
        _cleanup_stream()
        logger.info("Camera test mission ended")
        return False

#----------------------------------------------
# Helpers
#---------------------------------------------

def _cleanup_stream():
        global _stream_proc
        if _stream_proc and _stream_proc.poll() is None:
                logger.info("Terminating stream process...")
                _stream_proc.terminate()
                try:
                        _stream_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                        logger.warning("Stream process did not terminate, killing")
                        _stream_proc.kill()
        _stream_proc = None

def _get_local_ip() -> str:
        "Get robot LAN IP"
        try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
        except Exception:
                return "robot-ip"
        
def _led_pass():
        #TODO: Wire leds with led_controller. 
        pass

def _led_error():
        #TODO: Wire leds with led_controller.
        pass

