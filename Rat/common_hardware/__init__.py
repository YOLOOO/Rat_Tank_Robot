"""
Common Hardware Layer
====================
Centralized hardware abstraction layer.
All GPIO access goes through here.
"""
from config import SERVO_PCB_VERSION, SERVO_HZ
from .spi_ledpixel import Freenove_SPI_LedPixel
from .motor import tankMotor
from .servo import PigpioServo


_led_controller = None
_motor_controller = None
_servo_controller = None

def get_led_controller():
    """Get or create the LED controller singleton."""
    global _led_controller
    if _led_controller is None:
        _led_controller = Freenove_SPI_LedPixel()
    return _led_controller

def get_motor_controller():
    """Get or create the motor controller singleton."""
    global _motor_controller
    if _motor_controller is None:
        _motor_controller = tankMotor()
    return _motor_controller

def get_servo_controller():
    """Get or create the servo controller singleton."""
    global _servo_controller
    if _servo_controller is None:
        _servo_controller = PigpioServo(SERVO_PCB_VERSION, SERVO_HZ)
    return _servo_controller

__all__ = [
    "get_led_controller",
    "get_motor_controller",
    "get_servo_controller"
]
