"""
Steam Controller Backend (dev PC)
==================================
Reads a Steam Controller via pygame's game-controller API and fires
commands via callback.

Connect the controller through its wireless dongle ("the puck") with
Steam running and "Xbox Configuration Support" enabled (Steam > Big
Picture > Controller Settings). Steam then exposes the controller to
Windows as a standard XInput gamepad, which is what pygame reads here.

Two modes, toggled by the left stick click (L3):

  DRIVE mode (default):
    Left stick  Y   → left track speed
    Right stick Y   → right track speed

  ARM mode:
    Left stick  Y   → SERVO:0:delta  (arm fine adjust)
    Right stick Y   → SERVO:1:delta  (grip fine adjust)

Always active, regardless of mode:
    A button        → SELECT
    B button        → HALT
    X button        → ARM_TOGGLE
    Y button        → GRIP_TOGGLE
    D-Pad Left      → LEFT   (menu navigate)
    D-Pad Right     → RIGHT  (menu navigate)
    Back button     → QUIT
    Start button    → pause/resume controller output (local toggle, not sent to robot)
    L3 (stick click) → toggle DRIVE / ARM mode

Install dependency on dev PC:
    pip install pygame
"""

import threading
import time
import logging
from typing import Callable

import config

logger = logging.getLogger(__name__)

try:
    import pygame
    _PYGAME_AVAILABLE = True
except ImportError:
    _PYGAME_AVAILABLE = False
    logger.warning("pygame not installed — pip install pygame")


def _clamp(value: int, limit: int) -> int:
    return max(-limit, min(limit, value))


def _normalized_axis(raw: int) -> float:
    """Controller.get_axis() returns a raw SDL int (-32768..32767) — normalize to -1.0..1.0."""
    return max(-1.0, min(1.0, raw / 32768.0))


def _apply_deadzone(value: float, deadzone: float) -> float:
    return 0.0 if abs(value) < deadzone else value


