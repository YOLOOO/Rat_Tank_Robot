"""
Base Behavior Class
==================
Template for all behaviors.
"""

from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseBehavior(ABC):
    """Base class for all robot behaviors."""

    name = "UnnamedBehavior"
    color = (255, 255, 255)  # RGB

    @abstractmethod
    def run(self, brain) -> bool:
        """
        Run one iteration of the behavior.
        
        Args:
            brain: RatBrain instance with access to motors, LEDs, etc.
        
        Returns:
            True to continue, False/None to stop and return to IDLE
        """
        pass

    def cleanup(self):
        """Optional cleanup when behavior ends."""
        pass
