"""
Servo Hardware Abstraction
==========================
Controls servo motors (pan/tilt or other motion).
Supports multiple servo control backends based on Pi version and PCB version.
"""

import logging
import subprocess
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _get_raspberry_pi_version() -> int:
    """
    Detect Raspberry Pi version.
    Returns: 1 for Pi < 5, 2 for Pi 5
    """
    try:
        result = subprocess.run(['cat', '/sys/firmware/devicetree/base/model'], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            model = result.stdout.strip()
            if "Raspberry Pi 5" in model:
                logger.debug(f"Detected: {model} (Pi version 2)")
                return 2
            else:
                logger.debug(f"Detected: {model} (Pi version 1)")
                return 1
    except Exception as e:
        logger.debug(f"Pi version detection failed: {e}, assuming Pi version 1")
    return 1


class ServoBackend:
    """Base class for servo control backends."""
    
    def set_servo_angle(self, channel: int, angle: int):
        """Set servo angle (0-180 degrees)."""
        raise NotImplementedError
    
    def cleanup(self):
        """Cleanup resources."""
        pass


class GpiozeroServoBackend(ServoBackend):
    """
    Servo control using gpiozero library (AngularServo).
    Works on older Raspberry Pi versions.
    """
    
    def __init__(self, ch0_pin: int = 7, ch1_pin: int = 8, ch2_pin: int = 25):
        """Initialize gpiozero servo control."""
        try:
            from gpiozero import AngularServo
            self.AngularServo = AngularServo
            
            # Create servo objects with proper pulse width settings
            # Standard servo pulse widths: 0.5ms (0°) to 2.5ms (180°)
            self.servo0 = AngularServo(ch0_pin, initial_angle=90, min_angle=0, max_angle=180,
                                      min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)
            self.servo1 = AngularServo(ch1_pin, initial_angle=90, min_angle=0, max_angle=180,
                                      min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)
            self.servo2 = AngularServo(ch2_pin, initial_angle=90, min_angle=0, max_angle=180,
                                      min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)
            
            self.servos = {0: self.servo0, 1: self.servo1, 2: self.servo2}
            self.hardware_available = True
            logger.info("✓ Servo backend: gpiozero (AngularServo)")
        except ImportError as e:
            logger.error(f"gpiozero not available: {e}")
            self.hardware_available = False
        except Exception as e:
            logger.error(f"Servo initialization error: {e}")
            self.hardware_available = False
    
    def set_servo_angle(self, channel: int, angle: int):
        """Set servo angle using gpiozero."""
        if not self.hardware_available:
            return
        
        try:
            if channel in self.servos:
                self.servos[channel].angle = angle
                logger.debug(f"Servo {channel}: angle={angle}°")
        except Exception as e:
            logger.error(f"Error setting servo {channel} angle: {e}")
    
    def cleanup(self):
        """Cleanup servo objects."""
        try:
            for servo in self.servos.values():
                if hasattr(servo, 'close'):
                    servo.close()
        except Exception as e:
            logger.warning(f"Error during servo cleanup: {e}")


class HardwareServoBackend(ServoBackend):
    """
    Servo control using RPi.GPIO hardware PWM.
    Works on both older and Raspberry Pi 5.
    """
    
    def __init__(self, ch0_pin: int = 7, ch1_pin: int = 8, ch2_pin: int = 25):
        """Initialize hardware PWM servo control."""
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            self.ch0_pin = ch0_pin
            self.ch1_pin = ch1_pin
            self.ch2_pin = ch2_pin
            
            # Setup pins as output
            for pin in [ch0_pin, ch1_pin, ch2_pin]:
                GPIO.setup(pin, GPIO.OUT)
            
            # Create PWM objects at 50 Hz (standard servo frequency)
            self.pwm0 = GPIO.PWM(ch0_pin, 50)
            self.pwm1 = GPIO.PWM(ch1_pin, 50)
            self.pwm2 = GPIO.PWM(ch2_pin, 50)
            
            self.pwm0.start(0)
            self.pwm1.start(0)
            self.pwm2.start(0)
            
            self.pwms = {0: self.pwm0, 1: self.pwm1, 2: self.pwm2}
            self.hardware_available = True
            logger.info("✓ Servo backend: hardware PWM (RPi.GPIO)")
        except ImportError as e:
            logger.error(f"RPi.GPIO not available: {e}")
            self.hardware_available = False
        except Exception as e:
            logger.error(f"Servo initialization error: {e}")
            self.hardware_available = False
    
    def _angle_to_duty_cycle(self, angle: int) -> float:
        """
        Convert servo angle (0-180°) to PWM duty cycle (2.5-12.5%).
        
        For a standard servo:
        - 0° = 0.5ms pulse (2.5% at 50Hz, 20ms period)
        - 90° = 1.5ms pulse (7.5% at 50Hz)
        - 180° = 2.5ms pulse (12.5% at 50Hz)
        """
        min_duty = 2.5
        max_duty = 12.5
        duty = min_duty + (max_duty - min_duty) * (angle / 180.0)
        return duty
    
    def set_servo_angle(self, channel: int, angle: int):
        """Set servo angle using hardware PWM."""
        if not self.hardware_available:
            return
        
        try:
            if channel in self.pwms:
                duty_cycle = self._angle_to_duty_cycle(angle)
                self.pwms[channel].ChangeDutyCycle(duty_cycle)
                logger.debug(f"Servo {channel}: angle={angle}° (duty={duty_cycle:.1f}%)")
        except Exception as e:
            logger.error(f"Error setting servo {channel} angle: {e}")
    
    def cleanup(self):
        """Cleanup PWM and GPIO."""
        try:
            for pwm in self.pwms.values():
                if hasattr(pwm, 'stop'):
                    pwm.stop()
            if self.hardware_available:
                self.GPIO.cleanup()
        except Exception as e:
            logger.warning(f"Error during servo cleanup: {e}")


class ServoController:
    """
    High-level servo control abstraction.
    Automatically selects appropriate backend based on hardware.
    """
    
    def __init__(self, ch0_pin: int = 7, ch1_pin: int = 8, ch2_pin: int = 25,
                 pcb_version: int = 2, 
                 ch0_min: int = 0, ch0_max: int = 180,
                 ch1_min: int = 0, ch1_max: int = 180,
                 ch2_min: int = 0, ch2_max: int = 180):
        """
        Initialize servo controller.
        
        Args:
            ch0_pin, ch1_pin, ch2_pin: GPIO pins for servo channels
            pcb_version: PCB version (1 or 2)
            ch*_min, ch*_max: Angle limits for each channel
        """
        self.ch0_pin = ch0_pin
        self.ch1_pin = ch1_pin
        self.ch2_pin = ch2_pin
        self.pcb_version = pcb_version
        
        # Channel angle limits
        self.angle_limits = {
            0: (ch0_min, ch0_max),
            1: (ch1_min, ch1_max),
            2: (ch2_min, ch2_max),
        }
        
        self.current_angles = {0: 90, 1: 90, 2: 90}
        self.backend = None
        self.hardware_available = False
        
        self._init_backend()
    
    def _init_backend(self):
        """Initialize appropriate servo backend."""
        try:
            pi_version = _get_raspberry_pi_version()
            logger.debug(f"Initializing servo backend: Pi_v{pi_version}, PCB_v{self.pcb_version}")
            
            # Try hardware PWM first (more reliable)
            try:
                self.backend = HardwareServoBackend(self.ch0_pin, self.ch1_pin, self.ch2_pin)
                if self.backend.hardware_available:
                    self.hardware_available = True
                    return
            except Exception as e:
                logger.debug(f"Hardware PWM backend failed: {e}")
            
            # Fall back to gpiozero
            try:
                self.backend = GpiozeroServoBackend(self.ch0_pin, self.ch1_pin, self.ch2_pin)
                if self.backend.hardware_available:
                    self.hardware_available = True
                    return
            except Exception as e:
                logger.debug(f"gpiozero backend failed: {e}")
            
            # If we get here, no hardware available
            logger.warning("No servo hardware backend available - simulation mode")
            self.backend = ServoBackend()
            
        except Exception as e:
            logger.error(f"Servo backend initialization error: {e}")
            self.backend = ServoBackend()
    
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
            
            if self.backend and self.hardware_available:
                self.backend.set_servo_angle(channel, clamped_angle)
            else:
                logger.debug(f"Servo {channel} set angle {clamped_angle}° (simulation)")
    
    def center_servo(self, channel: int):
        """Center servo at 90 degrees."""
        self.set_servo_angle(channel, 90)
    
    def sweep_servo(self, channel: int, start_angle: int = None, end_angle: int = None, 
                    step: int = 1, delay: float = 0.05):
        """
        Sweep servo through full range (for testing).
        
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
        if self.backend:
            try:
                self.backend.cleanup()
            except Exception as e:
                logger.warning(f"Error during servo cleanup: {e}")
        
        # Center all servos before shutdown
        for channel in [0, 1, 2]:
            self.center_servo(channel)


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
            SERVO_PCB_VERSION,
        )
        _servo_controller = ServoController(
            ch0_pin=SERVO_CHANNEL_0,
            ch1_pin=SERVO_CHANNEL_1,
            ch2_pin=SERVO_CHANNEL_2,
            pcb_version=SERVO_PCB_VERSION,
            ch0_min=SERVO_CH0_MIN,
            ch0_max=SERVO_CH0_MAX,
            ch1_min=SERVO_CH1_MIN,
            ch1_max=SERVO_CH1_MAX,
            ch2_min=SERVO_CH2_MIN,
            ch2_max=SERVO_CH2_MAX,
        )
    return _servo_controller
