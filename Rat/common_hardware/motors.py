"""
Motor Hardware Abstraction
==========================
Controls tank robot movement (2 motors, left and right).
Wraps reference implementation from Code/Server/motor.py
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MotorController:
    """
    Abstraction for tank motor control using gpiozero.Motor.
    Tank has two independent motors (left and right).
    
    API compatible with Code/Server/motor.py tankMotor class:
    - setMotorModel(duty1, duty2): Set motor speeds with duty cycles
    - left_Wheel(duty), right_Wheel(duty): Individual motor control
    - close(): Cleanup resources
    """

    def __init__(
        self,
        left_forward_pin: int = 24,
        left_backward_pin: int = 23,
        right_forward_pin: int = 5,
        right_backward_pin: int = 6,
    ):
        """
        Initialize motor controller using gpiozero.Motor.
        
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

        # Try to initialize motors with gpiozero
        try:
            from gpiozero import Motor
            
            # Initialize motors: Motor(forward_pin, backward_pin)
            self.left_motor = Motor(left_forward_pin, left_backward_pin)
            self.right_motor = Motor(right_forward_pin, right_backward_pin)
            
            self.hardware_available = True
            logger.info(f"✓ Motor controller initialized")
        except ImportError:
            logger.warning("gpiozero not available - running in simulation mode")
        except Exception as e:
            logger.warning(f"Motor initialization error: {e} - running in simulation mode")

    def duty_range(self, duty1: int, duty2: int) -> tuple:
        """Ensure duty cycle values are within valid range (-4095 to 4095)."""
        duty1 = max(-4095, min(4095, duty1))
        duty2 = max(-4095, min(4095, duty2))
        return duty1, duty2

    def left_Wheel(self, duty: int):
        """
        Control left wheel based on duty cycle value.
        
        Args:
            duty: -4095 to 4095 (negative = backward, positive = forward)
        """
        if not self.hardware_available or not self.left_motor:
            logger.debug(f"Left motor: duty={duty} (simulation)")
            return
        
        duty = max(-4095, min(4095, duty))
        value = abs(duty) / 4096.0
        
        if duty > 0:
            self.left_motor.forward(value)
        elif duty < 0:
            self.left_motor.backward(value)
        else:
            self.left_motor.stop()
        
        logger.debug(f"Left motor: duty={duty}, value={value:.3f}")

    def right_Wheel(self, duty: int):
        """
        Control right wheel based on duty cycle value.
        
        Args:
            duty: -4095 to 4095 (negative = backward, positive = forward)
        """
        if not self.hardware_available or not self.right_motor:
            logger.debug(f"Right motor: duty={duty} (simulation)")
            return
        
        duty = max(-4095, min(4095, duty))
        value = abs(duty) / 4096.0
        
        if duty > 0:
            self.right_motor.forward(value)
        elif duty < 0:
            self.right_motor.backward(value)
        else:
            self.right_motor.stop()
        
        logger.debug(f"Right motor: duty={duty}, value={value:.3f}")

    def setMotorModel(self, duty1: int, duty2: int):
        """
        Set duty cycle for both motors (reference API).
        
        Args:
            duty1: Left motor duty cycle (-4095 to 4095)
            duty2: Right motor duty cycle (-4095 to 4095)
        """
        duty1, duty2 = self.duty_range(duty1, duty2)
        self.left_Wheel(duty1)
        self.right_Wheel(duty2)

    def forward(self, speed: int = 2000):
        """Move forward at given speed."""
        self.setMotorModel(speed, speed)
        logger.info(f"Motor: Forward (duty={speed})")

    def backward(self, speed: int = 2000):
        """Move backward at given speed."""
        self.setMotorModel(-speed, -speed)
        logger.info(f"Motor: Backward (duty={speed})")

    def spin_left(self, speed: int = 2000):
        """Spin left (left backward, right forward)."""
        self.setMotorModel(-speed, speed)
        logger.info(f"Motor: Spin left (duty={speed})")

    def spin_right(self, speed: int = 2000):
        """Spin right (left forward, right backward)."""
        self.setMotorModel(speed, -speed)
        logger.info(f"Motor: Spin right (duty={speed})")

    def stop(self):
        """Stop all motors immediately."""
        self.setMotorModel(0, 0)
        logger.info("Motor: Stop")

    def close(self):
        """Close motors to release resources."""
        self.stop()
        if self.hardware_available:
            try:
                if self.left_motor:
                    self.left_motor.close()
                if self.right_motor:
                    self.right_motor.close()
                logger.info("Motor controller closed")
            except Exception as e:
                logger.warning(f"Error closing motors: {e}")

    def cleanup(self):
        """Alias for close() for consistency."""
        self.close()


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
