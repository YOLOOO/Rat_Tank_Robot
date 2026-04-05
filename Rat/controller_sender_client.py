"""
Controller Sender Client (DEV PC)
==================================
Sends commands to the robot via TCP.

Input backends:
    KeyboardBackend  — raw single-keypress, no Enter needed (menu navigation)
    MntMouseBackend  — MNT Reform trackball for remote_control mission

Controls (keyboard):
    A - LEFT
    D - RIGHT
    S - SELECT
    H - HALT
    Q - QUIT

Controls (MNT trackball, active during remote_control mission):
    Ball             → differential motor control
    Left button      → ARM toggle
    Right button     → GRIP toggle
    Middle button    → HALT
"""

import socket
import sys
import logging
import tty
import termios
from typing import Optional

from mnt_backend import MntMouseBackend

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

CMD_LEFT   = "LEFT"
CMD_RIGHT  = "RIGHT"
CMD_SELECT = "SELECT"
CMD_HALT   = "HALT"
CMD_QUIT   = "QUIT"


# ------------------------------------------------------------------
# Keyboard backend (menu navigation)
# ------------------------------------------------------------------

class KeyboardBackend:
    """Raw single-keypress — no Enter required."""

    KEY_MAP = {
        'a': CMD_LEFT,
        'd': CMD_RIGHT,
        's': CMD_SELECT,
        'h': CMD_HALT,
        'q': CMD_QUIT,
    }

    def read_command(self) -> Optional[str]:
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            key = sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return self.KEY_MAP.get(key, None)

    def cleanup(self):
        pass


# ------------------------------------------------------------------
# TCP connection
# ------------------------------------------------------------------

class RobotConnection:
    """Manages TCP connection to the robot with auto-reconnect."""

    def __init__(self, host: str, port: int):
        self.host      = host
        self.port      = port
        self.socket    = None
        self.connected = False

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
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.connected = False
        logger.info("Disconnected")


# ------------------------------------------------------------------
# Controller
# ------------------------------------------------------------------

class RobotController:
    """
    Two modes:
        keyboard  — menu navigation via KeyboardBackend
        mnt       — remote_control mission via MntMouseBackend
    """

    def __init__(self, host: str, port: int, mode: str = "keyboard"):
        self.connection = RobotConnection(host, port)
        self.mode       = mode

    def run(self):
        print("\n" + "=" * 50)
        print("  RAT OS — CONTROLLER")
        print("=" * 50)

        if self.mode == "mnt":
            self._run_mnt()
        else:
            self._run_keyboard()

    # --- Keyboard mode ---

    def _run_keyboard(self):
        print("  A - LEFT    D - RIGHT")
        print("  S - SELECT  H - HALT")
        print("  Q - QUIT")
        print("=" * 50 + "\n")

        if not self.connection.connect():
            logger.error("Could not connect to robot.")
            sys.exit(1)

        backend = KeyboardBackend()
        try:
            while True:
                command = backend.read_command()
                if command is None:
                    continue
                if command == CMD_QUIT:
                    print("\nQuitting...")
                    break
                self.connection.ensure_connected()
                self.connection.send(command)
                if command == CMD_HALT:
                    print("  !! HALT sent !!")
        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            backend.cleanup()
            self.connection.disconnect()
            print("Controller stopped.")

    # --- MNT trackball mode ---

    def _run_mnt(self):
        print("  Ball         → drive")
        print("  Left button  → arm toggle")
        print("  Right button → grip toggle")
        print("  Middle       → HALT")
        print("  Ctrl+C       → quit")
        print("=" * 50 + "\n")

        if not self.connection.connect():
            logger.error("Could not connect to robot.")
            sys.exit(1)

        backend = MntMouseBackend()
        if not backend.start():
            logger.error("Failed to start MNT backend. Is the trackball plugged in?")
            sys.exit(1)

        try:
            while True:
                command = backend.get_command()
                if command is None:
                    continue
                self.connection.ensure_connected()
                self.connection.send(command)
                if command == CMD_HALT:
                    print("  !! HALT sent !!")
        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            backend.stop()
            self.connection.disconnect()
            print("Controller stopped.")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Rat OS Controller")
    parser.add_argument("--host",  default="localhost", help="Robot IP address")
    parser.add_argument("--port",  type=int, default=5577, help="Robot port")
    parser.add_argument(
        "--input", choices=["keyboard", "mnt"], default="keyboard",
        help="Input backend (default: keyboard)"
    )
    args = parser.parse_args()

    controller = RobotController(host=args.host, port=args.port, mode=args.input)
    controller.run()


if __name__ == "__main__":
    main()

