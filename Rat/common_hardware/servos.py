"""
Servo Controller - Unified interface for servo control
Supports:
  - PigpioServo: Basic pigpio backend
  - GpiozeroServo: gpiozero backend (fallback)
  - HardwareServo: rpi_hardware_pwm backend (PCB v2)
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
    """Servo control using pigpio"""
    
    def __init__(self):
        try:
            import pigpio
            logger.info("Initializing PigpioServo backend...")
            
            self.channel1 = SERVO_CHANNEL_0
            self.channel2 = SERVO_CHANNEL_1
            self.channel3 = SERVO_CHANNEL_2
            self.PwmServo = pigpio.pi()
            
            self.PwmServo.set_mode(self.channel1, pigpio.OUTPUT)
            self.PwmServo.set_mode(self.channel2, pigpio.OUTPUT)
            self.PwmServo.set_mode(self.channel3, pigpio.OUTPUT)
            
            self.PwmServo.set_PWM_frequency(self.channel1, 50)
            self.PwmServo.set_PWM_frequency(self.channel2, 50)
            self.PwmServo.set_PWM_frequency(self.channel3, 50)
            
            self.PwmServo.set_PWM_range(self.channel1, 4000)
            self.PwmServo.set_PWM_range(self.channel2, 4000)
            self.PwmServo.set_PWM_range(self.channel3, 4000)
            
            logger.info("✓ PigpioServo backend initialized")
            self.available = True
        except Exception as e:
            logger.error(f"PigpioServo init failed: {e}")
            self.available = False
    
    def setServoPwm(self, channel, angle):
        """Set servo angle using pigpio PWM duty cycle"""
        if not self.available:
            return
        
        try:
            if channel == '0':
                duty = int(80 + (400.0 / 180.0) * angle)
                self.PwmServo.set_PWM_dutycycle(self.channel1, duty)
            elif channel == '1':
                duty = int(80 + (400.0 / 180.0) * angle)
                self.PwmServo.set_PWM_dutycycle(self.channel2, duty)
            elif channel == '2':
                duty = int(80 + (400.0 / 180.0) * angle)
                self.PwmServo.set_PWM_dutycycle(self.channel3, duty)
            logger.debug(f"Pigpio servo ch{channel}: {angle}°")
        except Exception as e:
            logger.error(f"Failed to set servo {channel}: {e}")


class GpiozeroServo:
    """Servo control using gpiozero"""
    
    def __init__(self):
        try:
            from gpiozero import AngularServo
            logger.info("Initializing GpiozeroServo backend...")
            
            self.channel1 = SERVO_CHANNEL_0
            self.channel2 = SERVO_CHANNEL_1
            self.channel3 = SERVO_CHANNEL_2
            self.myCorrection = 0.0
            self.maxPW = (2.5 + self.myCorrection) / 1000
            self.minPW = (0.5 - self.myCorrection) / 1000
            
            self.servo1 = AngularServo(
                self.channel1,
                initial_angle=0,
                min_angle=0,
                max_angle=180,
                min_pulse_width=self.minPW,
                max_pulse_width=self.maxPW
            )
            self.servo2 = AngularServo(
                self.channel2,
                initial_angle=0,
                min_angle=0,
                max_angle=180,
                min_pulse_width=self.minPW,
                max_pulse_width=self.maxPW
            )
            self.servo3 = AngularServo(
                self.channel3,
                initial_angle=0,
                min_angle=0,
                max_angle=180,
                min_pulse_width=self.minPW,
                max_pulse_width=self.maxPW
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
        
        try:
            if channel == '0':
                self.servo1.angle = angle
            elif channel == '1':
                self.servo2.angle = angle
            elif channel == '2':
                self.servo3.angle = angle
            logger.debug(f"Gpiozero servo ch{channel}: {angle}°")
        except Exception as e:
            logger.error(f"Failed to set servo {channel}: {e}")


class HardwareServo:
    """Servo control using rpi_hardware_pwm (PCB v2)"""
    
    def __init__(self, pcb_version):
        try:
            from rpi_hardware_pwm import HardwarePWM
            logger.info("Initializing HardwareServo backend...")
            
            self.pcb_version = pcb_version
            self.pwm_gpio12 = None
            self.pwm_gpio13 = None
            
            if self.pcb_version == 1:
                self.pwm_gpio12 = HardwarePWM(pwm_channel=0, hz=50, chip=0)
                self.pwm_gpio13 = HardwarePWM(pwm_channel=1, hz=50, chip=0)
            elif self.pcb_version == 2:
                self.pwm_gpio12 = HardwarePWM(pwm_channel=0, hz=50, chip=0)
                self.pwm_gpio13 = HardwarePWM(pwm_channel=1, hz=50, chip=0)
            
            self.pwm_gpio12.start(0)
            self.pwm_gpio13.start(0)
            
            logger.info("✓ HardwareServo backend initialized")
            self.available = True
        except Exception as e:
            logger.error(f"HardwareServo init failed: {e}")
            self.available = False
    
    def setServoStop(self, channel):
        """Stop the PWM for the specified channel"""
        if not self.available:
            return
        
        try:
            if channel == '0':
                self.pwm_gpio12.stop()
            elif channel == '1':
                self.pwm_gpio13.stop()
        except Exception as e:
            logger.error(f"Failed to stop servo {channel}: {e}")
    
    def setServoFrequency(self, channel, freq):
        """Set the PWM frequency for the specified channel"""
        if not self.available:
            return
        
        try:
            if channel == '0':
                self.pwm_gpio12.change_frequency(freq)
            elif channel == '1':
                self.pwm_gpio13.change_frequency(freq)
        except Exception as e:
            logger.error(f"Failed to set frequency for servo {channel}: {e}")
    
    def setServoDuty(self, channel, duty):
        """Set the PWM duty cycle for the specified channel"""
        if not self.available:
            return
        
        try:
            if channel == '0':
                self.pwm_gpio12.change_duty_cycle(duty)
            elif channel == '1':
                self.pwm_gpio13.change_duty_cycle(duty)
        except Exception as e:
            logger.error(f"Failed to set duty cycle for servo {channel}: {e}")
    
    def map(self, x, in_min, in_max, out_min, out_max):
        """Map a value from one range to another"""
        return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    
    def setServoPwm(self, channel, angle):
        """Set the PWM duty cycle for the specified channel and angle"""
        if not self.available:
            return
        
        try:
            if channel == '0':
                duty = self.map(angle, 0, 180, 2.5, 12.5)
                self.setServoDuty(channel, duty)
            elif channel == '1':
                duty = self.map(angle, 0, 180, 2.5, 12.5)
                self.setServoDuty(channel, duty)
            logger.debug(f"Hardware servo ch{channel}: {angle}°")
        except Exception as e:
            logger.error(f"Failed to set servo {channel}: {e}")


class Servo:
    """
    Unified servo controller - matches Code/Server reference implementation.
    Selects backend based on PCB version and Raspberry Pi version.
    """
    
    def __init__(self):
        """Initialize servo controller based on PCB version"""
        try:
            from parameter import ParameterManager
            self.param = ParameterManager()
            self.pcb_version = self.param.get_pcb_version()
            self.pi_version = self.param.get_raspberry_pi_version()
            logger.info(f"PCB version: {self.pcb_version}, Pi version: {self.pi_version}")
        except Exception as e:
            logger.warning(f"Could not read parameters: {e}, using defaults")
            self.pcb_version = SERVO_PCB_VERSION
            self.pi_version = 2
        
        # Select backend based on PCB and Pi version
        if self.pcb_version == 1 and self.pi_version == 1:
            logger.info("Using GpiozeroServo (PCB v1, Pi v1)")
            self.pwm = GpiozeroServo()
        elif self.pcb_version == 1 and self.pi_version == 2:
            logger.info("Using GpiozeroServo (PCB v1, Pi v2)")
            self.pwm = GpiozeroServo()
        elif self.pcb_version == 2 and self.pi_version == 1:
            logger.info("Using HardwareServo (PCB v2, Pi v1)")
            self.pwm = HardwareServo(1)
            # Fallback to gpiozero if HardwareServo unavailable
            if not self.pwm.available:
                logger.warning("HardwareServo unavailable, falling back to GpiozeroServo")
                self.pwm = GpiozeroServo()
        elif self.pcb_version == 2 and self.pi_version == 2:
            logger.info("Using HardwareServo (PCB v2, Pi v2)")
            self.pwm = HardwareServo(2)
            # Fallback to gpiozero if HardwareServo unavailable
            if not self.pwm.available:
                logger.warning("HardwareServo unavailable, falling back to GpiozeroServo")
                self.pwm = GpiozeroServo()
        else:
            logger.warning(f"Unknown config (PCB{self.pcb_version}, Pi{self.pi_version}), using GpiozeroServo")
            self.pwm = GpiozeroServo()
        
        # Set initial positions
        self.pwm.setServoPwm("0", 90)
        self.pwm.setServoPwm("1", 140)
    
    def angle_range(self, channel, init_angle):
        """Ensure the angle is within the valid range for the specified channel"""
        try:
            if str(channel) == '0':
                if init_angle < SERVO_CH0_MIN:
                    init_angle = SERVO_CH0_MIN
                elif init_angle > SERVO_CH0_MAX:
                    init_angle = SERVO_CH0_MAX
            elif str(channel) == '1':
                if init_angle < SERVO_CH1_MIN:
                    init_angle = SERVO_CH1_MIN
                elif init_angle > SERVO_CH1_MAX:
                    init_angle = SERVO_CH1_MAX
            elif str(channel) == '2':
                if init_angle < SERVO_CH2_MIN:
                    init_angle = SERVO_CH2_MIN
                elif init_angle > SERVO_CH2_MAX:
                    init_angle = SERVO_CH2_MAX
        except Exception as e:
            logger.error(f"Error in angle_range: {e}")
        
        return init_angle
    
    
    def setServoAngle(self, channel, angle):
        """Set the angle for the specified channel"""
        try:
            angle = self.angle_range(str(channel), int(angle))
            self.pwm.setServoPwm(str(channel), int(angle))
            logger.debug(f"setServoAngle: ch{channel} → {angle}°")
        except Exception as e:
            logger.error(f"Failed to set servo angle: {e}")
    
    def setServoStop(self):
        """Stop the PWM for all servos"""
        if self.pcb_version == 2 and hasattr(self.pwm, 'setServoStop'):
            try:
                self.pwm.setServoStop('0')
                self.pwm.setServoStop('1')
                logger.info("Servos stopped")
            except Exception as e:
                logger.error(f"Failed to stop servos: {e}")


# Main program logic
if __name__ == '__main__':
    import time
    servo = Servo()
    
    print("Now servo 0 will be rotated to 150° and servo 1 will be rotated to 90°.")
    print("If they were already at 150° and 90°, nothing would be observed.")
    print("Please keep the program running when installing the servos.")
    print("After that, you can press ctrl-C to end the program.")
    
    try:
        while True:
            servo.setServoAngle('0', 150)
            servo.setServoAngle('1', 90)
            time.sleep(1)
    except KeyboardInterrupt:
        # Gradually decrease the angle of servo 0 from 150° to 90°
        for i in range(150, 90, -1):
            servo.setServoAngle('0', i)
            time.sleep(0.01)
        
        # Gradually increase the angle of servo 1 from 90° to 140°
        for i in range(90, 140, 1):
            servo.setServoAngle('1', i)
            time.sleep(0.01)
        
        servo.setServoStop()
        print("\nEnd of program")
