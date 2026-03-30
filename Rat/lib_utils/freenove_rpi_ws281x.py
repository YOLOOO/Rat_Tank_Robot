"""
Freenove RGB LED Strip Wrapper for Raspberry Pi
Wraps Adafruit_NeoPixel with brightness and color format handling.
"""

import time
from rpi_ws281x import Adafruit_NeoPixel, Color


class Freenove_RPI_WS281X:
    """Freenove wrapper for WS2811/WS2812 RGB LED strips."""

    def __init__(self, led_count=4, bright=255, sequence="RGB"):
        """
        Initialize the LED strip wrapper.
        
        Args:
            led_count: Number of LEDs (default 4 for Freenove tank)
            bright: Brightness 0-255 (default 255)
            sequence: RGB color order (RGB, RBG, GRB, GBR, BRG, BGR)
        """
        self.set_led_type(sequence)
        self.set_led_count(led_count)
        self.set_led_brightness(bright)
        self.led_begin()
        self.set_all_led_color(0, 0, 0)

    def led_begin(self):
        """Initialize the NeoPixel strip."""
        self.strip = Adafruit_NeoPixel(self.get_led_count(), 18, 800000, 10, False, self.led_brightness, 0)
        self.led_init_state = 0 if self.strip.begin() else 1

    def check_rpi_ws281x_state(self):
        """Check the initialization state of the NeoPixel strip."""
        return self.led_init_state

    def led_close(self):
        """Turn off all LEDs."""
        self.set_all_led_rgb([0, 0, 0])

    def set_led_count(self, count):
        """Set the number of LEDs in the strip."""
        self.led_count = count
        self.led_color = [0, 0, 0] * self.led_count
        self.led_original_color = [0, 0, 0] * self.led_count

    def get_led_count(self):
        """Get the number of LEDs in the strip."""
        return self.led_count

    def set_led_type(self, rgb_type):
        """Set the RGB sequence type for the LEDs."""
        try:
            led_type = ['RGB', 'RBG', 'GRB', 'GBR', 'BRG', 'BGR']
            led_type_offset = [0x06, 0x09, 0x12, 0x21, 0x18, 0x24]
            index = led_type.index(rgb_type)
            self.led_red_offset = (led_type_offset[index] >> 4) & 0x03
            self.led_green_offset = (led_type_offset[index] >> 2) & 0x03
            self.led_blue_offset = (led_type_offset[index] >> 0) & 0x03
            return index
        except ValueError:
            self.led_red_offset = 1
            self.led_green_offset = 0
            self.led_blue_offset = 2
            return -1

    def set_led_brightness(self, brightness):
        """Set the brightness of the LEDs."""
        self.led_brightness = brightness
        for i in range(self.get_led_count()):
            self.set_led_rgb_data(i, self.led_original_color)

    def set_ledpixel(self, index, r, g, b):
        """Set the color of a specific LED."""
        p = [0, 0, 0]
        p[self.led_red_offset] = round(r * self.led_brightness / 255)
        p[self.led_green_offset] = round(g * self.led_brightness / 255)
        p[self.led_blue_offset] = round(b * self.led_brightness / 255)
        self.led_original_color[index * 3 + self.led_red_offset] = r
        self.led_original_color[index * 3 + self.led_green_offset] = g
        self.led_original_color[index * 3 + self.led_blue_offset] = b
        for i in range(3):
            self.led_color[index * 3 + i] = p[i]

    def set_led_color_data(self, index, r, g, b):
        """Set the color data of a specific LED."""
        self.set_ledpixel(index, r, g, b)

    def set_led_rgb_data(self, index, color):
        """Set the RGB data of a specific LED."""
        self.set_ledpixel(index, color[0], color[1], color[2])

    def set_led_color(self, index, r, g, b):
        """Set the color of a specific LED and update the display."""
        self.set_ledpixel(index, r, g, b)
        self.show()

    def set_led_rgb(self, index, color):
        """Set the RGB color of a specific LED and update the display."""
        self.set_led_rgb_data(index, color)
        self.show()

    def set_all_led_color_data(self, r, g, b):
        """Set the color data of all LEDs."""
        for i in range(self.get_led_count()):
            self.set_led_color_data(i, r, g, b)

    def set_all_led_rgb_data(self, color):
        """Set the RGB data of all LEDs."""
        for i in range(self.get_led_count()):
            self.set_led_rgb_data(i, color)

    def set_all_led_color(self, r, g, b):
        """Set the color of all LEDs and update the display."""
        for i in range(self.get_led_count()):
            self.set_led_color_data(i, r, g, b)
        self.show()

    def set_all_led_rgb(self, color):
        """Set the RGB color of all LEDs and update the display."""
        for i in range(self.get_led_count()):
            self.set_led_rgb_data(i, color)
        self.show()

    def show(self):
        """Update the LED strip with the current color data."""
        for i in range(self.get_led_count()):
            self.strip.setPixelColor(i, Color(self.led_color[i * 3], self.led_color[i * 3 + 1], self.led_color[i * 3 + 2]))
        self.strip.show()

    def wheel(self, pos):
        """Generate a color wheel value based on the position."""
        if pos < 85:
            return [(255 - pos * 3), (pos * 3), 0]
        elif pos < 170:
            pos = pos - 85
            return [0, (255 - pos * 3), (pos * 3)]
        else:
            pos = pos - 170
            return [(pos * 3), 0, (255 - pos * 3)]
