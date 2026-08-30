"""
RAT BRAIN - Core State Machine
=============================
State machine and mission orchestration for Rat OS.

States: IDLE, RUNNING_MISSION, ERROR
Menu:   missions only (defined in config.MISSIONS)
HALT:   checked directly from server halt_flag every tick — never queued,
        never blockable
"""

import faulthandler
import logging
import signal
import time
import importlib
from enum import Enum

import config
from rat_brain.control_receiver_server import get_command_server
import common_hardware.motor as motor
from common_hardware import get_led_controller, get_servo_controller
from behavior_scripts.led import patterns as led_patterns
from behavior_scripts.servo import ramp as servo_ramp

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Catches crashes that no Python try/except can ever see: a segfault/abort in
# a C extension (pigpio, lgpio, rpi_hardware_pwm) kills the interpreter before
# any exception handler runs, and normally leaves zero trace of why. This
# installs a low-level signal handler that dumps the native + Python stack of
# every thread to a dedicated file first. It can't help with an uncatchable
# SIGKILL (OOM killer) or a full board power-brownout/hang, but it is the one
# thing that can explain "crashed mid remote-control session, no clue why".
_crash_log = open("rat_brain_crash.log", "a", buffering=1)
faulthandler.enable(file=_crash_log, all_threads=True)


class RobotState(Enum):
    IDLE            = "IDLE"
    RUNNING_MISSION = "RUNNING_MISSION"
    ERROR           = "ERROR"


