import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import INFRARED_PCB_VERSION
from gpiozero import LineSensor


class Infrared:
    def __init__(self):
        if INFRARED_PCB_VERSION == 1:
            self.IR01 = 16
            self.IR02 = 20
            self.IR03 = 21
        elif INFRARED_PCB_VERSION == 2:
            self.IR01 = 16
            self.IR02 = 26
            self.IR03 = 21

        self.IR01_sensor = LineSensor(self.IR01)
        self.IR02_sensor = LineSensor(self.IR02)
        self.IR03_sensor = LineSensor(self.IR03)

    def read_one_infrared(self, channel):
        if channel == 1:
            return 1 if self.IR01_sensor.value else 0
        elif channel == 2:
            return 1 if self.IR02_sensor.value else 0
        elif channel == 3:
            return 1 if self.IR03_sensor.value else 0

    def read_all_infrared(self):
        return (self.read_one_infrared(1) << 2) | (self.read_one_infrared(2) << 1) | self.read_one_infrared(3)

    def close(self):
        self.IR01_sensor.close()
        self.IR02_sensor.close()
        self.IR03_sensor.close()


if __name__ == '__main__':
    import time
    infrared = Infrared()
    try:
        while True:
            print("Infrared value: {}".format(infrared.read_all_infrared()))
            time.sleep(0.5)
    except KeyboardInterrupt:
        infrared.close()
        print("\nEnd of program")
