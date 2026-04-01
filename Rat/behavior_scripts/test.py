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
        Test LED functionality (reference flow).
        
        Each color shown for 1 second before moving to next.
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
        
        # Individual color tests - 1 second each
        if self.phase_step < len(colors):
            color, name = colors[self.phase_step]
            brain.led.set_color(color)
            logger.info(f"LED Test: {name} {color}")
            self.phase_step += 1
            return True
        
        # All color tests done - move to servo
        else:
            brain.led.turn_off()
            logger.info("LED tests completed! Moving to servo tests...")
            self.test_phase = 1
            self.phase_step = 0
            return True

    def _test_servo(self, brain) -> bool:
        """
        Test servo motion control (reference API).
        
        Exactly matches Code/Server/test.py servo test:
        - Smooth 1-degree steps at 0.01s intervals
        - 4 sweep movements repeated 3 times
        """
        self.current_phase_name = "SERVO"
        servo_controller = brain.servo
        
        # Motion 1: Servo 0 sweep 90→150 (3 cycles)
        if self.phase_step < 3:
            cycle = self.phase_step
            logger.info(f"Servo Test: Servo 0 sweep (cycle {cycle + 1}/3)")
            # Smooth sweep: 1 degree steps, 0.01s delay = 0.6s per sweep
            for i in range(90, 150, 1):
                servo_controller.setServoAngle('0', i)
                time.sleep(0.01)
            self.phase_step += 1
            return True
        
        # Motion 2: Servo 1 sweep 140→90 (3 cycles)
        elif self.phase_step < 6:
            cycle = self.phase_step - 3
            logger.info(f"Servo Test: Servo 1 sweep down (cycle {cycle + 1}/3)")
            # Smooth sweep: 1 degree steps, 0.01s delay
            for i in range(140, 90, -1):
                servo_controller.setServoAngle('1', i)
                time.sleep(0.01)
            self.phase_step += 1
            return True
        
        # Motion 3: Servo 1 sweep 90→140 (3 cycles)
        elif self.phase_step < 9:
            cycle = self.phase_step - 6
            logger.info(f"Servo Test: Servo 1 sweep up (cycle {cycle + 1}/3)")
            # Smooth sweep: 1 degree steps, 0.01s delay
            for i in range(90, 140, 1):
                servo_controller.setServoAngle('1', i)
                time.sleep(0.01)
            self.phase_step += 1
            return True
        
        # Motion 4: Servo 0 sweep 150→90 (3 cycles)
        elif self.phase_step < 12:
            cycle = self.phase_step - 9
            logger.info(f"Servo Test: Servo 0 sweep down (cycle {cycle + 1}/3)")
            # Smooth sweep: 1 degree steps, 0.01s delay
            for i in range(150, 90, -1):
                servo_controller.setServoAngle('0', i)
                time.sleep(0.01)
            self.phase_step += 1
            return True
        
        # Servo test complete - move to motor test
        else:
            logger.info("Servo tests completed! Moving to motor tests...")
            self.test_phase = 2
            self.phase_step = 0
            return True

    def _test_motor(self, brain) -> bool:
        """
        Test motor movement control (reference API).
        
        Uses duty cycles -4095 to 4095 matching Code/Server reference.
        """
        self.current_phase_name = "MOTOR"
        motor_controller = brain.motor
        
        movements = [
            ("Forward", lambda: motor_controller.setMotorModel(2000, 2000)),
            ("Backward", lambda: motor_controller.setMotorModel(-2000, -2000)),
            ("Spin Left", lambda: motor_controller.setMotorModel(-2000, 2000)),
            ("Spin Right", lambda: motor_controller.setMotorModel(2000, -2000)),
            ("Stop", lambda: motor_controller.setMotorModel(0, 0)),
        ]
        
        if self.phase_step < len(movements):
            move_name, move_func = movements[self.phase_step]
            
            if move_name == "Stop":
                logger.info(f"Motor Test: {move_name}")
                move_func()
                self.phase_step += 1
                time.sleep(0.5)
            else:
                logger.info(f"Motor Test: {move_name} (2s)")
                move_func()
                self.phase_step += 1
                time.sleep(2)
            
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
