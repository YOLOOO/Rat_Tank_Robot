"""
Servo Controller - Unified interface for servo control
Supports:
  - pigpio backend for Pi 5 + PCB v2 (hardware PWM via software)
  - gpiozero backend fallback for other configurations
"""

import logging
import time
from config import (
    SERVO_CHANNEL_0, SERVO_CHANNEL_1, SERVO_CHANNEL_2,
    SERVO_CH0_MIN, SERVO_CH0_MAX,
    SERVO_CH1_MIN, SERVO_CH1_MAX,
    SERVO_CH2_MIN, SERVO_CH2_MAX,
    SERVO_PCB_VERSION
)

logger = logging.getLogger(__name__)


class PigpioServo:
    """Servo control using pigpio (Pi 5 + PCB v2)"""
    
    def __init__(self):
        try:
            import pigpio
            logger.info("Attempting pigpio connection...")
            
            self.pi = pigpio.pi()
            
            # Verify pigpiod daemon is running
            if not self.pi.connected:
                logger.error("pigpiod daemon not connected! Run: sudo pigpiod")
                self.available = False
                return
            
            logger.info("✓ pigpiod daemon connected")
            
            # Map channels to pins
            self.channel_pins = {
                '0': SERVO_CHANNEL_0,
                0: SERVO_CHANNEL_0,
                '1': SERVO_CHANNEL_1,
                1: SERVO_CHANNEL_1,
                '2': SERVO_CHANNEL_2,
                2: SERVO_CHANNEL_2,
            }
            
            # Configure each GPIO pin for PWM
            for ch, pin in [('0', SERVO_CHANNEL_0), ('1', SERVO_CHANNEL_1), ('2', SERVO_CHANNEL_2)]:
                self.pi.set_mode(pin, pigpio.OUTPUT)
                self.pi.set_PWM_frequency(pin, 50)  # 50 Hz for servos
                self.pi.set_PWM_range(pin, 4000)    # 4000 range for finer control
                logger.info(f"  Servo {ch}: GPIO {pin} configured (50Hz, 4000 range)")
            
            self.available = True
            logger.info("✓ PigpioServo backend initialized")
            
        except Exception as e:
            logger.error(f"PigpioServo init failed: {e}")
            self.available = False
    
    def setServoPwm(self, channel, angle):
        """Set servo angle using pigpio PWM duty cycle"""
        if not self.available:
            return
        
        pin = self.channel_pins.get(channel)
        if pin is None:
            logger.warning(f"Invalid channel: {channel}")
            return
        
        # Calculate duty cycle for angle
        # Formula: duty = 80 + (400/180) * angle
        # 0°   → 80 counts   (0.5ms / 20ms = 0.025 = 80/4000)
        # 180° → 480 counts  (2.5ms / 20ms = 0.125 = 480/4000)
        duty = int(80 + (400.0 / 180.0) * angle)
        
        try:
            self.pi.set_PWM_dutycycle(pin, duty)
            logger.debug(f"Pigpio servo ch{channel} (GPIO{pin}): {angle}° → duty {duty}/4000")
        except Exception as e:
            logger.error(f"Failed to set servo {channel}: {e}")


class GpiozeroServo:
    """Servo control using gpiozero (fallback)"""
    
    def __init__(self):
        try:
            from gpiozero import AngularServo
            logger.info("Initializing GpiozeroServo backend...")
            
            self.servos = {}
            
            self.servos[0] = AngularServo(
                SERVO_CHANNEL_0,
                initial_angle=90,
                min_angle=0,
                max_angle=180,
                min_pulse_width=0.5 / 1000,
                max_pulse_width=2.5 / 1000
            )
            
            self.servos[1] = AngularServo(
                SERVO_CHANNEL_1,
                initial_angle=90,
                min_angle=0,
                max_angle=180,
                min_pulse_width=0.5 / 1000,
                max_pulse_width=2.5 / 1000
            )
            
            self.servos[2] = AngularServo(
                SERVO_CHANNEL_2,
                initial_angle=0,
                min_angle=0,
                max_angle=180,
                min_pulse_width=0.5 / 1000,
                max_pulse_width=2.5 / 1000
            )
            
            logger.info("✓ GpiozeroServo backend initialized")
            self.available = True
            
        except Exception as e:
            logger.error(f"GpiozeroServo init failed: {e}")
            self.available = False
    
    def setServoPwm(self, channel, angle):
        """Set servo angle using gpiozero"""
        if not self.available:
            return
        
        ch_num = int(channel) if isinstance(channel, str) else channel
        if ch_num not in self.servos:
            logger.warning(f"Invalid channel: {channel}")
            return
        
        try:
            self.servos[ch_num].angle = angle
            logger.debug(f"Gpiozero servo ch{ch_num}: {angle}°")
        except Exception as e:
            logger.error(f"Failed to set servo {channel}: {e}")


