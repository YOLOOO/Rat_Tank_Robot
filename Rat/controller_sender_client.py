"""
Controller Sender Client (DEV PC)
==================================
Sends commands to the robot via TCP.
Robot IP and port come from config.py — just run with no arguments:
    python controller_sender_client.py

Keyboard-only. Two modes, both read from the same keys:

Menu mode (default):
    A - LEFT
    D - RIGHT
    S - SELECT (selecting REMOTE_CONTROL switches to drive mode)
    H - HALT
    Q - QUIT

Drive mode (after selecting REMOTE_CONTROL):
    W - forward
    S - backward
    A - spin left
    D - spin right
    SPACE - stop moving (stays in drive mode)
    R - ARM_TOGGLE (raise/lower)
    G - GRIP_TOGGLE (open/close)
    H - HALT (stops the robot and returns to menu mode)
    Q - QUIT

Held-key driving isn't possible here — Windows console key reads are
discrete presses, not press/release events — so each tap sets the motors
to a fixed state until the next tap changes it.
"""

import sys
import socket
import logging
import threading
import platform
import time

import config

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

if platform.system() == "Windows":
    import msvcrt
else:
    import tty
    import termios

CMD_LEFT   = "LEFT"
CMD_RIGHT  = "RIGHT"
CMD_SELECT = "SELECT"
CMD_HALT   = "HALT"
CMD_QUIT   = "QUIT"

_SPEED = config.KEYBOARD_DRIVE_SPEED

MENU_KEY_MAP = {
    'a': CMD_LEFT,
    'd': CMD_RIGHT,
    's': CMD_SELECT,
    'h': CMD_HALT,
    'q': CMD_QUIT,
}

DRIVE_KEY_MAP = {
    'w': f"MOTOR:{-_SPEED}:{-_SPEED}",   # forward
    's': f"MOTOR:{_SPEED}:{_SPEED}",     # backward
    'a': f"MOTOR:{_SPEED}:{-_SPEED}",    # spin left
    'd': f"MOTOR:{-_SPEED}:{_SPEED}",    # spin right
    ' ': "MOTOR:0:0",                    # stop moving, stay in drive mode
    'r': "ARM_TOGGLE",
    'g': "GRIP_TOGGLE",
    'h': CMD_HALT,
    'q': CMD_QUIT,
}


# ------------------------------------------------------------------
# TCP connection
# ------------------------------------------------------------------

class RobotConnection:
    """Manages TCP connection to the robot with auto-reconnect."""

    # Ongoing send/recv timeout once connected — bounds how long a single
    # keypress can block the keyboard thread if the link goes half-dead
    # (socket looks fine locally but the peer stopped acking).
    SEND_TIMEOUT = 3.0

    # Minimum time between reconnect attempts. Without this, every keypress
    # while disconnected (and OS key-repeat sends many per second while a
    # key is held) fires its own blocking connect() — the "reconnect loop"
    # spam. This throttles it to one attempt per cooldown window.
    RECONNECT_COOLDOWN = 2.0

    def __init__(self):
        self.host           = config.ROBOT_IP
        self.port           = config.SERVER_PORT
        self.socket         = None
        self.connected      = False
        self._lock          = threading.Lock()
        self._last_attempt  = 0.0

    def connect(self) -> bool:
        self._last_attempt = time.time()

        # A previous socket left over from a dead connection is never closed
        # before being replaced — leaks a handle on every reconnect attempt.
        if self.socket is not None:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((self.host, self.port))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Bounded (not None) so a half-dead link can't hang a send()
            # indefinitely — that stall was blocking the keyboard reader.
            sock.settimeout(self.SEND_TIMEOUT)
            self.socket    = sock
            self.connected = True
            logger.info(f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False

    def send(self, command: str) -> bool:
        with self._lock:
            if not self.connected:
                return False
            try:
                self.socket.send(f"{command}\n".encode("utf-8"))
                logger.debug(f"Sent: {command}")
                return True
            except Exception as e:
                logger.error(f"Send failed: {e}")
                self.connected = False
                return False

    def ensure_connected(self) -> bool:
        if self.connected:
            return True
        if time.time() - self._last_attempt < self.RECONNECT_COOLDOWN:
            return False
        logger.info("Reconnecting...")
        return self.connect()

    def disconnect(self):
        with self._lock:
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
                self.socket = None
            self.connected = False
            logger.info("Disconnected")


# ------------------------------------------------------------------
# Keyboard backend
# ------------------------------------------------------------------

class KeyboardBackend:
    """
    Reads raw single keypresses in a background thread and passes each
    one to a callback. Mode-dependent interpretation (menu vs drive)
    happens in RobotController, not here.
    """

    def __init__(self, on_key):
        self._on_key  = on_key
        self._thread  = None
        self._running = False

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self):
        while self._running:
            try:
                if platform.system() == "Windows":
                    key = msvcrt.getwch().lower()
                else:
                    fd  = sys.stdin.fileno()
                    old = termios.tcgetattr(fd)
                    try:
                        tty.setraw(fd)
                        key = sys.stdin.read(1).lower()
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old)

                self._on_key(key)

            except Exception as e:
                if self._running:
                    logger.error(f"Keyboard read error: {e}")
                break

    def stop(self):
        self._running = False


