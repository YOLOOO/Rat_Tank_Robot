"""
RAT BRAIN - Core State Machine
=============================
Main state machine and behavior orchestration.
Manages IDLE, RUNNING_BEHAVIOR, RUNNING_MISSION, and ERROR states.
"""

import logging
import time
import sys
from enum import Enum
from typing import Optional
import importlib

# Add parent directory to path for config import
sys.path.insert(0, "..")

from config import BEHAVIORS, MISSIONS, MENU_ITEMS, STATE_UPDATE_INTERVAL, DEBUG
from rat_brain.control_receiver_server import get_command_server
from common_hardware import get_led_controller, get_motor_controller

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)


class RobotState(Enum):
    """Robot operational states."""
    IDLE = "IDLE"
    RUNNING_BEHAVIOR = "RUNNING_BEHAVIOR"
    RUNNING_MISSION = "RUNNING_MISSION"
    ERROR = "ERROR"


class RatBrain:
    """Core robot brain - state machine and behavior coordinator."""

    def __init__(self):
        """Initialize the robot brain."""
        self.state = RobotState.IDLE
        self.command_server = get_command_server()
        self.led_controller = get_led_controller()
        self.motor_controller = get_motor_controller()
        
        self.selection_index = 0
        self.running_behavior = None
        self.behavior_start_time = None
        
        # Load available behaviors and missions
        self.behaviors = {}
        self.missions = {}
        self._load_behaviors()
        self._load_missions()
        
        logger.info("RatBrain initialized")

    def _load_behaviors(self):
        """Load behavior modules."""
        for name, (module_path, color, order) in BEHAVIORS.items():
            if module_path is None:
                # IDLE doesn't have a module
                self.behaviors[name] = {"module": None, "color": color, "order": order}
            else:
                try:
                    module = importlib.import_module(module_path)
                    behavior = module.Behavior() if hasattr(module, "Behavior") else None
                    self.behaviors[name] = {
                        "module": behavior,
                        "color": color,
                        "order": order,
                    }
                    logger.info(f"Loaded behavior: {name}")
                except Exception as e:
                    logger.error(f"Failed to load behavior {name}: {e}")

    def _load_missions(self):
        """Load mission modules."""
        for name, (module_path, color, order) in MISSIONS.items():
            try:
                module = importlib.import_module(module_path)
                mission = module.Mission() if hasattr(module, "Mission") else None
                self.missions[name] = {
                    "module": mission,
                    "color": color,
                    "order": order,
                }
                logger.info(f"Loaded mission: {name}")
            except Exception as e:
                logger.error(f"Failed to load mission {name}: {e}")

    def _get_selected_item_name(self) -> str:
        """Get name of currently selected menu item."""
        if self.selection_index < len(MENU_ITEMS):
            return MENU_ITEMS[self.selection_index]
        return MENU_ITEMS[0]

    def _get_selected_item_color(self) -> tuple:
        """Get color of currently selected item."""
        item_name = self._get_selected_item_name()
        
        if item_name in self.behaviors:
            return self.behaviors[item_name]["color"]
        elif item_name in self.missions:
            return self.missions[item_name]["color"]
        
        return (255, 255, 255)  # White fallback

    def _update_idle_state(self):
        """Process commands and manage selection in IDLE state."""
        command = self.command_server.get_command(timeout=0.01)
        
        if command == "LEFT":
            self.selection_index = (self.selection_index - 1) % len(MENU_ITEMS)
            logger.info(f"Selection: {self._get_selected_item_name()}")
        
        elif command == "RIGHT":
            self.selection_index = (self.selection_index + 1) % len(MENU_ITEMS)
            logger.info(f"Selection: {self._get_selected_item_name()}")
        
        elif command == "SELECT":
            selected = self._get_selected_item_name()
            logger.info(f"Executing selected item: {selected}")
            
            if selected in self.behaviors:
                self._start_behavior(selected)
            elif selected in self.missions:
                self._start_mission(selected)
        
        # Flash LED with selection color
        selection_color = self._get_selected_item_color()
        self.led_controller.flash(selection_color, interval=0.5)

    def _start_behavior(self, behavior_name: str):
        """Start a behavior."""
        behavior_data = self.behaviors.get(behavior_name)
        if not behavior_data or behavior_data["module"] is None:
            logger.error(f"Cannot start behavior: {behavior_name}")
            self.state = RobotState.ERROR
            return
        
        self.running_behavior = behavior_data["module"]
        self.behavior_start_time = time.time()
        self.state = RobotState.RUNNING_BEHAVIOR
        logger.info(f"Started behavior: {behavior_name}")

    def _start_mission(self, mission_name: str):
        """Start a mission."""
        mission_data = self.missions.get(mission_name)
        if not mission_data or mission_data["module"] is None:
            logger.error(f"Cannot start mission: {mission_name}")
            self.state = RobotState.ERROR
            return
        
        self.running_behavior = mission_data["module"]  # Reuse for missions too
        self.behavior_start_time = time.time()
        self.state = RobotState.RUNNING_MISSION
        logger.info(f"Started mission: {mission_name}")

    def _update_running_state(self):
        """Execute current behavior/mission and check for completion."""
        if self.running_behavior is None:
            self.state = RobotState.IDLE
            return
        
        try:
            # Run the behavior
            if hasattr(self.running_behavior, "run"):
                result = self.running_behavior.run(self)
                
                # If run() returns False or None, consider it done
                if result is False or result is None:
                    self._stop_running()
                    self.state = RobotState.IDLE
        except Exception as e:
            logger.error(f"Behavior error: {e}")
            self._stop_running()
            self.state = RobotState.ERROR

    def _stop_running(self):
        """Stop current behavior and cleanup."""
        # Stop motors
        self.motor_controller.stop()
        
        # Turn off LEDs
        self.led_controller.turn_off()
        
        self.running_behavior = None
        self.behavior_start_time = None
        logger.info("Stopped running behavior/mission")

    def update(self):
        """Main update loop - called frequently."""
        try:
            if self.state == RobotState.IDLE:
                self._update_idle_state()
            
            elif self.state == RobotState.RUNNING_BEHAVIOR or self.state == RobotState.RUNNING_MISSION:
                self._update_running_state()
            
            elif self.state == RobotState.ERROR:
                # Flash red and wait for restart
                self.led_controller.flash((255, 0, 0), interval=0.3)
                time.sleep(0.1)
            
            # Update LED flashing
            self.led_controller.update()
        
        except Exception as e:
            logger.error(f"Brain update error: {e}")
            self.state = RobotState.ERROR

    def run(self):
        """Start the main brain loop."""
        logger.info("RAT BRAIN STARTED")
        self.command_server.start()
        
        try:
            while True:
                self.update()
                time.sleep(STATE_UPDATE_INTERVAL)
        
        except KeyboardInterrupt:
            logger.info("Brain interrupted by user")
        
        except Exception as e:
            logger.error(f"Brain fatal error: {e}")
        
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up...")
        self._stop_running()
        self.motor_controller.cleanup()
        self.led_controller.turn_off()
        self.command_server.stop()
        logger.info("RAT BRAIN STOPPED")


def main():
    """Entry point."""
    brain = RatBrain()
    brain.run()


if __name__ == "__main__":
    main()