class ServoController:
    """
    Unified servo controller matching Code/Server reference API.
    Automatically selects backend (pigpio for PCB v2, gpiozero fallback).
    """
    
    def __init__(self):
        """Initialize servo controller based on PCB version and hardware availability"""
        self.hardware_available = False
        self.pwm = None
        
        # Try pigpio first (PCB v2 with Pi 5)
        if SERVO_PCB_VERSION == 2:
            logger.info("PCB v2 detected - trying pigpio backend...")
            self.pwm = PigpioServo()
            if self.pwm.available:
                self.hardware_available = True
                logger.info("✓ Using PigpioServo backend for PCB v2")
            else:
                logger.warning("Pigpio not available, falling back to gpiozero...")
        
        # Fallback to gpiozero if pigpio failed or PCB v1
        if not self.hardware_available:
            logger.info("Initializing gpiozero fallback...")
            self.pwm = GpiozeroServo()
            self.hardware_available = self.pwm.available
            if self.hardware_available:
                logger.info("✓ Using GpiozeroServo backend")
        
        # Channel angle limits
        self.angle_limits = {
            '0': (SERVO_CH0_MIN, SERVO_CH0_MAX),
            0: (SERVO_CH0_MIN, SERVO_CH0_MAX),
            '1': (SERVO_CH1_MIN, SERVO_CH1_MAX),
            1: (SERVO_CH1_MIN, SERVO_CH1_MAX),
            '2': (SERVO_CH2_MIN, SERVO_CH2_MAX),
            2: (SERVO_CH2_MIN, SERVO_CH2_MAX),
        }
        
        # Set initial positions
        if self.hardware_available:
            try:
                self.pwm.setServoPwm("0", 90)
                self.pwm.setServoPwm("1", 140)
                logger.info("Servos initialized to default positions")
            except Exception as e:
                logger.warning(f"Failed to set initial positions: {e}")
    
    def angle_range(self, channel, angle):
        """Clamp angle to channel-specific limits"""
        ch_key = channel if isinstance(channel, str) else str(channel)
        min_angle, max_angle = self.angle_limits.get(channel, (0, 180))
        
        clamped = max(min_angle, min(max_angle, angle))
        
        if clamped != angle:
            logger.debug(f"Servo {ch_key}: angle {angle}° clamped to {clamped}° ({min_angle}-{max_angle})")
        
        return clamped
    
    def setServoAngle(self, channel, angle):
        """
        Set servo angle (reference API).
        Accepts channel as string ('0', '1', '2') or int (0, 1, 2).
        """
        ch_str = str(channel)
        clamped = self.angle_range(channel, int(angle))
        
        logger.info(f"setServoAngle: ch{ch_str} → {clamped}°")
        
        if not self.hardware_available:
            logger.debug(f"[SIMULATION] Servo {ch_str} would rotate to {clamped}°")
            return
        
        if self.pwm:
            self.pwm.setServoPwm(ch_str, clamped)
    
    def set_servo_angle(self, channel, angle):
        """Lowercase alias for setServoAngle"""
        self.setServoAngle(channel, angle)
    
    def sweep_servo(self, channel, start_angle=None, end_angle=None, step=5, delay=0.05):
        """
        Sweep servo from start to end angle.
        Defaults to channel min/max if not specified.
        """
        ch_num = int(channel) if isinstance(channel, str) else channel
        min_angle, max_angle = self.angle_limits.get(channel, (0, 180))
        
        start = start_angle if start_angle is not None else min_angle
        end = end_angle if end_angle is not None else max_angle
        
        logger.info(f"Servo {ch_num} sweep: {start}° → {end}° (step={step}, delay={delay}s)")
        
        # Forward sweep
        if start <= end:
            current = start
            while current <= end:
                self.setServoAngle(channel, current)
                time.sleep(delay)
                current += step
        else:
            current = start
            while current >= end:
                self.setServoAngle(channel, current)
                time.sleep(delay)
                current -= step
        
        # Ensure exact final position
        self.setServoAngle(channel, end)
    
    def setServoStop(self):
        """Stop all servos (for reference compatibility)"""
        logger.info("Stopping all servos")
        # Servos don't need explicit stop in software control
    
    def cleanup(self):
        """Cleanup resources"""
        if self.pwm and hasattr(self.pwm, 'pi'):
            try:
                self.pwm.pi.stop()
                logger.info("pigpio connection closed")
            except:
                pass


# Singleton factory pattern
_servo_controller = None


def get_servo_controller() -> ServoController:
    """Get or create the servo controller singleton."""
    global _servo_controller
    if _servo_controller is None:
        _servo_controller = ServoController()
    return _servo_controller
