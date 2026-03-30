"""
DANCE DEMO Behavior
==================
Robot spins and moves in a demo pattern.
"""

import time
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from behavior_scripts.base_behavior import BaseBehavior

logger = logging.getLogger(__name__)


class Behavior(BaseBehavior):
    """Dance behavior - spin, move, and show off."""

    name = "DANCE"
    color = (255, 0, 255)  # Magenta

    def __init__(self):
        self.start_time = None
        self.phase = 0
        self.phase_duration = 1.0  # seconds per phase

    def run(self, brain) -> bool:
        """
        Execute dance routine.
        """
        if self.start_time is None:
            self.start_time = time.time()
            logger.info("Dance started!")

        elapsed = time.time() - self.start_time
        phase = int(elapsed / self.phase_duration) % 8

        # LED color during dance
        brain.led_controller.set_color(self.color)

        # 8-phase dance routine
        if phase == 0:
            brain.motor_controller.spin_left(150)
        elif phase == 1:
            brain.motor_controller.forward(150)
        elif phase == 2:
            brain.motor_controller.spin_right(150)
        elif phase == 3:
            brain.motor_controller.backward(150)
        elif phase == 4:
            brain.motor_controller.spin_left(100)
        elif phase == 5:
            brain.motor_controller.forward(100)
        elif phase == 6:
            brain.motor_controller.spin_right(100)
        elif phase == 7:
            brain.motor_controller.stop()
            # End dance after 8 phases
            return False

        return True
