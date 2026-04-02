"""
Hardware Test Behavior
======================
Comprehensive hardware testing behavior.
Tests LED modes, servo motion, and motor movement through the brain interface.
"""

import time
import logging
from behavior_scripts.base_behavior import BaseBehavior

logger = logging.getLogger(__name__)


class Behavior(BaseBehavior):
    """
    TEST: Hardware Testing Behavior
    ===============================
    Comprehensive hardware testing behavior.
    Can be selected from the menu to run hardware diagnostics.
    Tests LED modes, servo motion, and motor movement through the brain interface.
    """

    name = "TEST"
    color = (255, 165, 0)  # Orange

    def __init__(self):
        """Initialize test behavior with state tracking."""
        super().__init__()
        self.test_phase = 0  # Current test phase
        self.phase_step = 0  # Step within current phase
        self.phase_start_time = time.time()
        
        # Test phases: 0=LED, 1=SERVO, 2=MOTOR
        self.num_phases = 3
        self.current_phase_name = "LED"
        
        logger.info("Test behavior initialized")

    def run(self, brain) -> bool:
        """
        Run one iteration of the test behavior.
        
        Args:
            brain: RatBrain instance with access to motors, LEDs, servos
        
        Returns:
            True to continue testing, False to finish and return to IDLE
        """
        try:
            if self.test_phase == 0:
                return self._test_led(brain)
            elif self.test_phase == 1:
                return self._test_servo(brain)
            elif self.test_phase == 2:
                return self._test_motor(brain)
            else:
                # All tests complete
                logger.info("All hardware tests completed!")
                brain.led.turn_off()
                return False
        
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
            brain.motor.stop()
            brain.led.turn_off()
            return False
        except Exception as e:
            logger.error(f"Test error: {e}", exc_info=True)
            brain.motor.stop()
            brain.led.set_color((255, 0, 0))  # Red = error
            time.sleep(1)
            brain.led.turn_off()
            return False

    def _test_led(self, brain) -> bool:
        """
        Test LED functionality with 1 second per color.
        """
        self.current_phase_name = "LED"
        colors = [
            ((255, 0, 0), "Red"),
            ((0, 255, 0), "Green"),
            ((0, 0, 255), "Blue"),
            ((255, 255, 255), "White"),
            ((255, 255, 0), "Yellow"),
            ((0, 255, 255), "Cyan"),
            ((255, 0, 255), "Magenta"),
        ]
        
        # Reset timer on first call or phase change
        if self.phase_step == 0:
            self.phase_start_time = time.time()
        
        # Individual color tests - 1 second each
        elapsed = time.time() - self.phase_start_time
        color_index = int(elapsed)  # Every 1 second, move to next color
        
        if color_index < len(colors):
            color, name = colors[color_index]
            brain.led.set_color(color)
            logger.info(f"LED Test: {name} {color} (showing for 1s)")
            return True
        
        # All color tests done - move to servo
        else:
            brain.led.turn_off()
            logger.info("LED tests completed! Moving to servo tests...")
            self.test_phase = 1
            self.phase_step = 0
            self.phase_start_time = time.time()
            return True

    def _test_servo(self, brain) -> bool:
        """
        Test servo motion control with visual delays.
        """
        self.current_phase_name = "SERVO"
        servo_controller = brain.servo
        
        movements = [
            ("Servo 0 sweep UP (90→150)", lambda: self._servo_sweep(servo_controller, '0', 90, 150)),
            ("Servo 0 sweep DOWN (150→90)", lambda: self._servo_sweep(servo_controller, '0', 150, 90)),
            ("Servo 1 sweep UP (90→140)", lambda: self._servo_sweep(servo_controller, '1', 90, 140)),
            ("Servo 1 sweep DOWN (140→90)", lambda: self._servo_sweep(servo_controller, '1', 140, 90)),
        ]
        
        if self.phase_step < len(movements):
            move_name, move_func = movements[self.phase_step]
            logger.info(f"Servo Test: {move_name}")
            move_func()
            self.phase_step += 1
            
            # Brief pause between movements to observe
            time.sleep(0.5)
            return True
        
        # Servo test complete - move to motor test
        else:
            logger.info("Servo tests completed! Moving to motor tests...")
            self.test_phase = 2
            self.phase_step = 0
            return True
    
    def _servo_sweep(self, servo_controller, channel, start, end):
        """Helper: Sweep servo from start to end angle."""
        if start < end:
            for angle in range(start, end + 1, 1):
                servo_controller.setServoAngle(channel, angle)
                time.sleep(0.01)
        else:
            for angle in range(start, end - 1, -1):
                servo_controller.setServoAngle(channel, angle)
                time.sleep(0.01)

    def _test_motor(self, brain) -> bool:
        """
        Test motor movement control with visual timing.
        """
        self.current_phase_name = "MOTOR"
        motor_controller = brain.motor
        
        movements = [
            ("Forward (2s)", lambda: motor_controller.setMotorModel(2000, 2000), 2.0),
            ("Backward (2s)", lambda: motor_controller.setMotorModel(-2000, -2000), 2.0),
            ("Spin Left (2s)", lambda: motor_controller.setMotorModel(-2000, 2000), 2.0),
            ("Spin Right (2s)", lambda: motor_controller.setMotorModel(2000, -2000), 2.0),
            ("Diagonal Front-Left (2s)", lambda: motor_controller.setMotorModel(1000, 2000), 2.0),
            ("Diagonal Front-Right (2s)", lambda: motor_controller.setMotorModel(2000, 1000), 2.0),
            ("Stop", lambda: motor_controller.setMotorModel(0, 0), 0.5),
        ]
        
        if self.phase_step < len(movements):
            move_name, move_func, duration = movements[self.phase_step]
            logger.info(f"Motor Test: {move_name}")
            move_func()
            self.phase_step += 1
            time.sleep(duration)
            return True
        
        # Motor test complete - all tests done
        else:
            logger.info("Motor tests completed! All hardware tests finished!")
            motor_controller.setMotorModel(0, 0)
            brain.led.set_color((0, 255, 0))  # Green = success
            time.sleep(1)
            brain.led.turn_off()
            self.test_phase = 3  # Mark as complete
            return False

    def cleanup(self):
        """Cleanup when test behavior ends."""
        logger.info("Test behavior cleanup")
