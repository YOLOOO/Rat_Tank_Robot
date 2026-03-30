"""
Freenove SPI LED Pixel Wrapper for Raspberry Pi 5
Uses SPI instead of PWM for LED control on newer Pi versions.
"""

import spidev
import numpy


class Freenove_SPI_LedPixel(object):
    """Freenove wrapper for WS2811/WS2812 RGB LED strips using SPI."""

    def __init__(self, count=4, bright=255, sequence='GRB', bus=0, device=0):
        """
        Initialize SPI LED controller.
        
        Args:
            count: Number of LEDs (default 4 for Freenove tank)
            bright: Brightness 0-255 (default 255)
            sequence: RGB color order ('RGB', 'RBG', 'GRB', 'GBR', 'BRG', 'BGR')
            bus: SPI bus number (default 0)
            device: SPI device number (default 0)
        """
        self.set_led_type(sequence)
        self.set_led_count(count)
        self.set_led_brightness(bright)
        self.led_begin(bus, device)
        self.set_all_led_color(0, 0, 0)

    def led_begin(self, bus=0, device=0):
        """Initialize SPI connection."""
        self.bus = bus
        self.device = device
        try:
            self.spi = spidev.SpiDev()
            self.spi.open(self.bus, self.device)
            self.spi.mode = 0
            self.led_init_state = 1
        except OSError as e:
            print(f"SPI initialization failed: {e}")
            print("Please check the configuration in /boot/firmware/config.txt.")
            if self.bus == 0:
                print("You can turn on the 'SPI' in 'Interface Options' by using 'sudo raspi-config'.")
                print("Or make sure that 'dtparam=spi=on' is not commented, then reboot the Raspberry Pi.")
            self.led_init_state = 0

    def check_spi_state(self):
        """Return the current SPI initialization state."""
        return self.led_init_state

    def led_close(self):
        """Turn off all LEDs and close SPI connection."""
        self.set_all_led_rgb([0, 0, 0])
        try:
            self.spi.close()
        except:
            pass

    def set_led_count(self, count):
        """Set the number of LEDs."""
        self.led_count = count
        self.led_color = [0, 0, 0] * self.led_count
        self.led_original_color = [0, 0, 0] * self.led_count

    def get_led_count(self):
        """Get the number of LEDs."""
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
        """Update the LED strip with the current color data via SPI."""
        try:
            # Prepare SPI data
            data = []
            for i in range(self.get_led_count()):
                data.append(self.led_color[i * 3])
                data.append(self.led_color[i * 3 + 1])
                data.append(self.led_color[i * 3 + 2])
            
            if self.led_init_state == 1 and hasattr(self, 'spi'):
                self.spi.writebytes(data)
        except Exception as e:
            pass
