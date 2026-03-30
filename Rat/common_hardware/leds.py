"""
LED Hardware Abstraction
========================
Controls RGB LED strips with color and flash patterns.
Adapted from Freenove FNK0077 Tank implementation.
Includes console visualization for testing without hardware.
"""

import time
import logging
import subprocess
import os
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


class LEDController:
    """
    Abstraction for LED control using Freenove_RPI_WS281X wrapper.
    Works on Raspberry Pi with ws2812b (NeoPixel) LED strips.
    Gracefully falls back to simulation mode if hardware unavailable.
    """

    def __init__(self, pin: int = 18, count: int = 4, brightness: int = 255, 
                 color_format: str = 'RGB', pcb_version: int = 2):
        """
        Initialize LED controller using Freenove wrapper.
        
        Args:
            pin: GPIO pin number (18 for GPIO_GEN1)
            count: Number of LEDs (typically 4 for Freenove tank)
            brightness: Max brightness (0-255)
            color_format: RGB sequence type ('RGB', 'RBG', 'GRB', 'GBR', 'BRG', 'BGR')
            pcb_version: PCB version (1 or 2)
        """
        self.pin = pin
        self.count = count
        self.brightness = brightness
        self.color_format = color_format
        self.pcb_version = pcb_version
        self.current_color = (0, 0, 0)
        self.is_flashing = False
        self.flash_start_time = None
        self.flash_interval = 0.5
        self.hardware_available = False
        self.strip = None
        self.pi_version = _get_raspberry_pi_version()
        
        # State tracking - only print when state actually changes
        self._last_color = None
        self._last_flash_state = None
        self._last_flash_params = None  # Track (color, interval) to prevent repeated prints

        # Check hardware compatibility
        if not self._is_hardware_supported():
            logger.warning(f"PCB v{pcb_version} not supported on Raspberry Pi {self.pi_version} - simulation mode")
            return

        # Try to initialize hardware
        self._init_hardware()

    def _is_hardware_supported(self) -> bool:
        """Check if hardware combination is supported."""
        # PCB v1 not supported on Raspberry Pi 5
        if self.pcb_version == 1 and self.pi_version == 2:
            return False
        # PCB v2 works on both Pi versions
        if self.pcb_version == 2:
            return True
        return True

    def _init_hardware(self):
        """Initialize appropriate LED wrapper based on Pi and PCB version (using Freenove mapping)."""
        try:
            # Construct import path for local lib_utils
            lib_utils_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lib_utils')
            
            # Add lib_utils to path
            import sys
            if lib_utils_path not in sys.path:
                sys.path.insert(0, lib_utils_path)
            
            logger.debug(f"Initializing LEDs: Pi_v{self.pi_version}, PCB_v{self.pcb_version}")
            
            # Use Freenove's exact mapping logic
            if self.pcb_version == 1 and self.pi_version == 1:
                # Old Pi + PCB v1: Use RPI_WS281X with RGB
                logger.debug("Using RPI_WS281X wrapper (Pi < 5, PCB v1)")
                try:
                    from freenove_rpi_ws281x import Freenove_RPI_WS281X
                    self.strip = Freenove_RPI_WS281X(
                        led_count=self.count,
                        bright=self.brightness,
                        sequence=self.color_format  # RGB
                    )
                    if self.strip.check_rpi_ws281x_state() == 0:
                        self.hardware_available = True
                        logger.info(f"✓ LEDs (RPI_WS281X): pin=18, count={self.count}, "
                                  f"brightness={self.brightness}, format=RGB, Pi_v1, PCB_v1")
                    else:
                        logger.error("RPI_WS281X initialization failed")
                        self.hardware_available = False
                except Exception as e:
                    logger.error(f"RPI_WS281X initialization error: {e}")
                    self.hardware_available = False
                    
            elif self.pcb_version == 2 and (self.pi_version == 1 or self.pi_version == 2):
                # Any Pi + PCB v2: Use SPI with GRB
                logger.debug(f"Using SPI wrapper (Pi v{self.pi_version}, PCB v2)")
                try:
                    from freenove_spi_ledpixel import Freenove_SPI_LedPixel
                    self.strip = Freenove_SPI_LedPixel(
                        count=self.count,
                        bright=self.brightness,
                        sequence='GRB'  # SPI PCB v2 uses GRB
                    )
                    if self.strip.check_spi_state() == 1:
                        self.hardware_available = True
                        logger.info(f"✓ LEDs (SPI): bus=0, count={self.count}, "
                                  f"brightness={self.brightness}, format=GRB, Pi_v{self.pi_version}, PCB_v2")
                    else:
                        logger.error("SPI LED initialization failed - check /boot/firmware/config.txt for SPI enabled")
                        self.hardware_available = False
                except ImportError as e:
                    logger.error(f"spidev import failed: {e} - install with: pip install spidev")
                    self.hardware_available = False
                except Exception as e:
                    logger.error(f"SPI LED initialization error: {e}")
                    self.hardware_available = False
                    
            elif self.pcb_version == 1 and self.pi_version == 2:
                # Pi 5 + PCB v1: Not supported!
                logger.error("PCB Version 1.0 is NOT supported on Raspberry PI 5!")
                logger.error("You need PCB v2 for Pi 5. Check if LEDs connected to correct pins.")
                self.hardware_available = False
            else:
                logger.error(f"Unsupported combination: Pi_v{self.pi_version}, PCB_v{self.pcb_version}")
                self.hardware_available = False
                
        except Exception as e:
            logger.error(f"LED initialization critical error: {type(e).__name__}: {e}", exc_info=True)
            self.hardware_available = False


    def set_color(self, rgb: Tuple[int, int, int]):
        """Set all LEDs to a single color (stop flashing)."""
        self.current_color = rgb
        self.is_flashing = False
        
        # Only print if color actually changed
        if self._last_color != rgb:
            self._last_color = rgb
            self._last_flash_state = None  # Reset flash state tracking
            
            if self.hardware_available and self.strip:
                try:
                    self.strip.set_all_led_rgb(rgb)
                except Exception as e:
                    logger.debug(f"Set color hardware error: {e}")
            
            # Console visualization
            viz = _visualize_led(rgb)
            logger.info(f"LED set color {viz} RGB{rgb}")
        else:
            # Still update hardware silently if color not changed
            if self.hardware_available and self.strip:
                try:
                    self.strip.set_all_led_rgb(rgb)
                except Exception as e:
                    logger.debug(f"Set color hardware error: {e}")

    
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
        # Only print if flash parameters actually changed
        current_params = (rgb, interval)
        if self._last_flash_params != current_params:
            self._last_flash_params = current_params
            self._last_flash_state = None  # Reset state to print next toggle
            
            self.current_color = rgb
            self.is_flashing = True
            self.flash_interval = interval
            self.flash_start_time = time.time()
            
            # Console visualization
            viz = _visualize_led(rgb)
            logger.info(f"LED flash started {viz} RGB{rgb} @ {interval}s interval")
            
            # Actually send to hardware
            if self.hardware_available and self.strip:
                try:
                    self.strip.set_all_led_rgb(rgb)
                except Exception as e:
                    logger.debug(f"Flash hardware error: {e}")

    def update(self):
        """Called periodically to update flash state."""
        if not self.is_flashing:
            return

        elapsed = time.time() - self.flash_start_time
        cycle_time = self.flash_interval * 2  # on + off time
        position_in_cycle = elapsed % cycle_time

        # First half: on, second half: off
        is_on = position_in_cycle < self.flash_interval

        if self.hardware_available and self.strip:
            try:
                color = self.current_color if is_on else (0, 0, 0)
                self.strip.set_all_led_rgb(color)
            except Exception as e:
                logger.debug(f"Flash update hardware error: {e}")
        
        # Only print when flash state actually changes (ON->OFF or OFF->ON)
        if self._last_flash_state != is_on:
            self._last_flash_state = is_on
            state = "ON" if is_on else "OFF"
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


def get_led_controller(pin: int = 18, count: int = 4, brightness: int = 255, 
                       color_format: str = 'RGB', pcb_version: int = 2) -> LEDController:
    """
    Get or create the LED controller singleton.
    
    Args:
        pin: GPIO pin number (default 18 for Freenove tank)
        count: Number of LEDs (default 4 for Freenove tank)
        brightness: Max brightness 0-255 (default 255)
        color_format: RGB sequence type ('RGB', 'RBG', 'GRB', etc)
        pcb_version: PCB version 1 or 2 (auto-detected from Pi version)
    
    Returns:
        LEDController singleton instance
    """
    global _led_controller
    if _led_controller is None:
        _led_controller = LEDController(pin, count, brightness, color_format, pcb_version)
    return _led_controller
