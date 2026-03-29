"""
Controller Sender Client (DEV PC)
================================
Sends commands to robot from DEV PC.
Reads keyboard input (a/d/s) and sends commands via TCP.
Later: replace with MNT mouse ball input.
"""

import socket
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class RobotController:
    """Client that sends commands to robot via TCP."""

    # Input mapping (keyboard)
    INPUT_MAP = {
        'a': 'LEFT',
        'd': 'RIGHT',
        's': 'SELECT',
        'q': 'QUIT',
    }

    def __init__(self, host: str = "localhost", port: int = 5577):
        """
        Initialize controller.
        
        Args:
            host: Robot IP address
            port: Robot server port
        """
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to robot server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            logger.info(f"Connected to robot at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False

    def send_command(self, command: str) -> bool:
        """
        Send command to robot.
        
        Args:
            command: Command string (LEFT, RIGHT, SELECT)
        
        Returns:
            True if sent successfully
        """
        if not self.connected:
            logger.warning("Not connected to robot")
            return False

        try:
            # Commands are newline-delimited
            self.socket.send(f"{command}\n".encode('utf-8'))
            logger.debug(f"Sent: {command}")
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self.connected = False
            return False

    def reconnect_if_needed(self):
        """Try to reconnect if connection dropped."""
        if not self.connected:
            logger.info("Attempting to reconnect...")
            self.connect()

    def disconnect(self):
        """Disconnect from robot."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        logger.info("Disconnected from robot")

    def run(self):
        """Main control loop - read keyboard and send commands."""
        print("\n" + "="*50)
        print("RAT TANK ROBOT CONTROLLER")
        print("="*50)
        print("\nControls:")
        print("  A  - LEFT (previous item)")
        print("  D  - RIGHT (next item)")
        print("  S  - SELECT (run behavior)")
        print("  Q  - QUIT")
        print("\n" + "="*50 + "\n")

        if not self.connect():
            logger.error("Failed to connect to robot. Check IP and port.")
            sys.exit(1)

        try:
            while True:
                # Read keyboard input
                try:
                    key = input("Command: ").lower().strip()
                except EOFError:
                    # Piped input or stream ended
                    break

                if not key:
                    continue

                if key == 'q':
                    print("Quitting...")
                    break

                if key in self.INPUT_MAP:
                    command = self.INPUT_MAP[key]
                    self.reconnect_if_needed()
                    self.send_command(command)
                else:
                    print(f"Unknown command: {key}")
                    print("Valid commands: a(left), d(right), s(select), q(quit)")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            self.disconnect()
            print("\nController stopped.")


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="RAT Brain Robot Controller"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Robot IP address (default: localhost for local testing)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5577,
        help="Robot server port (default: 5577)"
    )

    args = parser.parse_args()

    controller = RobotController(host=args.host, port=args.port)
    controller.run()


if __name__ == "__main__":
    main()
