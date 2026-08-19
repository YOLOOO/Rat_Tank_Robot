"""
tools/probe_steam_controller.py
================================
Standalone diagnostic — lists connected controllers and streams live
axis/button values so you can confirm the Steam Controller is being
seen correctly and tune STEAM_DEADZONE in config.py.

Run on the DEV PC (Windows), with Steam running and the controller
connected via its dongle:
    python tools/probe_steam_controller.py

Move the sticks and press each button. Ctrl-C to quit.
"""

import sys
import time

try:
    import pygame
except ImportError:
    print("pygame not installed. Run: pip install pygame")
    sys.exit(1)

pygame.init()
pygame.controller.init()

count = pygame.controller.get_count()
print(f"\nControllers found: {count}")
if count == 0:
    print("None detected — is Steam running with Xbox Configuration Support enabled,")
    print("and the controller connected via its wireless dongle?")
    sys.exit(1)

controller = pygame.controller.Controller(0)
controller.init()
print(f"Using: {controller.get_name()}\n")

AXES = {
    "LEFTX": pygame.CONTROLLER_AXIS_LEFTX,
    "LEFTY": pygame.CONTROLLER_AXIS_LEFTY,
    "RIGHTX": pygame.CONTROLLER_AXIS_RIGHTX,
    "RIGHTY": pygame.CONTROLLER_AXIS_RIGHTY,
    "TRIGGERLEFT": pygame.CONTROLLER_AXIS_TRIGGERLEFT,
    "TRIGGERRIGHT": pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
}

BUTTONS = {
    "A": pygame.CONTROLLER_BUTTON_A,
    "B": pygame.CONTROLLER_BUTTON_B,
    "X": pygame.CONTROLLER_BUTTON_X,
    "Y": pygame.CONTROLLER_BUTTON_Y,
    "BACK": pygame.CONTROLLER_BUTTON_BACK,
    "START": pygame.CONTROLLER_BUTTON_START,
    "LEFTSTICK": pygame.CONTROLLER_BUTTON_LEFTSTICK,
    "RIGHTSTICK": pygame.CONTROLLER_BUTTON_RIGHTSTICK,
    "LEFTSHOULDER": pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
    "RIGHTSHOULDER": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
    "DPAD_UP": pygame.CONTROLLER_BUTTON_DPAD_UP,
    "DPAD_DOWN": pygame.CONTROLLER_BUTTON_DPAD_DOWN,
    "DPAD_LEFT": pygame.CONTROLLER_BUTTON_DPAD_LEFT,
    "DPAD_RIGHT": pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
}

print("Streaming live values — move sticks / press buttons. Ctrl-C to quit.\n")

try:
    while True:
        pygame.event.pump()

        axis_vals = {name: controller.get_axis(axis) / 32768.0 for name, axis in AXES.items()}
        pressed   = [name for name, btn in BUTTONS.items() if controller.get_button(btn)]

        line = "  ".join(f"{name}:{val:+.2f}" for name, val in axis_vals.items())
        if pressed:
            line += "   BUTTONS: " + ",".join(pressed)

        print("\r" + line + " " * 20, end="", flush=True)
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nStopped.")
