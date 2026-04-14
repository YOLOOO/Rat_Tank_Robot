"""
Controller Sender Client (DEV PC)
==================================
Sends commands to the robot via TCP.
Robot IP and port come from config.py — just run with no arguments:
    python controller_sender_client.py

Both input backends run simultaneously in the same process:
    KeyboardBackend  — always active, menu navigation + HALT + quit
    MntMouseBackend  — always active if trackball is plugged in,
                       drives motors and arm during remote_control mission

Controls (keyboard):
    A - LEFT
    D - RIGHT
    S - SELECT
    H - HALT
    P - PAUSE / RESUME trackball (local toggle, not sent to robot)
    Q - QUIT

Controls (MNT trackball):
    Left extra (hold) → motors forward full speed
    Right extra (hold)→ motors backward full speed
    Ball X            → differential steering (slows one motor while driving)
    Left button       → ARM toggle
    Right button      → GRIP toggle
    Middle button     → HALT
"""

import sys
import socket
import logging
import threading
import platform

import config
from mnt_backend import MntMouseBackend

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


# ------------------------------------------------------------------
# TCP connection
# ------------------------------------------------------------------

class RobotConnection:
    """Manages TCP connection to the robot with auto-reconnect."""

    def __init__(self):
        self.host      = config.ROBOT_IP
        self.port      = config.SERVER_PORT
        self.socket    = None
        self.connected = False
        self._lock     = threading.Lock()

    def connect(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(None)
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
        if not self.connected:
            logger.info("Reconnecting...")
            return self.connect()
        return True

    def disconnect(self):
        with self._lock:
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
            self.connected = False
            logger.info("Disconnected")


# ------------------------------------------------------------------
# Keyboard backend
# ------------------------------------------------------------------

class KeyboardBackend:
    """
    Reads raw single keypresses in a background thread.
    Puts commands into a shared callback.
    """

    KEY_MAP = {
        'a': CMD_LEFT,
        'd': CMD_RIGHT,
        's': CMD_SELECT,
        'h': CMD_HALT,
        'q': CMD_QUIT,
        'p': "MNT_TOGGLE",
    }

    def __init__(self, on_command):
        self._on_command = on_command
        self._thread     = None
        self._running    = False

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

                command = self.KEY_MAP.get(key)
                if command:
                    self._on_command(command)

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
    Runs keyboard and MNT backends simultaneously.
    Both feed into the same TCP connection.
    Keyboard Q shuts everything down cleanly.
    """

    def __init__(self):
        self.connection  = RobotConnection()
        self._quit_event = threading.Event()
        self._mnt        = None  # set in run() once backend is created

    def _on_command(self, command: str):
        if command == CMD_QUIT:
            print("\nQuitting...")
            self._quit_event.set()
            return
        if command == "MNT_TOGGLE":
            if self._mnt is not None:
                self._mnt.toggle_enabled()
                state = "ENABLED" if self._mnt._enabled else "PAUSED"
                print(f"  Trackball {state}")
            return
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
        print("  P - PAUSE/RESUME trackball")
        print("  Q - QUIT")
        print("  Trackball active if plugged in")
        print("=" * 50 + "\n")

        if not self.connection.connect():
            logger.error(f"Could not connect to robot at {config.ROBOT_IP}:{config.SERVER_PORT}")
            sys.exit(1)

        # Start keyboard backend
        keyboard = KeyboardBackend(on_command=self._on_command)
        keyboard.start()

        # Start MNT backend if available
        self._mnt  = MntMouseBackend(on_command=self._on_command)
        mnt_active = self._mnt.start()
        if mnt_active:
            logger.info("MNT trackball active")
        else:
            logger.info("MNT trackball not found — keyboard only")

        try:
            self._quit_event.wait()  # Block until Q is pressed
        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            keyboard.stop()
            if mnt_active:
                self._mnt.stop()
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
