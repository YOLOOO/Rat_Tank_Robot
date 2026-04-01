"""
Servo Hardware Abstraction
==========================
Controls servo motors (pan/tilt or other motion).
Uses gpiozero.AngularServo for reliable control.
"""

import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ServoController:
    """
    High-level servo control abstraction using gpiozero.AngularServo.
    Supports 3 servo channels for pan/tilt and additional motion.
    """
    
    def __init__(self, 
                 ch0_pin: int = 7, 
                 ch1_pin: int = 8, 
                 ch2_pin: int = 25,
                 ch0_min: int = 0, 
                 ch0_max: int = 180,
                 ch1_min: int = 0, 
                 ch1_max: int = 180,
                 ch2_min: int = 0, 
                 ch2_max: int = 180):
        """
        Initialize servo controller using gpiozero.AngularServo.
        
        Args:
            ch0_pin, ch1_pin, ch2_pin: GPIO pins for servo channels
            ch*_min, ch*_max: Angle limits for each channel
        """
        self.ch0_pin = ch0_pin
        self.ch1_pin = ch1_pin
        self.ch2_pin = ch2_pin
        
        # Channel angle limits
        self.angle_limits = {
            0: (ch0_min, ch0_max),
            1: (ch1_min, ch1_max),
            2: (ch2_min, ch2_max),
        }
        
        self.current_angles = {0: 90, 1: 90, 2: 90}
        self.servos = {}
        self.hardware_available = False
        
        self._init_servos()
    
    def _init_servos(self):
        """Initialize servo objects using gpiozero.AngularServo."""
        try:
            from gpiozero import AngularServo
            
            # Standard servo pulse widths: 0.5ms (0°) to 2.5ms (180°)
            min_pw = 0.5 / 1000  # 0.5ms in seconds
            max_pw = 2.5 / 1000  # 2.5ms in seconds
            
            # Create servo objects
            self.servos[0] = AngularServo(
                self.ch0_pin,
                initial_angle=90,
                min_angle=0,
                max_angle=180,
                min_pulse_width=min_pw,
                max_pulse_width=max_pw
            )
            self.servos[1] = AngularServo(
                self.ch1_pin,
                initial_angle=90,
                min_angle=0,
                max_angle=180,
                min_pulse_width=min_pw,
                max_pulse_width=max_pw
            )
            self.servos[2] = AngularServo(
                self.ch2_pin,
                initial_angle=90,
                min_angle=0,
                max_angle=180,
                min_pulse_width=min_pw,
                max_pulse_width=max_pw
            )
            
            self.hardware_available = True
            logger.info(f"✓ Servo controller initialized (gpiozero.AngularServo)")
            logger.debug(f"  Channel 0 (pin {self.ch0_pin}): 0-180°")
            logger.debug(f"  Channel 1 (pin {self.ch1_pin}): 0-180°")
            logger.debug(f"  Channel 2 (pin {self.ch2_pin}): 0-180°")
            
        except ImportError:
            logger.warning("gpiozero not available - running in simulation mode")
        except Exception as e:
            logger.warning(f"Servo initialization error: {e} - running in simulation mode")
    
    def _clamp_angle(self, channel: int, angle: int) -> int:
        """Clamp angle to channel's valid range."""
        min_angle, max_angle = self.angle_limits.get(channel, (0, 180))
        return max(min_angle, min(max_angle, angle))
    
    def set_servo_angle(self, channel: int, angle: int):
        """
        Set servo to angle (0-180 degrees).
        
        Args:
            channel: Servo channel (0, 1, or 2)
            angle: Target angle in degrees (0-180)
        """
        if channel not in [0, 1, 2]:
            logger.warning(f"Invalid servo channel: {channel}")
            return
        
        # Clamp to valid range
        clamped_angle = self._clamp_angle(channel, angle)
        
        # Only send if angle changed
        if self.current_angles[channel] != clamped_angle:
            self.current_angles[channel] = clamped_angle
            
            if self.hardware_available and channel in self.servos:
                try:
                    self.servos[channel].angle = clamped_angle
                    logger.debug(f"Servo {channel}: set angle to {clamped_angle}°")
                except Exception as e:
                    logger.error(f"Error setting servo {channel} angle: {e}")
            else:
                logger.debug(f"Servo {channel}: set angle to {clamped_angle}° (simulation)")
    
    def center_servo(self, channel: int):
        """Center servo at 90 degrees."""
        self.set_servo_angle(channel, 90)
    
    def sweep_servo(self, channel: int, start_angle: int = None, end_angle: int = None, 
                    step: int = 1, delay: float = 0.05):
        """
        Sweep servo through range (for testing).
        
        Args:
            channel: Servo channel
            start_angle: Starting angle (default: min for channel)
            end_angle: Ending angle (default: max for channel)
            step: Angle increment per step
            delay: Delay between steps in seconds
        """
        min_angle, max_angle = self.angle_limits[channel]
        
        if start_angle is None:
            start_angle = min_angle
        if end_angle is None:
            end_angle = max_angle
        
        # Forward sweep
        current = start_angle
        while current <= end_angle:
            self.set_servo_angle(channel, current)
            time.sleep(delay)
            current += step
        
        # Backward sweep
        current = end_angle
        while current >= start_angle:
            self.set_servo_angle(channel, current)
            time.sleep(delay)
            current -= step
    
    def cleanup(self):
        """Cleanup servo resources."""
        try:
            for channel in [0, 1, 2]:
                if channel in self.servos:
                    try:
                        self.center_servo(channel)
                        self.servos[channel].close()
                    except Exception as e:
                        logger.debug(f"Error closing servo {channel}: {e}")
            logger.info("Servo controller cleaned up")
        except Exception as e:
            logger.warning(f"Error during servo cleanup: {e}")


# Singleton instance
_servo_controller = None


def get_servo_controller() -> ServoController:
    """Get or create the servo controller singleton."""
    global _servo_controller
    if _servo_controller is None:
        from config import (
            SERVO_CHANNEL_0,
            SERVO_CHANNEL_1,
            SERVO_CHANNEL_2,
            SERVO_CH0_MIN,
            SERVO_CH0_MAX,
            SERVO_CH1_MIN,
            SERVO_CH1_MAX,
            SERVO_CH2_MIN,
            SERVO_CH2_MAX,
        )
        _servo_controller = ServoController(
            ch0_pin=SERVO_CHANNEL_0,
            ch1_pin=SERVO_CHANNEL_1,
            ch2_pin=SERVO_CHANNEL_2,
            ch0_min=SERVO_CH0_MIN,
            ch0_max=SERVO_CH0_MAX,
            ch1_min=SERVO_CH1_MIN,
            ch1_max=SERVO_CH1_MAX,
            ch2_min=SERVO_CH2_MIN,
            ch2_max=SERVO_CH2_MAX,
        )
    return _servo_controller
