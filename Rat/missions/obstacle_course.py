"""
OBSTACLE COURSE Mission
======================
Navigate through obstacle course with turns and movements.
Stub implementation.
"""

import time
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from behavior_scripts.base_behavior import BaseBehavior

logger = logging.getLogger(__name__)


class Mission(BaseBehavior):
    """Obstacle Course - navigate and overcome challenges."""

    name = "OBSTACLE"
    color = (255, 165, 0)  # Orange

    def __init__(self):
        self.start_time = None
        self.phase_duration = 1.5

    def run(self, brain) -> bool:
        """Execute obstacle course mission."""
        if self.start_time is None:
            self.start_time = time.time()
            logger.info("OBSTACLE COURSE mission started!")

        elapsed = time.time() - self.start_time
        phase = int(elapsed / self.phase_duration) % 8

        brain.led_controller.set_color(self.color)

        # Navigate obstacle course
        if phase == 0:
            brain.motor_controller.forward(100)
        elif phase == 1:
            brain.motor_controller.spin_right(120)
        elif phase == 2:
            brain.motor_controller.forward(100)
        elif phase == 3:
            brain.motor_controller.spin_left(120)
        elif phase == 4:
            brain.motor_controller.forward(100)
        elif phase == 5:
            brain.motor_controller.backward(80)
        elif phase == 6:
            brain.motor_controller.spin_right(100)
        elif phase == 7:
            brain.motor_controller.stop()
            logger.info("OBSTACLE COURSE mission complete!")
            return False

        return True
