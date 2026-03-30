"""
SCAN / TOY CAR PICKER Behavior
=============================
Robot simulates scanning for targets and displays detection pattern.
Placeholder for sensor integration later.
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
    """
    Scan/search behavior - robot simulates looking for targets.
    Stub implementation: will integrate real sensors later.
    """

    name = "SCAN"
    color = (255, 255, 0)  # Yellow

    def __init__(self):
        self.start_time = None
        self.scan_duration = 0.5  # seconds per scan direction
        self.total_duration = 8.0  # Total scan time

    def run(self, brain) -> bool:
        """
        Execute scanning routine with LED feedback.
        """
        if self.start_time is None:
            self.start_time = time.time()
            logger.info("Scan started!")

        elapsed = time.time() - self.start_time

        # Scanning pattern
        scan_phase = int(elapsed / self.scan_duration) % 8

        # LED pulses to show scanning
        brain.led_controller.set_color(self.color)

        # Spin pattern to simulate scanning
        if scan_phase < 4:
            brain.motor_controller.spin_left(100)
        else:
            brain.motor_controller.spin_right(100)

        # After total duration, stop
        if elapsed >= self.total_duration:
            brain.motor_controller.stop()
            logger.info("Scan complete!")
            return False

        return True