# ------------------------------------------------------------------
# Combined controller
# ------------------------------------------------------------------

class RobotController:
    """
    Keyboard-driven client. Tracks menu selection and drive mode locally
    so the same keys can mean "navigate the menu" or "drive the robot"
    depending on context.
    """

    def __init__(self):
        self.connection  = RobotConnection()
        self._quit_event = threading.Event()
        self._menu       = sorted(config.MISSIONS.keys(), key=lambda n: config.MISSIONS[n][2])
        self._idx        = 0
        self._driving    = False  # True once REMOTE_CONTROL has been selected

    def _on_key(self, key: str):
        key_map = DRIVE_KEY_MAP if self._driving else MENU_KEY_MAP
        command = key_map.get(key)
        if command is None:
            return

        if command == CMD_QUIT:
            print("\nQuitting...")
            self._quit_event.set()
            return

        if command == CMD_HALT:
            self._driving = False

        if not self._driving:
            if command == CMD_LEFT:
                self._idx = (self._idx - 1) % len(self._menu)
            elif command == CMD_RIGHT:
                self._idx = (self._idx + 1) % len(self._menu)
            elif command == CMD_SELECT:
                selected = self._menu[self._idx]
                if selected == "REMOTE_CONTROL":
                    self._driving = True
                    print("\n  DRIVE MODE — W/A/S/D drive, SPACE stop, R arm, G grip, H halt\n")

        self.connection.ensure_connected()
        self.connection.send(command)
        if command == CMD_HALT:
            print("  !! HALT sent !!")

    def run(self):
        print("\n" + "=" * 50)
        print("  RAT OS — CONTROLLER")
        print("=" * 50)
        print("  A - LEFT    D - RIGHT")
        print("  S - SELECT  H - HALT")
        print("  Q - QUIT")
        print("  Select REMOTE_CONTROL to switch to drive mode:")
        print("    W/A/S/D drive, SPACE stop, R arm, G grip, H halt")
        print("=" * 50 + "\n")

        if not self.connection.connect():
            logger.error(f"Could not connect to robot at {config.ROBOT_IP}:{config.SERVER_PORT}")
            sys.exit(1)

        keyboard = KeyboardBackend(on_key=self._on_key)
        keyboard.start()

        try:
            self._quit_event.wait()  # Block until Q is pressed
        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            keyboard.stop()
            self.connection.disconnect()
            print("Controller stopped.")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    controller = RobotController()
    controller.run()


if __name__ == "__main__":
    main()
