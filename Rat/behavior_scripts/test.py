"""
Hardware Testing Behavior
Tests LED, Motor, and Servo through brain interface.
"""

import logging
import time

logger = logging.getLogger(__name__)


class Behavior:
    """Hardware test behavior - runs tests and returns to IDLE."""
    
    def __init__(self):
        """Initialize test behavior."""
        self.phase = 0  # 0=LED, 1=SERVO, 2=MOTOR
        self.step = 0
        self.phase_start = time.time()
        logger.info("Test behavior initialized")
    
    def run(self, brain) -> bool:
        """
        Run one iteration of hardware tests.
        
        Args:
            brain: RatBrain instance
        
        Returns:
            True to keep running, False to finish and return to IDLE
        """
        try:
            if self.phase == 0:
                # LED TEST PHASE
                if self._test_led_phase(brain):
                    return True  # Keep running
                else:
                    # Move to servo phase
                    self.phase = 1
                    self.step = 0
                    self.phase_start = time.time()
                    return True
            
            elif self.phase == 1:
                # SERVO TEST PHASE
                if self._test_servo_phase(brain):
                    return True  # Keep running
                else:
                    # Move to motor phase
                    self.phase = 2
                    self.step = 0
                    self.phase_start = time.time()
                    return True
            
            elif self.phase == 2:
                # MOTOR TEST PHASE
                if self._test_motor_phase(brain):
                    return True  # Keep running
                else:
                    # All tests done - return to IDLE
                    logger.info("All tests completed!")
                    brain.led.turn_off()
                    return False
        
        except Exception as e:
            logger.error(f"Test error: {e}")
            brain.motor.stop()
            brain.led.turn_off()
            return False
    
    def _test_led_phase(self, brain) -> bool:
        """
        Test LEDs - show each color for 1 second.
        Returns True if still testing, False when done.
        """
        colors = [
            ((255, 0, 0), "Red"),
            ((0, 255, 0), "Green"),
            ((0, 0, 255), "Blue"),
            ((255, 255, 255), "White"),
            ((255, 255, 0), "Yellow"),
            ((0, 255, 255), "Cyan"),
            ((255, 0, 255), "Magenta"),
        ]
        
        elapsed = time.time() - self.phase_start
        color_idx = int(elapsed)  # Every 1 second, next color
        
        if color_idx < len(colors):
            color, name = colors[color_idx]
            brain.led.set_color(color)
            logger.info(f"LED: {name}")
            return True
        else:
            logger.info("LED phase complete")
            return False
    
    def _test_servo_phase(self, brain) -> bool:
        """
        Test Servos - sweep movements.
        4 movements, each ~0.6 seconds.
        """
        movements = [
            (0, 90, 150, 1),    # Servo 0: 90°→150°
            (0, 150, 90, -1),   # Servo 0: 150°→90°
            (1, 90, 140, 1),    # Servo 1: 90°→140°
            (1, 140, 90, -1),   # Servo 1: 140°→90°
        ]
        
        if self.step >= len(movements):
            logger.info("Servo phase complete")
            return False
        
        channel, start, end, direction = movements[self.step]
        elapsed = time.time() - self.phase_start
        
        # Each sweep takes ~0.6 seconds (60 steps * 0.01s)
        # Do one full sweep per this run() call
        if elapsed < 0.7:  # 0.6s sweep + 0.1s margin
            # Perform smooth sweep
            if direction > 0:
                for angle in range(start, end + 1):
                    brain.servo.setServoAngle(str(channel), angle)
                    time.sleep(0.01)
            else:
                for angle in range(start, end - 1, -1):
                    brain.servo.setServoAngle(str(channel), angle)
                    time.sleep(0.01)
            
            logger.info(f"Servo {channel} sweep: {start}→{end}")
            self.step += 1
            self.phase_start = time.time()
            return True
        else:
            return True
    
    def _test_motor_phase(self, brain) -> bool:
        """
        Test Motors - movement sequences.
        """
        movements = [
            ("Forward", lambda: brain.motor.setMotorModel(2000, 2000), 2.0),
            ("Backward", lambda: brain.motor.setMotorModel(-2000, -2000), 2.0),
            ("Spin Left", lambda: brain.motor.setMotorModel(-2000, 2000), 2.0),
            ("Spin Right", lambda: brain.motor.setMotorModel(2000, -2000), 2.0),
            ("Diagonal FL", lambda: brain.motor.setMotorModel(1000, 2000), 1.5),
            ("Diagonal FR", lambda: brain.motor.setMotorModel(2000, 1000), 1.5),
            ("Stop", lambda: brain.motor.setMotorModel(0, 0), 0.5),
        ]
        
        if self.step >= len(movements):
            logger.info("Motor phase complete")
            return False
        
        name, func, duration = movements[self.step]
        elapsed = time.time() - self.phase_start
        
        if elapsed < duration:
            func()
            logger.info(f"Motor: {name}")
            return True
        else:
            self.step += 1
            self.phase_start = time.time()
            return True
