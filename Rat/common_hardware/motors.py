"""
Motor Hardware Abstraction
==========================
Controls tank robot movement (2 motors, left and right).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MotorController:
    """
    Abstraction for tank motor control.
    Tank has two independent motors (left and right).
    """

    def __init__(
        self,
        left_forward_pin: int = 12,
        left_backward_pin: int = 11,
        right_forward_pin: int = 8,
        right_backward_pin: int = 7,
        pwm_freq: int = 1000,
    ):
        """
        Initialize motor controller.
        
        Args:
            left_forward_pin: GPIO pin for left motor forward
            left_backward_pin: GPIO pin for left motor backward
            right_forward_pin: GPIO pin for right motor forward
            right_backward_pin: GPIO pin for right motor backward
            pwm_freq: PWM frequency in Hz
        """
        self.left_forward_pin = left_forward_pin
        self.left_backward_pin = left_backward_pin
        self.right_forward_pin = right_forward_pin
        self.right_backward_pin = right_backward_pin
        self.pwm_freq = pwm_freq

        self.left_speed = 0
        self.right_speed = 0
        self.hardware_available = False

        # Try to import GPIO library
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Setup pins as output
            for pin in [left_forward_pin, left_backward_pin, right_forward_pin, right_backward_pin]:
                GPIO.setup(pin, GPIO.OUT)
            
            # Setup PWM
            self.left_fwd_pwm = GPIO.PWM(left_forward_pin, pwm_freq)
            self.left_bwd_pwm = GPIO.PWM(left_backward_pin, pwm_freq)
            self.right_fwd_pwm = GPIO.PWM(right_forward_pin, pwm_freq)
            self.right_bwd_pwm = GPIO.PWM(right_backward_pin, pwm_freq)
            
            self.left_fwd_pwm.start(0)
            self.left_bwd_pwm.start(0)
            self.right_fwd_pwm.start(0)
            self.right_bwd_pwm.start(0)
            
            self.hardware_available = True
            logger.info("Motor controller initialized")
        except ImportError:
            logger.warning("RPi.GPIO not available - running in simulation mode")
        except RuntimeError as e:
            logger.error(f"GPIO setup failed: {e} - continuing in simulation mode")

    def _set_motor(self, fwd_pwm, bwd_pwm, speed: int):
        """
        Set a single motor speed and direction.
        
        Args:
            fwd_pwm: Forward PWM object
            bwd_pwm: Backward PWM object
            speed: -255 to 255 (negative = backward)
        """
        speed = max(-255, min(255, speed))  # Clamp to range

        if not self.hardware_available:
            return

        if speed > 0:  # Forward
            fwd_pwm.ChangeDutyCycle(speed)
            bwd_pwm.ChangeDutyCycle(0)
        elif speed < 0:  # Backward
            fwd_pwm.ChangeDutyCycle(0)
            bwd_pwm.ChangeDutyCycle(-speed)
        else:  # Stop
            fwd_pwm.ChangeDutyCycle(0)
            bwd_pwm.ChangeDutyCycle(0)

    def forward(self, speed: int = 100):
        """Move forward at given speed (0-255)."""
        self.left_speed = speed
        self.right_speed = speed
        self._set_motor(self.left_fwd_pwm, self.left_bwd_pwm, speed)
        self._set_motor(self.right_fwd_pwm, self.right_bwd_pwm, speed)
        logger.debug(f"Forward: speed={speed}")

    def backward(self, speed: int = 100):
        """Move backward at given speed (0-255)."""
        self.forward(-speed)
        logger.debug(f"Backward: speed={speed}")

    def spin_left(self, speed: int = 100):
        """Spin left at given speed (0-255)."""
        self.left_speed = -speed
        self.right_speed = speed
        self._set_motor(self.left_fwd_pwm, self.left_bwd_pwm, -speed)
        self._set_motor(self.right_fwd_pwm, self.right_bwd_pwm, speed)
        logger.debug(f"Spin left: speed={speed}")

    def spin_right(self, speed: int = 100):
        """Spin right at given speed (0-255)."""
        self.left_speed = speed
        self.right_speed = -speed
        self._set_motor(self.left_fwd_pwm, self.left_bwd_pwm, speed)
        self._set_motor(self.right_fwd_pwm, self.right_bwd_pwm, -speed)
        logger.debug(f"Spin right: speed={speed}")

    def stop(self):
        """Stop all motors immediately."""
        self.left_speed = 0
        self.right_speed = 0
        self._set_motor(self.left_fwd_pwm, self.left_bwd_pwm, 0)
        self._set_motor(self.right_fwd_pwm, self.right_bwd_pwm, 0)
        logger.debug("Stopped")

    def cleanup(self):
        """Cleanup GPIO resources."""
        self.stop()
        if self.hardware_available:
            try:
                self.left_fwd_pwm.stop()
                self.left_bwd_pwm.stop()
                self.right_fwd_pwm.stop()
                self.right_bwd_pwm.stop()
                self.GPIO.cleanup()
                logger.info("Motor controller cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


# Singleton instance
_motor_controller = None


def get_motor_controller() -> MotorController:
    """Get or create the motor controller singleton."""
    global _motor_controller
    if _motor_controller is None:
        from config import (
            MOTOR_LEFT_FORWARD,
            MOTOR_LEFT_BACKWARD,
            MOTOR_RIGHT_FORWARD,
            MOTOR_RIGHT_BACKWARD,
            MOTOR_PWM_FREQ,
        )
        _motor_controller = MotorController(
            MOTOR_LEFT_FORWARD,
            MOTOR_LEFT_BACKWARD,
            MOTOR_RIGHT_FORWARD,
            MOTOR_RIGHT_BACKWARD,
            MOTOR_PWM_FREQ,
        )
    return _motor_controller
