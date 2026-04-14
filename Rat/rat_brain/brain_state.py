"""
RAT BRAIN - Core State Machine
=============================
State machine and mission orchestration for Rat OS.

States: IDLE, RUNNING_MISSION, ERROR
Menu:   missions only (defined in config.MISSIONS)
HALT:   checked directly from server halt_flag every tick — never queued,
        never blockable
"""

import logging
import time
import importlib
from enum import Enum

import config
from rat_brain.control_receiver_server import get_command_server
import common_hardware.motor as motor
from common_hardware import get_led_controller

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG if config.DEBUG else logging.INFO)


class RobotState(Enum):
    IDLE            = "IDLE"
    RUNNING_MISSION = "RUNNING_MISSION"
    ERROR           = "ERROR"


class RatBrain:
    """Core robot brain — state machine and mission coordinator."""

    def __init__(self):
        self.state          = RobotState.IDLE
        self.halt_flag      = False  # Readable by behaviors via check_halt.py

        self.command_server = get_command_server()

        self.selection_index = 0
        self.running_mission = None
        self.mission_start_time = None

        self.missions = {}
        self._load_missions()

        logger.info("RatBrain initialized")

    # ------------------------------------------------------------------
    # LED helper
    # ------------------------------------------------------------------

    def _set_led(self, color: tuple):
        try:
            r, g, b = color
            get_led_controller().set_all_led_rgb([r, g, b])
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
        print("\n" + "=" * 50)
        print("  RAT OS — MISSION SELECT")
        print("=" * 50)
        for idx, name in enumerate(items):
            marker = "→" if idx == self.selection_index else " "
            bullet = "●" if idx == self.selection_index else "○"
            print(f"  {marker} {bullet} {name}")
        print("=" * 50)
        print("  LEFT / RIGHT = scroll    SELECT = run    HALT = stop")
        print("=" * 50 + "\n")

        selected = self._selected_name()
        if selected and selected in self.missions:
            self._set_led(self.missions[selected]["color"])
        else:
            self._set_led(config.LED_COLORS["idle"])

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
        self.halt_flag = True
        motor.stop()
        logger.warning("HALT — all motion stopped")
        self._stop_mission()
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

        except Exception as e:
            logger.error(f"Mission error: {e}")
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

    def _stop_mission(self):
        motor.stop()
        self.running_mission    = None
        self.mission_start_time = None
        self._set_led(config.LED_COLORS["idle"])
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
                self._set_led(config.LED_COLORS["error"])
                time.sleep(0.3)

        except Exception as e:
            logger.error(f"Brain update error: {e}")
            self.state = RobotState.ERROR

    def run(self):
        logger.info("RAT BRAIN STARTED")
        self.command_server.start()
        self._print_menu()

        try:
            while True:
                self.update()
                time.sleep(config.STATE_UPDATE_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Interrupted")

        except Exception as e:
            logger.error(f"Fatal error: {e}")

        finally:
            self.cleanup()

    def cleanup(self):
        logger.info("Cleaning up...")
        self._stop_mission()
        motor.cleanup()
        try:
            get_led_controller().led_close()
        except Exception as e:
            logger.warning(f"LED cleanup error: {e}")
        self.command_server.stop()
        logger.info("RAT BRAIN STOPPED")


def main():
    brain = RatBrain()
    brain.run()


if __name__ == "__main__":
    main()
