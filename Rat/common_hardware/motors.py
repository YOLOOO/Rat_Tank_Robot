"""
Motor Hardware Abstraction
==========================
Controls tank robot movement (2 motors, left and right).
Uses gpiozero.Motor for reliable GPIO control.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MotorController:
    """
    Abstraction for tank motor control.
    Tank has two independent motors (left and right).
    Uses gpiozero.Motor for hardware control.
    """

    def __init__(
        self,
        left_forward_pin: int = 24,
        left_backward_pin: int = 23,
        right_forward_pin: int = 5,
        right_backward_pin: int = 6,
    ):
        """
        Initialize motor controller using gpiozero.
        
        Args:
            left_forward_pin: GPIO pin for left motor forward
            left_backward_pin: GPIO pin for left motor backward
            right_forward_pin: GPIO pin for right motor forward
            right_backward_pin: GPIO pin for right motor backward
        """
        self.left_forward_pin = left_forward_pin
        self.left_backward_pin = left_backward_pin
        self.right_forward_pin = right_forward_pin
        self.right_backward_pin = right_backward_pin

        self.left_speed = 0
        self.right_speed = 0
        self.hardware_available = False
        self.left_motor = None
        self.right_motor = None

        # Try to import and initialize gpiozero Motors
        try:
            from gpiozero import Motor
            
            # Initialize motors with gpiozero
            # Motor(forward_pin, backward_pin)
            self.left_motor = Motor(left_forward_pin, left_backward_pin)
            self.right_motor = Motor(right_forward_pin, right_backward_pin)
            
            self.hardware_available = True
            logger.info(f"✓ Motor controller initialized (gpiozero)")
            logger.debug(f"  Left: pins {left_forward_pin}/{left_backward_pin}")
            logger.debug(f"  Right: pins {right_forward_pin}/{right_backward_pin}")
        except ImportError:
            logger.warning("gpiozero not available - running in simulation mode")
        except Exception as e:
            logger.warning(f"Motor initialization error: {e} - running in simulation mode")

    def forward(self, speed: int = 150):
        """
        Move forward at given speed (0-255).
        
        Args:
            speed: Speed from 0-255
        """
        self.left_speed = speed
        self.right_speed = speed
        
        if self.hardware_available and self.left_motor and self.right_motor:
            # gpiozero Motor.forward() takes value 0.0-1.0
            duty = speed / 255.0
            self.left_motor.forward(duty)
            self.right_motor.forward(duty)
        
        logger.info(f"Motor: Forward (speed={speed})")

    def backward(self, speed: int = 150):
        """
        Move backward at given speed (0-255).
        
        Args:
            speed: Speed from 0-255
        """
        self.left_speed = -speed
        self.right_speed = -speed
        
        if self.hardware_available and self.left_motor and self.right_motor:
            # gpiozero Motor.backward() takes value 0.0-1.0
            duty = speed / 255.0
            self.left_motor.backward(duty)
            self.right_motor.backward(duty)
        
        logger.info(f"Motor: Backward (speed={speed})")

    def spin_left(self, speed: int = 150):
        """
        Spin left (left backward, right forward).
        
        Args:
            speed: Speed from 0-255
        """
        self.left_speed = -speed
        self.right_speed = speed
        
        if self.hardware_available and self.left_motor and self.right_motor:
            duty = speed / 255.0
            self.left_motor.backward(duty)
            self.right_motor.forward(duty)
        
        logger.info(f"Motor: Spin left (speed={speed})")

    def spin_right(self, speed: int = 150):
        """
        Spin right (left forward, right backward).
        
        Args:
            speed: Speed from 0-255
        """
        self.left_speed = speed
        self.right_speed = -speed
        
        if self.hardware_available and self.left_motor and self.right_motor:
            duty = speed / 255.0
            self.left_motor.forward(duty)
            self.right_motor.backward(duty)
        
        logger.info(f"Motor: Spin right (speed={speed})")

    def stop(self):
        """Stop all motors immediately."""
        self.left_speed = 0
        self.right_speed = 0
        
        if self.hardware_available and self.left_motor and self.right_motor:
            self.left_motor.stop()
            self.right_motor.stop()
        
        logger.info("Motor: Stop")

    def cleanup(self):
        """Cleanup motor resources."""
        self.stop()
        if self.hardware_available:
            try:
                if self.left_motor:
                    self.left_motor.close()
                if self.right_motor:
                    self.right_motor.close()
                logger.info("Motor controller cleaned up")
            except Exception as e:
                logger.warning(f"Error during motor cleanup: {e}")


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
        )
        _motor_controller = MotorController(
            MOTOR_LEFT_FORWARD,
            MOTOR_LEFT_BACKWARD,
            MOTOR_RIGHT_FORWARD,
            MOTOR_RIGHT_BACKWARD,
        )
    return _motor_controller
