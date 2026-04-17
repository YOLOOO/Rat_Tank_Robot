"""
MNT Reform Optical Trackball Backend (dev PC)
=============================================
Reads the MNT trackball via evdev and fires commands via callback.

Two modes, toggled by BTN_MIDDLE:

  DRIVE mode (default):
    BTN_LEFT  held    → full-speed forward (hold to drive)
    BTN_RIGHT held    → full-speed backward (hold to drive)
    Ball X            → differential steering while a direction is held
    Ball Y            → ignored

  ARM mode:
    BTN_LEFT  click   → ARM_TOGGLE
    BTN_RIGHT click   → GRIP_TOGGLE
    Ball X            → SERVO:1:delta  (grip fine adjust)
    Ball Y            → SERVO:0:delta  (arm fine adjust)

Both modes:
    BTN_MIDDLE click  → toggle drive/arm mode (local, no robot command)
    P key (keyboard)  → pause/resume all MNT output

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

        # Accumulated ball deltas between output ticks
        self._dx            = 0
        self._dy            = 0
        self._axis_lock     = threading.Lock()

        # Drive mode held state
        self._fwd_held      = False
        self._rev_held      = False

        # Current mode: "drive" or "arm"
        self._mode          = "drive"

        # Output rate limiting
        self._send_interval = 1.0 / config.MNT_SEND_RATE

        # P-key toggle — when False no commands are forwarded to the robot
        self._enabled       = True

    def start(self) -> bool:
        """Start the backend. Returns True if trackball was found."""
        if not _EVDEV_AVAILABLE:
            return False
        self._device = _find_device()
        if self._device is None:
            return False
        self._running    = True
        self._thread     = threading.Thread(target=self._read_loop, daemon=True)
        self._output_thread = threading.Thread(target=self._output_loop, daemon=True)
        self._thread.start()
        self._output_thread.start()
        logger.info("MNT backend started (DRIVE mode)")
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
                        elif event.code == ecodes.REL_Y:
                            self._dy += event.value

                elif event.type == ecodes.EV_KEY:
                    self._handle_button(event.code, event.value)

        except Exception as e:
            if self._running:
                logger.error(f"MNT read error: {e}")

    def _handle_button(self, code: int, value: int):
        # BTN_MIDDLE always toggles mode, regardless of enabled state
        if code == ecodes.BTN_MIDDLE and value == 1:
            self._toggle_mode()
            return

        if not self._enabled:
            return

        if self._mode == "drive":
            if code == ecodes.BTN_LEFT:
                self._fwd_held = (value == 1)
            elif code == ecodes.BTN_RIGHT:
                self._rev_held = (value == 1)

        else:  # arm mode — fire on keydown only
            if value != 1:
                return
            if code == ecodes.BTN_LEFT:
                self._on_command("ARM_TOGGLE")
            elif code == ecodes.BTN_RIGHT:
                self._on_command("GRIP_TOGGLE")

    def _toggle_mode(self):
        self._mode     = "arm" if self._mode == "drive" else "drive"
        self._fwd_held = False
        self._rev_held = False
        # Discard any ball movement accumulated before the switch
        with self._axis_lock:
            self._dx = 0
            self._dy = 0
        label = self._mode.upper()
        logger.info(f"MNT mode: {label}")
        print(f"  MNT mode: {label}")

    # ------------------------------------------------------------------
    # Output loop — rate limited, drives motors or servos depending on mode
    # ------------------------------------------------------------------

    def _output_loop(self):
        was_moving = False

        while self._running:
            time.sleep(self._send_interval)

            with self._axis_lock:
                dx       = self._dx
                dy       = self._dy
                self._dx = 0
                self._dy = 0

            if not self._enabled:
                was_moving = False
                continue

            if self._mode == "drive":
                was_moving = self._tick_drive(dx, was_moving)
            else:
                self._tick_arm(dx, dy)
                was_moving = False

    def _tick_drive(self, dx: int, was_moving: bool) -> bool:
        if abs(dx) < config.MNT_DEADZONE:
            dx = 0

        if self._fwd_held and not self._rev_held:
            base = config.MNT_MAX_DUTY
        elif self._rev_held and not self._fwd_held:
            base = -config.MNT_MAX_DUTY
        else:
            base = 0

        if base == 0:
            if was_moving:
                self._on_command("MOTOR:0:0")
            return False

        offset = int(dx * config.MNT_SPEED_SCALE)
        left   = _clamp(base - offset, config.MNT_MAX_DUTY)
        right  = _clamp(base + offset, config.MNT_MAX_DUTY)
        self._on_command(f"MOTOR:{left}:{right}")
        return True

    def _tick_arm(self, dx: int, dy: int):
        # X → grip (servo ch1), Y → arm (servo ch0)
        if abs(dx) >= config.MNT_DEADZONE:
            scaled = int(dx * config.MNT_ARM_SCALE)
            if scaled:
                self._on_command(f"SERVO:1:{scaled}")
        if abs(dy) >= config.MNT_DEADZONE:
            scaled = int(dy * config.MNT_ARM_SCALE)
            if scaled:
                self._on_command(f"SERVO:0:{scaled}")
