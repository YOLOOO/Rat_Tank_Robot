"""
MNT Reform Optical Trackball Backend (dev PC)
=============================================
Reads the MNT trackball via evdev and fires commands via callback.

Drive model:
    Y key (keyboard)        — toggle full-speed forward latch
    U key (keyboard)        — toggle full-speed backward latch
    Ball X axis             — differential steering: offsets left/right motor
                              while a direction latch is active
    Ball Y axis             — not used

Arm / halt:
    BTN_LEFT   (primary)    → ARM_TOGGLE
    BTN_RIGHT  (secondary)  → GRIP_TOGGLE
    BTN_MIDDLE              → HALT

Install dependency on dev PC:
    pip install evdev
"""

import threading
import time
import logging
from typing import Optional, Callable

import config

logger = logging.getLogger(__name__)

try:
    import evdev
    from evdev import ecodes
    _EVDEV_AVAILABLE = True
except ImportError:
    _EVDEV_AVAILABLE = False
    import platform as _platform
    if _platform.system() == "Windows":
        logger.info("MNT trackball not supported on Windows — keyboard only")
    else:
        logger.warning("evdev not installed — pip install evdev")


def _find_device() -> Optional["evdev.InputDevice"]:
    if not _EVDEV_AVAILABLE:
        return None
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        if config.MNT_DEVICE_NAME.lower() in dev.name.lower():
            logger.info(f"Found MNT trackball: {dev.name} at {path}")
            return dev
        dev.close()
    available = [evdev.InputDevice(p).name for p in evdev.list_devices()]
    logger.warning(f"MNT trackball not found. Looking for: '{config.MNT_DEVICE_NAME}'. Available: {available}")
    return None


def _clamp(value: int, limit: int) -> int:
    return max(-limit, min(limit, value))


class MntMouseBackend:
    """
    Reads MNT trackball in a background thread.
    Fires commands via on_command callback — same interface as KeyboardBackend.
    """

    def __init__(self, on_command: Callable[[str], None]):
        self._on_command    = on_command
        self._device        = None
        self._thread        = None
        self._running       = False

        # Accumulated X delta between motor send ticks (Y ignored)
        self._dx            = 0
        self._axis_lock     = threading.Lock()

        # Hold state for direction buttons
        self._fwd_held      = False  # BTN_EXTRA — left extra
        self._rev_held      = False  # BTN_SIDE  — right extra

        # Motor send rate limiting
        self._send_interval = 1.0 / config.MNT_SEND_RATE
        self._last_send     = 0.0

        # P-key toggle — when False no commands are forwarded to the robot
        self._enabled       = True

    def start(self) -> bool:
        """Start the backend. Returns True if trackball was found."""
        if not _EVDEV_AVAILABLE:
            return False
        self._device = _find_device()
        if self._device is None:
            return False
        self._running = True
        self._thread  = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        self._motor_thread = threading.Thread(target=self._motor_loop, daemon=True)
        self._motor_thread.start()
        logger.info("MNT backend started")
        return True

    def stop(self):
        self._running = False
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass

    def toggle_enabled(self):
        """Toggle whether MNT commands are forwarded to the robot (P key)."""
        self._enabled = not self._enabled
        if not self._enabled:
            self._fwd_held = False
            self._rev_held = False
        state = "ENABLED" if self._enabled else "PAUSED"
        logger.info(f"MNT backend {state}")

    def drive_forward(self):
        """Toggle forward latch (Y key). Press again to stop."""
        if self._fwd_held:
            self._fwd_held = False
            logger.info("Drive: stopped")
        else:
            self._fwd_held = True
            self._rev_held = False
            logger.info("Drive: forward")

    def drive_backward(self):
        """Toggle backward latch (U key). Press again to stop."""
        if self._rev_held:
            self._rev_held = False
            logger.info("Drive: stopped")
        else:
            self._rev_held = True
            self._fwd_held = False
            logger.info("Drive: backward")

    # ------------------------------------------------------------------
    # Background read loop
    # ------------------------------------------------------------------

    def _read_loop(self):
        try:
            for event in self._device.read_loop():
                if not self._running:
                    break

                if event.type == ecodes.EV_REL:
                    with self._axis_lock:
                        if event.code == ecodes.REL_X:
                            self._dx += event.value
                        # REL_Y intentionally ignored

                elif event.type == ecodes.EV_KEY and event.value == 1 and self._enabled:
                    cmd = self._map_button(event.code)
                    if cmd:
                        self._on_command(cmd)

        except Exception as e:
            if self._running:
                logger.error(f"MNT read error: {e}")

    def _map_button(self, code: int) -> Optional[str]:
        if code == ecodes.BTN_LEFT:
            return "ARM_TOGGLE"
        elif code == ecodes.BTN_RIGHT:
            return "GRIP_TOGGLE"
        elif code == ecodes.BTN_MIDDLE:
            return "HALT"
        return None

    # ------------------------------------------------------------------
    # Motor loop — rate limited, button-held base speed + X differential
    # ------------------------------------------------------------------

    def _motor_loop(self):
        was_moving = False

        while self._running:
            time.sleep(self._send_interval)

            with self._axis_lock:
                dx      = self._dx
                self._dx = 0

            if abs(dx) < config.MNT_DEADZONE:
                dx = 0

            if not self._enabled:
                was_moving = False
                continue

            # Base speed from held button — both buttons cancel out
            if self._fwd_held and not self._rev_held:
                base = config.MNT_MAX_DUTY
            elif self._rev_held and not self._fwd_held:
                base = -config.MNT_MAX_DUTY
            else:
                base = 0

            if base == 0:
                if was_moving:
                    self._on_command("MOTOR:0:0")
                was_moving = False
                continue

            # Differential steering: X offsets one motor down
            offset = int(dx * config.MNT_SPEED_SCALE)
            left  = _clamp(base - offset, config.MNT_MAX_DUTY)
            right = _clamp(base + offset, config.MNT_MAX_DUTY)

            self._on_command(f"MOTOR:{left}:{right}")
            was_moving = True
