"""
Tracking Sensor Hardware Abstraction
====================================
Reads from tracking/line-following sensor.
"""

import logging

logger = logging.getLogger(__name__)


class TrackingSensor:
    """Tracking/line-following sensor abstraction."""

    def __init__(self, pin: int = 27):
        """
        Initialize tracking sensor.
        
        Args:
            pin: GPIO pin number
        """
        self.pin = pin
        self.hardware_available = False
        self.last_value = 0

        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.IN)
            self.hardware_available = True
            logger.info(f"Tracking sensor initialized on pin {pin}")
        except ImportError:
            logger.warning("Tracking sensor library not available - simulation mode")

    def read_value(self) -> int:
        """
        Read tracking sensor value.
        
        Returns:
            Sensor value (0 or 1 for digital, or 0-255 for analog in simulation)
        """
        if not self.hardware_available:
            return 0  # Simulate no tracking in demo mode

        try:
            # In real implementation, would read GPIO or ADC
            self.last_value = 0
            return self.last_value
        except Exception as e:
            logger.error(f"Error reading tracking sensor: {e}")
            return self.last_value

    def is_tracking_line(self) -> bool:
        """Check if sensor is tracking a line."""
        return self.read_value() > 128


# Singleton instance
_tracking_sensor = None


def get_tracking_sensor(pin: int = 27) -> TrackingSensor:
    """Get or create the tracking sensor singleton."""
    global _tracking_sensor
    if _tracking_sensor is None:
        _tracking_sensor = TrackingSensor(pin)
    return _tracking_sensor
