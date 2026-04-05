"""
MNT Reform Optical Trackball Backend (dev PC)
=============================================
Reads the MNT trackball via evdev and produces robot commands.

Only used inside the remote_control mission flow — NOT for menu navigation.

Ball → differential motor control:
    Y axis  → base speed (forward / backward)
    X axis  → turn offset (added/subtracted across tracks)
    left  = clamp(base - offset)
    right = clamp(base + offset)

Buttons:
    BTN_LEFT   (primary)  → ARM toggle
    BTN_RIGHT  (secondary)→ GRIP toggle
    BTN_MIDDLE (middle)   → HALT
    BTN_SIDE              → spare
    BTN_EXTRA             → spare

Install dependency on dev PC:
    pip install evdev
"""

import threading
import time
import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)

try:
    import evdev
    from evdev import ecodes
    _EVDEV_AVAILABLE = True
except ImportError:
    _EVDEV_AVAILABLE = False
    logger.error("evdev not installed — pip install evdev")


def _find_device() -> Optional["evdev.InputDevice"]:
    """Find the MNT trackball by matching device name."""
    if not _EVDEV_AVAILABLE:
        return None
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        if config.MNT_DEVICE_NAME.lower() in dev.name.lower():
            logger.info(f"Found MNT trackball: {dev.name} at {path}")
            return dev
        dev.close()
    logger.error(
        f"MNT trackball not found. "
        f"Looking for: '{config.MNT_DEVICE_NAME}'. "
        f"Available devices: {[evdev.InputDevice(p).name for p in evdev.list_devices()]}"
    )
    return None


def _clamp(value: int, limit: int) -> int:
    return max(-limit, min(limit, value))


class MntMouseBackend:
    """
    Reads MNT trackball in a background thread.
    Call get_command() from the sender loop to drain queued commands.
    """

    def __init__(self):
        self._device    = None
        self._thread    = None
        self._running   = False

        # Accumulated axis deltas between send ticks
        self._dx        = 0
        self._dy        = 0
        self._lock      = threading.Lock()

        # Command queue (small — only needs to buffer between read and send)
        self._commands  = []

        # Rate limiting
        self._send_interval = 1.0 / config.MNT_SEND_RATE
        self._last_send     = 0.0

    def start(self) -> bool:
        if not _EVDEV_AVAILABLE:
            return False
        self._device = _find_device()
        if self._device is None:
            return False
        self._running = True
        self._thread  = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
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
    # Background read loop
    # ------------------------------------------------------------------

    def _read_loop(self):
        try:
            for event in self._device.read_loop():
                if not self._running:
                    break

                if event.type == ecodes.EV_REL:
                    with self._lock:
                        if event.code == ecodes.REL_X:
                            self._dx += event.value
                        elif event.code == ecodes.REL_Y:
                            self._dy += event.value

                elif event.type == ecodes.EV_KEY and event.value == 1:  # key down only
                    cmd = self._map_button(event.code)
                    if cmd:
                        with self._lock:
                            self._commands.append(cmd)

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
        # BTN_SIDE, BTN_EXTRA — spare, ignore for now
        return None

    # ------------------------------------------------------------------
    # Called by sender loop to get next command
    # ------------------------------------------------------------------

    def get_command(self) -> Optional[str]:
        """
        Returns the next pending command, or a MOTOR command if enough
        time has passed and the ball has moved.
        Returns None if nothing to send yet.
        """
        with self._lock:
            # Button commands always go first
            if self._commands:
                return self._commands.pop(0)

            # Rate-limit motor commands
            now = time.monotonic()
            if now - self._last_send < self._send_interval:
                return None

            self._last_send = now
            dx, dy = self._dx, self._dy
            self._dx = 0
            self._dy = 0

        # Apply deadzone
        if abs(dx) < config.MNT_DEADZONE:
            dx = 0
        if abs(dy) < config.MNT_DEADZONE:
            dy = 0

        if dx == 0 and dy == 0:
            # Send a stop to keep motors from running if ball goes idle
            return "MOTOR:0:0"

        # Y is inverted — push ball forward (negative Y) = forward motion
        base   = int(-dy * config.MNT_SPEED_SCALE)
        offset = int( dx * config.MNT_SPEED_SCALE)

        left  = _clamp(base - offset, config.MNT_MAX_DUTY)
        right = _clamp(base + offset, config.MNT_MAX_DUTY)

        return f"MOTOR:{left}:{right}"
