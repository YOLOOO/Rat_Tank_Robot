"""
LED Hardware Abstraction
========================
Controls RGB LED strips with color and flash patterns.
"""

import time
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class LEDController:
    """
    Abstraction for LED control.
    Works on Raspberry Pi with ws2812b (NeoPixel) or similar.
    """

    def __init__(self, pin: int = 18, count: int = 24, brightness: int = 255):
        """
        Initialize LED controller.
        
        Args:
            pin: GPIO pin number
            count: Number of LEDs
            brightness: Max brightness (0-255)
        """
        self.pin = pin
        self.count = count
        self.brightness = brightness
        self.current_color = (0, 0, 0)
        self.is_flashing = False
        self.flash_start_time = None
        self.flash_interval = 0.5
        self.hardware_available = False

        # Try to import actual hardware driver
        try:
            # Try local library first (for development/consistency)
            try:
                from lib_utils.rpi_ws281x import Adafruit_NeoPixel, Color
                logger.debug("Using local rpi_ws281x library")
            except (ImportError, ModuleNotFoundError) as e:
                # Fall back to system package
                logger.debug(f"Local import failed ({e}), trying system package")
                from rpi_ws281x import Adafruit_NeoPixel, Color
                logger.debug("Using system rpi_ws281x library")
            
            self.Adafruit_NeoPixel = Adafruit_NeoPixel
            self.Color = Color
            self.strip = Adafruit_NeoPixel(count, pin, 800000, 10, False, brightness)
            try:
                self.strip.begin()
                logger.info(f"LEDs initialized on pin {pin} with {count} LEDs")
                self.hardware_available = True
            except RuntimeError as hw_err:
                logger.warning(f"LED hardware init failed: {hw_err} - running in simulation mode")
                self.hardware_available = False
        except ImportError:
            logger.warning("LED library not available - running in simulation mode")
            self.hardware_available = False
        except Exception as e:
            logger.warning(f"LED initialization error: {e} - running in simulation mode")
            self.hardware_available = False

    def set_color(self, rgb: Tuple[int, int, int]):
        """Set all LEDs to a single color (stop flashing)."""
        self.current_color = rgb
        self.is_flashing = False
        
        if self.hardware_available:
            for i in range(self.count):
                self.strip.setPixelColor(i, self.Color(rgb[0], rgb[1], rgb[2]))
            self.strip.show()
        
        logger.debug(f"LED color set to RGB{rgb}")

    def turn_off(self):
        """Turn off all LEDs."""
        self.set_color((0, 0, 0))

    def flash(self, rgb: Tuple[int, int, int], interval: float = 0.5):
        """
        Start flashing LEDs at given color.
        
        Args:
            rgb: Color tuple (R, G, B)
            interval: Flash interval in seconds
        """
        self.current_color = rgb
        self.is_flashing = True
        self.flash_interval = interval
        self.flash_start_time = time.time()
        logger.debug(f"LED flash started: RGB{rgb}, interval={interval}s")

    def update(self):
        """Called periodically to update flash state."""
        if not self.is_flashing:
            return

        elapsed = time.time() - self.flash_start_time
        cycle_time = self.flash_interval * 2  # on + off time
        position_in_cycle = elapsed % cycle_time

        # First half: on, second half: off
        is_on = position_in_cycle < self.flash_interval

        if self.hardware_available:
            color = self.current_color if is_on else (0, 0, 0)
            for i in range(self.count):
                self.strip.setPixelColor(i, self.Color(color[0], color[1], color[2]))
            self.strip.show()

    def pulse(self, rgb: Tuple[int, int, int], cycles: int = 3):
        """Pulse LEDs a specific number of times."""
        for _ in range(cycles):
            self.set_color(rgb)
            time.sleep(0.2)
            self.set_color((0, 0, 0))
            time.sleep(0.2)


# Singleton instance
_led_controller = None


def get_led_controller(pin: int = 18, count: int = 24, brightness: int = 255) -> LEDController:
    """Get or create the LED controller singleton."""
    global _led_controller
    if _led_controller is None:
        _led_controller = LEDController(pin, count, brightness)
    return _led_controller
