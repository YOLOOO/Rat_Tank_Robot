"""
LED Hardware Abstraction
========================
Controls RGB LED strips with color and flash patterns.
Includes console visualization for testing without hardware.
"""

import time
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# ANSI color codes for terminal output
ANSI_COLORS = {
    (0, 255, 0): "\033[92m",      # Green (IDLE)
    (255, 0, 255): "\033[95m",    # Magenta (DANCE)
    (0, 0, 255): "\033[94m",      # Blue (PATROL)
    (255, 255, 0): "\033[93m",    # Yellow (SCAN)
    (255, 0, 0): "\033[91m",      # Red (ERROR)
    (255, 165, 0): "\033[33m",    # Orange (OBSTACLE)
    (0, 100, 255): "\033[36m",    # Cyan (RUNNING)
    (0, 0, 0): "\033[0m",         # Reset (OFF)
}
ANSI_RESET = "\033[0m"


def _rgb_to_ansi(rgb: Tuple[int, int, int]) -> str:
    """Get closest ANSI color code for RGB."""
    return ANSI_COLORS.get(rgb, ANSI_RESET)


def _visualize_led(rgb: Tuple[int, int, int], label: str = "") -> str:
    """Create a visual LED indicator for console."""
    if rgb == (0, 0, 0):
        symbol = "◯"  # Off
    else:
        symbol = "●"  # On/lit
    
    color_code = _rgb_to_ansi(rgb)
    return f"{color_code}{symbol}{ANSI_RESET} {label}"


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
        
        # Console visualization
        viz = _visualize_led(rgb)
        logger.info(f"LED set color {viz} RGB{rgb}")

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
        
        # Console visualization
        viz = _visualize_led(rgb)
        logger.info(f"LED flash started {viz} RGB{rgb} @ {interval}s interval")

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
        
        # Console visualization - show flash state occasionally
        if position_in_cycle < 0.05:  # Show state change at start of each phase
            state = "ON " if is_on else "OFF"
            if is_on:
                viz = _visualize_led(self.current_color)
            else:
                viz = _visualize_led((0, 0, 0))
            logger.debug(f"LED flash [{state}] {viz}")

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
