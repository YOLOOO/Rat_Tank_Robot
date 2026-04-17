"""
Command Receiver Server (TCP)
============================
Receives commands from DEV PC via TCP socket.
Validates and queues commands for the brain to process.

HALT is special — it bypasses the queue and sets a flag directly
so it can never be blocked by a full queue or slow brain loop.
"""

import socket
import threading
import logging
from queue import Queue, Full
from typing import Optional

import config

logger = logging.getLogger(__name__)

VALID_COMMANDS = {
    "LEFT", "RIGHT", "SELECT", "HALT",
    # remote_control mission commands
    "ARM_TOGGLE", "GRIP_TOGGLE",
    # MOTOR:left:right is validated separately due to dynamic values
}


class CommandReceiverServer:
    """TCP server that receives commands from the controller client."""

    def __init__(self):
        self.host          = config.SERVER_HOST
        self.port          = config.SERVER_PORT
        self.command_queue = Queue(maxsize=config.MAX_COMMAND_QUEUE_SIZE)
        self.halt_flag     = False  # Set immediately on HALT, never queued

        self.server_socket = None
        self.client_socket = None
        self.server_thread = None
        self.running       = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        if self.running:
            logger.warning("Command server already running")
            return

        self.running      = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        logger.info(f"Command server starting on {self.host}:{self.port}")

    def stop(self):
        self.running = False

        for sock in (self.client_socket, self.server_socket):
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

        self.client_socket = None
        self.server_socket = None
        logger.info("Command server stopped")

    # ------------------------------------------------------------------
    # Server loop
    # ------------------------------------------------------------------

    def _run_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)
            logger.info(f"Listening on {self.host}:{self.port}")

            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    self.client_socket = client_socket
                    logger.info(f"Client connected: {addr}")
                    self._handle_client(client_socket, addr)
                except socket.timeout:
                    continue
                except OSError as e:
                    if self.running:
                        logger.error(f"Accept error: {e}")
                    break

        except OSError as e:
            logger.error(f"Server bind error on {self.host}:{self.port}: {e}")
        except Exception as e:
            logger.exception(f"Server error: {e}")
        finally:
            self.stop()

    def _handle_client(self, client_socket: socket.socket, addr: tuple):
        buffer = ""
        try:
            client_socket.settimeout(0.5)
            while self.running:
                try:
                    data = client_socket.recv(1024).decode("utf-8")
                    if not data:
                        logger.info(f"Client {addr} disconnected")
                        break

                    buffer += data
                    lines  = buffer.split("\n")
                    buffer = lines[-1]

                    for line in lines[:-1]:
                        command = line.strip().upper()
                        if command:
                            self._process_command(command)

                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Client read error: {e}")
                    break
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
            self.client_socket = None
            logger.info(f"Client {addr} closed")

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    def _process_command(self, command: str):
        command = command.strip().upper()

        # HALT bypasses the queue — set flag immediately
        if command == "HALT":
            self.halt_flag = True
            logger.warning("HALT received")
            return

        # MOTOR:left:right — validate structure and values
        if command.startswith("MOTOR:"):
            parts = command.split(":")
            if len(parts) == 3:
                try:
                    int(parts[1])
                    int(parts[2])
                except ValueError:
                    logger.warning(f"Malformed MOTOR command: {command}")
                    return
            else:
                logger.warning(f"Malformed MOTOR command: {command}")
                return

        # SERVO:channel:delta — validate structure and values
        elif command.startswith("SERVO:"):
            parts = command.split(":")
            if len(parts) == 3:
                try:
                    int(parts[1])
                    int(parts[2])
                except ValueError:
                    logger.warning(f"Malformed SERVO command: {command}")
                    return
            else:
                logger.warning(f"Malformed SERVO command: {command}")
                return

        elif command not in VALID_COMMANDS:
            logger.warning(f"Unknown command: {command}")
            return

        try:
            self.command_queue.put_nowait(command)
            logger.debug(f"Queued: {command}")
        except Full:
            # For MOTOR commands during remote control, silently drop rather
            # than log — at 30Hz drops are expected under load
            if not command.startswith("MOTOR:"):
                logger.warning(f"Queue full, dropping: {command}")

    def get_command(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Get next command. Brain should check halt_flag separately and first.
        Returns None on timeout or empty queue.
        """
        try:
            return self.command_queue.get(timeout=timeout)
        except Exception:
            return None

    def clear_halt(self):
        """Reset halt flag after the brain has processed it."""
        self.halt_flag = False


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_server: Optional[CommandReceiverServer] = None


def get_command_server() -> CommandReceiverServer:
    global _server
    if _server is None:
        _server = CommandReceiverServer()
        logger.info(f"Created command server singleton id={id(_server)}")
    else:
        logger.info(f"Reusing command server singleton id={id(_server)}")
    return _server