class SteamControllerBackend:
    """
    Reads a Steam Controller (via XInput/pygame) in a background thread.
    Fires commands via on_command callback — same interface as KeyboardBackend.
    """

    def __init__(self, on_command: Callable[[str], None]):
        self._on_command = on_command
        self._controller = None
        self._thread      = None
        self._running     = False

        # Button edge-detection state — fire once per press, not once per tick
        self._prev_buttons = {}

        # Current mode: "drive" or "arm"
        self._mode = "drive"

        # Output rate limiting
        self._poll_interval = 1.0 / config.STEAM_POLL_RATE

        # Start-button toggle — when False no commands are forwarded to the robot
        self._enabled = True

    def start(self) -> bool:
        """Start the backend. Returns True if a controller was found."""
        if not _PYGAME_AVAILABLE:
            return False

        pygame.init()
        pygame.controller.init()

        if pygame.controller.get_count() == 0:
            logger.warning(
                "No controller found — is the Steam Controller dongle plugged in "
                "and Steam running with Xbox Configuration Support enabled?"
            )
            return False

        self._controller = pygame.controller.Controller(0)
        self._controller.init()
        logger.info(f"Found controller: {self._controller.get_name()}")

        self._running = True
        self._thread  = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Steam controller backend started (DRIVE mode)")
        return True

    def stop(self):
        self._running = False
        if _PYGAME_AVAILABLE:
            try:
                pygame.controller.quit()
                pygame.quit()
            except Exception:
                pass

    def toggle_enabled(self):
        """Toggle whether controller commands are forwarded to the robot (Start button / P key)."""
        self._enabled = not self._enabled
        state = "ENABLED" if self._enabled else "PAUSED"
        logger.info(f"Steam controller backend {state}")

    def is_enabled(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # Background poll loop
    # ------------------------------------------------------------------

    def _poll_loop(self):
        was_moving = False

        while self._running:
            time.sleep(self._poll_interval)
            pygame.event.pump()

            self._handle_buttons()

            if not self._enabled:
                was_moving = False
                continue

            left_y  = _apply_deadzone(_normalized_axis(self._controller.get_axis(pygame.CONTROLLER_AXIS_LEFTY)), config.STEAM_DEADZONE)
            right_y = _apply_deadzone(_normalized_axis(self._controller.get_axis(pygame.CONTROLLER_AXIS_RIGHTY)), config.STEAM_DEADZONE)

            if self._mode == "drive":
                was_moving = self._tick_drive(left_y, right_y, was_moving)
            else:
                self._tick_arm(left_y, right_y)
                was_moving = False

    def _button_pressed(self, button: int) -> bool:
        """Edge-detect: True only on the tick a button transitions up -> down."""
        now  = bool(self._controller.get_button(button))
        was  = self._prev_buttons.get(button, False)
        self._prev_buttons[button] = now
        return now and not was

    def _handle_buttons(self):
        if self._button_pressed(pygame.CONTROLLER_BUTTON_LEFTSTICK):
            self._toggle_mode()
            return  # mode toggle always works, even while paused

        tracked = (
            pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_B,
            pygame.CONTROLLER_BUTTON_X, pygame.CONTROLLER_BUTTON_Y,
            pygame.CONTROLLER_BUTTON_BACK, pygame.CONTROLLER_BUTTON_START,
            pygame.CONTROLLER_BUTTON_DPAD_LEFT, pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
        )

        if not self._enabled:
            # Still consume edges so nothing "fires late" once re-enabled
            for button in tracked:
                self._button_pressed(button)
            return

        if self._button_pressed(pygame.CONTROLLER_BUTTON_A):
            self._on_command("SELECT")
        if self._button_pressed(pygame.CONTROLLER_BUTTON_B):
            self._on_command("HALT")
        if self._button_pressed(pygame.CONTROLLER_BUTTON_X):
            self._on_command("ARM_TOGGLE")
        if self._button_pressed(pygame.CONTROLLER_BUTTON_Y):
            self._on_command("GRIP_TOGGLE")
        if self._button_pressed(pygame.CONTROLLER_BUTTON_DPAD_LEFT):
            self._on_command("LEFT")
        if self._button_pressed(pygame.CONTROLLER_BUTTON_DPAD_RIGHT):
            self._on_command("RIGHT")
        if self._button_pressed(pygame.CONTROLLER_BUTTON_BACK):
            self._on_command("QUIT")
        if self._button_pressed(pygame.CONTROLLER_BUTTON_START):
            self.toggle_enabled()

    def _toggle_mode(self):
        self._mode = "arm" if self._mode == "drive" else "drive"
        label = self._mode.upper()
        logger.info(f"Steam controller mode: {label}")
        print(f"  Steam controller mode: {label}")

    # ------------------------------------------------------------------
    # Output — rate limited, drives motors or servos depending on mode
    # ------------------------------------------------------------------

    def _tick_drive(self, left_y: float, right_y: float, was_moving: bool) -> bool:
        # Stick Y is inverted (up = negative) — flip so pushing up drives forward
        left  = _clamp(int(-left_y * config.STEAM_MAX_DUTY), config.STEAM_MAX_DUTY)
        right = _clamp(int(-right_y * config.STEAM_MAX_DUTY), config.STEAM_MAX_DUTY)

        if left != 0 or right != 0:
            self._on_command(f"MOTOR:{left}:{right}")
            return True
        elif was_moving:
            self._on_command("MOTOR:0:0")
        return False

    def _tick_arm(self, left_y: float, right_y: float):
        if left_y != 0.0:
            scaled = int(-left_y * config.STEAM_ARM_SCALE)
            if scaled:
                self._on_command(f"SERVO:0:{scaled}")
        if right_y != 0.0:
            scaled = int(-right_y * config.STEAM_ARM_SCALE)
            if scaled:
                self._on_command(f"SERVO:1:{scaled}")
