"""
PATROL Behavior
==============
Robot moves forward and backward in a simple pattern.
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
    """Patrol behavior - simple forward/backward movement."""

    name = "PATROL"
    color = (0, 0, 255)  # Blue

    def __init__(self):
        self.start_time = None
        self.direction = 1  # 1 = forward, -1 = backward
        self.phase_duration = 2.0  # seconds before changing direction

    def run(self, brain) -> bool:
        """
        Execute patrol routine.
        """
        if self.start_time is None:
            self.start_time = time.time()
            logger.info("Patrol started!")

        elapsed = time.time() - self.start_time
        phase = int(elapsed / self.phase_duration) % 6

        # LED color during patrol
        brain.led_controller.set_color(self.color)

        # Change direction every phase
        if phase % 2 == 0:
            brain.motor_controller.forward(120)
        else:
            brain.motor_controller.backward(120)

        # End patrol after 12 seconds (6 phases)
        if phase == 5 and elapsed % self.phase_duration > self.phase_duration * 0.9:
            brain.motor_controller.stop()
            return False

        return True