class RatBrain:
    """Core robot brain — state machine and mission coordinator."""

    def __init__(self):
        self.state          = RobotState.IDLE
        self.halt_flag      = False  # Readable by behaviors via check_halt.py
        self._running       = False  # Set to False to exit the main loop cleanly

        self.command_server = get_command_server()

        self.selection_index = 0
        self.running_mission = None
        self.mission_start_time = None
        self._error_since = None

        self.missions = {}
        self._load_missions()

        logger.info("RatBrain initialized")

    # ------------------------------------------------------------------
    # LED helper
    # ------------------------------------------------------------------

    def _set_led(self, color: tuple):
        try:
            led_patterns.static(color)
        except Exception as e:
            logger.warning(f"LED error: {e}")

    # ------------------------------------------------------------------
    # Mission loading
    # ------------------------------------------------------------------

    def _load_missions(self):
        """Import mission modules listed in config.MISSIONS."""
        for name, (module_path, color, order) in config.MISSIONS.items():
            try:
                module = importlib.import_module(module_path)
                self.missions[name] = {
                    "module": module,
                    "color":  color,
                    "order":  order,
                }
                logger.info(f"Loaded mission: {name}")
            except Exception as e:
                logger.error(f"Failed to load mission {name}: {e}")

    # ------------------------------------------------------------------
    # Menu helpers
    # ------------------------------------------------------------------

    def _menu_items(self) -> list:
        return sorted(self.missions.keys(), key=lambda n: self.missions[n]["order"])

    def _selected_name(self) -> str:
        items = self._menu_items()
        if not items:
            return ""
        return items[self.selection_index % len(items)]

    def _print_menu(self):
        items = self._menu_items()
        lines = ["", "=" * 50, "  RAT OS — MISSION SELECT", "=" * 50]
        for idx, name in enumerate(items):
            marker = "→" if idx == self.selection_index else " "
            bullet = "●" if idx == self.selection_index else "○"
            lines.append(f"  {marker} {bullet} {name}")
        lines.append("=" * 50)
        lines.append("  LEFT / RIGHT = scroll    SELECT = run    HALT = stop")
        lines.append("=" * 50)
        logger.info("\n".join(lines))

        self._set_menu_led()

    def _set_menu_led(self):
        """There is no persistent 'idle' LED state — at rest, the ring always
        shows the currently highlighted mission's color (LED_COLOR_IDLE is
        used only as a brief transition flash, see _flash_to_menu())."""
        selected = self._selected_name()
        if selected and selected in self.missions:
            self._set_led(self.missions[selected]["color"])
        else:
            self._set_led(config.LED_COLOR_IDLE)

    def _flash_to_menu(self):
        """Marks the transition back to mission-select (mission stopped, HALT,
        or ERROR recovery) with a brief green flash, then settles on the
        currently highlighted mission's color. Blocks for LED_MENU_FLASH_S —
        short and deliberate, not a hang risk."""
        self._set_led(config.LED_COLOR_IDLE)
        time.sleep(config.LED_MENU_FLASH_S)
        self._set_menu_led()

    # ------------------------------------------------------------------
    # HALT — checked directly from server flag, never queued
    # ------------------------------------------------------------------

    def _check_halt(self) -> bool:
        """Check server halt_flag. If set, process immediately and return True."""
        if self.command_server.halt_flag:
            self._process_halt()
            return True
        return False


    def _process_halt(self):
        # This is the last line of defense — clearing the halt flag and
        # returning to IDLE must happen no matter what fails above, or a
        # single hardware hiccup here leaves halt_flag stuck True forever.
        # _check_halt() is the first thing every state does, so a stuck
        # flag means _process_halt() gets retried every tick forever and
        # the brain never processes another command again (menu, mission
        # select, everything) — a total hang that looks like a dead robot
        # but isn't logged as one.
        self.halt_flag = True
        try:
            motor.stop()
        except Exception:
            logger.exception("Motor stop error during HALT")
        logger.warning("HALT — all motion stopped")
        try:
            self._stop_mission()
        finally:
            self.command_server.clear_halt()
            self.state     = RobotState.IDLE
            self.halt_flag = False

    # ------------------------------------------------------------------
    # State: IDLE
    # ------------------------------------------------------------------

    def _update_idle(self):
        if self._check_halt():
            return

        command = self.command_server.get_command(timeout=config.COMMAND_POLL_INTERVAL)
        items   = self._menu_items()

        if not items:
            return

        if command == "LEFT":
            self.selection_index = (self.selection_index - 1) % len(items)
            self._print_menu()
            logger.info(f"Selected: {self._selected_name()}")

        elif command == "RIGHT":
            self.selection_index = (self.selection_index + 1) % len(items)
            self._print_menu()
            logger.info(f"Selected: {self._selected_name()}")

        elif command == "SELECT":
            self._start_mission(self._selected_name())

    # ------------------------------------------------------------------
    # State: RUNNING_MISSION
    # ------------------------------------------------------------------

    def _update_running_mission(self):
        # HALT is always first — flag is set by receiver thread, not the queue
        if self._check_halt():
            return

        if self.running_mission is None:
            self.state = RobotState.IDLE
            return

        try:
            result = self.running_mission.run(self)
            if result is False or result is None:
                self._stop_mission()
                self.state = RobotState.IDLE

        except Exception:
            logger.exception("Mission error")
            self._stop_mission()
            self.state = RobotState.ERROR

    def _start_mission(self, name: str):
        mission_data = self.missions.get(name)
        if not mission_data:
            logger.error(f"Mission not found: {name}")
            self.state = RobotState.ERROR
            return

        module = importlib.reload(mission_data["module"])
        mission_data["module"] = module
        if not hasattr(module, "run"):
            logger.error(f"Mission {name} has no run() function")
            self.state = RobotState.ERROR
            return

        self.running_mission    = module
        self.mission_start_time = time.time()
        self.state              = RobotState.RUNNING_MISSION
        self._set_led(mission_data["color"])
        logger.info(f"Started mission: {name}")

    @staticmethod
    def _worst_case_start(target: float, ch_min: float, ch_max: float) -> float:
        """Whichever channel extreme is farther from target. Bootstrap
        fallback ONLY, for the rare case a channel has never been commanded
        this process lifetime (get_last_angle() returns None) — there is
        truly no information to go on yet. Once anything has commanded the
        servo even once, _park_and_stop_servos() ramps from that real
        tracked value instead, never this guess."""
        return ch_min if abs(target - ch_min) >= abs(target - ch_max) else ch_max

    def _park_and_stop_servos(self):
        """Uniform servo shutdown, called from _stop_mission() so it runs on
        every mission exit — HALT or a mission ending on its own — not just
        HALT. Eases both channels to the rest position (config.SERVO_PARK_*)
        using the same time-interpolated servo_ramp every other servo move
        in the codebase already uses, then cuts PWM.

        Deliberately not instant: a servo left de-energized during a
        servo-less mission (camera_test, sensory_test) has zero holding
        torque and can droop under gravity for the mission's whole duration
        with nothing noticing — this is open-loop, there's no true position
        feedback anywhere in this system. The fix is NOT "ramp from a
        guessed worst-case angle" — an earlier version of this method did
        that, and it just moved the slam: servo_ramp.step()'s very first
        call commands start_angle immediately, full speed, since the servo
        has no idea it's "step 1 of a ramp" — it just drives toward
        whatever PWM target it's given. Seeding that first frame with a
        guessed extreme instantly snapped the arm toward it exactly like
        the original bug, just relabeled.

        Instead this ramps from HardwareServo.get_last_angle() — the real
        last angle *commanded* to each channel, tracked centrally in
        common_hardware/servo.py since every servo move anywhere in the
        codebase funnels through its one setServoPwm(). That's not true
        physical position (a servo can still droop away from its last
        commanded angle while depowered, open-loop, same limitation as
        before), but it's always at least as accurate as a blind guess and
        normally far closer to reality, so the first frame is a small
        correction instead of an instant jump to an assumed extreme. The
        worst-case-extreme guess is now only a bootstrap fallback for a
        channel that has never been commanded at all this process lifetime.

        servo_ramp.step() is called without a brain argument (defaults to
        None) deliberately — command_server.halt_flag is still True for the
        whole time _process_halt() is inside this call (cleared only after
        _stop_mission() returns), so passing self would make is_halted()
        true and silently skip every servo command on exactly the path
        this exists to cover.
        """
        try:
            servo = get_servo_controller()

            arm_start = servo.get_last_angle('0')
            if arm_start is None:
                arm_start = self._worst_case_start(config.SERVO_PARK_ARM_ANGLE, config.SERVO_CH0_MIN, config.SERVO_CH0_MAX)

            grip_start = servo.get_last_angle('1')
            if grip_start is None:
                grip_start = self._worst_case_start(config.SERVO_PARK_GRIP_ANGLE, config.SERVO_CH1_MIN, config.SERVO_CH1_MAX)

            arm_duration  = servo_ramp.duration_for(arm_start,  config.SERVO_PARK_ARM_ANGLE,  config.SERVO_PARK_SPEED)
            grip_duration = servo_ramp.duration_for(grip_start, config.SERVO_PARK_GRIP_ANGLE, config.SERVO_PARK_SPEED)

            start_time = time.time()
            arm_done = grip_done = False
            while not (arm_done and grip_done):
                if not arm_done:
                    _, arm_done = servo_ramp.step('0', arm_start, config.SERVO_PARK_ARM_ANGLE,
                                                   start_time, arm_duration)
                if not grip_done:
                    _, grip_done = servo_ramp.step('1', grip_start, config.SERVO_PARK_GRIP_ANGLE,
                                                    start_time, grip_duration)
                time.sleep(0.02)

            servo.setServoStop('0')
            servo.setServoStop('1')
        except Exception:
            logger.exception("Servo park/stop error")

    def _stop_mission(self):
        try:
            motor.stop()
        except Exception:
            logger.exception("Motor stop error")
        self._park_and_stop_servos()
        # Missions that hold resources beyond a single run() call (background
        # threads, an open camera) never get another run() after HALT — the
        # brain drops straight to IDLE — so this is their only teardown hook.
        if self.running_mission is not None and hasattr(self.running_mission, "on_stop"):
            try:
                self.running_mission.on_stop(self)
            except Exception:
                logger.exception("Mission on_stop error")
        self.running_mission    = None
        self.mission_start_time = None
        self._flash_to_menu()
        logger.info("Mission stopped")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def update(self):
        try:
            if self.state == RobotState.IDLE:
                self._update_idle()

            elif self.state == RobotState.RUNNING_MISSION:
                self._update_running_mission()

            elif self.state == RobotState.ERROR:
                self._set_led(config.LED_COLOR_ERROR)
                if self._error_since is None:
                    self._error_since = time.time()
                    logger.error("Entered ERROR state — auto-recovering in 5s")
                elif time.time() - self._error_since > 5.0:
                    logger.info("Recovering from ERROR state → IDLE")
                    self._error_since = None
                    self.state = RobotState.IDLE
                    self._flash_to_menu()

        except Exception:
            logger.exception("Brain update error")
            self.state = RobotState.ERROR

    def _handle_signal(self, signum, _frame):
        logger.info(f"Signal {signum} received — shutting down")
        self._running = False

    def run(self):
        logger.info("RAT BRAIN STARTED")
        signal.signal(signal.SIGINT,  self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._running = True
        self.command_server.start()
        self._print_menu()

        try:
            while self._running:
                self.update()
                time.sleep(config.STATE_UPDATE_INTERVAL)

        except Exception:
            logger.exception("Fatal error")

        finally:
            self.cleanup()

    def cleanup(self):
        logger.info("Cleaning up...")
        self._stop_mission()
        motor.cleanup()
        try:
            servo = get_servo_controller()
            servo.setServoStop('0')
            servo.setServoStop('1')
        except Exception:
            logger.exception("Servo cleanup error")
        try:
            get_led_controller().led_close()
        except Exception as e:
            logger.warning(f"LED cleanup error: {e}")
        self.command_server.stop()
        logger.info("RAT BRAIN STOPPED")


def main():
    try:
        brain = RatBrain()
        brain.run()
    except Exception:
        logger.exception("RAT BRAIN crashed during startup")
        raise


if __name__ == "__main__":
    main()
