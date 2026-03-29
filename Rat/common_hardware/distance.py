"""
Distance Sensor Hardware Abstraction
====================================
Reads distance from ultrasonic sensor.
"""

import logging
import time

logger = logging.getLogger(__name__)


class DistanceSensor:
    """Ultrasonic distance sensor abstraction."""

    def __init__(self, pin: int = 17):
        """
        Initialize distance sensor.
        
        Args:
            pin: GPIO pin number
        """
        self.pin = pin
        self.hardware_available = False
        self.last_distance = 0

        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.IN)
            self.hardware_available = True
            logger.info(f"Distance sensor initialized on pin {pin}")
        except ImportError:
            logger.warning("Distance sensor library not available - simulation mode")

    def read_distance(self) -> float:
        """
        Read distance in cm.
        
        Returns:
            Distance in centimeters (or 0 in simulation)
        """
        if not self.hardware_available:
            return 50.0  # Simulate 50cm in demo mode

        try:
            # Simplified ultrasonic reading
            # In real implementation, would toggle trigger and measure echo time
            self.last_distance = 50.0  # Placeholder
            return self.last_distance
        except Exception as e:
            logger.error(f"Error reading distance: {e}")
            return self.last_distance


# Singleton instance
_distance_sensor = None


def get_distance_sensor(pin: int = 17) -> DistanceSensor:
    """Get or create the distance sensor singleton."""
    global _distance_sensor
    if _distance_sensor is None:
        _distance_sensor = DistanceSensor(pin)
    return _distance_sensor
