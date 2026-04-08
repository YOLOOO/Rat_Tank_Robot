"""
MNT Reform Optical Trackball Backend (dev PC)
=============================================
Reads the MNT trackball via evdev and fires commands via callback.

Ball → differential motor control:
    Y axis  → base speed (forward / backward)
    X axis  → turn offset (differential steering)
    left  = clamp(base - offset)
    right = clamp(base + offset)

Buttons:
    BTN_LEFT   (primary)   → ARM_TOGGLE
    BTN_RIGHT  (secondary) → GRIP_TOGGLE
    BTN_MIDDLE (middle)    → HALT
    BTN_SIDE               → spare
    BTN_EXTRA              → spare

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

        # Accumulated axis deltas between send ticks
        self._dx            = 0
        self._dy            = 0
        self._axis_lock     = threading.Lock()

        # Motor send rate limiting
        self._send_interval = 1.0 / config.MNT_SEND_RATE
        self._last_send     = 0.0

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
        # Motor tick runs on its own timer thread
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

    # ------------------------------------------------------------------
    # Background read loop — buttons fire immediately
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
                        elif event.code == ecodes.REL_Y:
                            self._dy += event.value

                elif event.type == ecodes.EV_KEY and event.value == 1:  # key down only
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
        return None  # BTN_SIDE, BTN_EXTRA spare

    # ------------------------------------------------------------------
    # Motor loop — rate limited, converts accumulated deltas to MOTOR cmd
    # ------------------------------------------------------------------

    def _motor_loop(self):
        was_moving = False

        while self._running:
            time.sleep(self._send_interval)

            with self._axis_lock:
                dx, dy = self._dx, self._dy
                self._dx = 0
                self._dy = 0

            # Apply deadzone
            if abs(dx) < config.MNT_DEADZONE:
                dx = 0
            if abs(dy) < config.MNT_DEADZONE:
                dy = 0

            is_moving = dx != 0 or dy != 0

            if not is_moving:
                if was_moving:
                    self._on_command("MOTOR:0:0")  # one clean stop, then silence
                was_moving = False
                continue

            # Y inverted — push forward (negative Y) = forward motion
            base   = int( dy * config.MNT_SPEED_SCALE)
            offset = int( dx * config.MNT_SPEED_SCALE)

            left  = _clamp(base - offset, config.MNT_MAX_DUTY)
            right = _clamp(base + offset, config.MNT_MAX_DUTY)

            self._on_command(f"MOTOR:{left}:{right}")
            was_moving = True
