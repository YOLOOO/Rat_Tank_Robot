"""
Common Hardware Layer
====================
Centralized hardware abstraction layer.
All GPIO access goes through here.
"""

from .leds import get_led_controller
from .motors import get_motor_controller
from .servos import get_servo_controller
from .distance import get_distance_sensor
from .tracking import get_tracking_sensor

__all__ = [
    "get_led_controller",
    "get_motor_controller",
    "get_servo_controller",
    "get_distance_sensor",
    "get_tracking_sensor",
]
