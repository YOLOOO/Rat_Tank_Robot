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
import time
import logging
from queue import Queue, Full
from typing import Optional

import config

logger = logging.getLogger(__name__)

VALID_COMMANDS = {
    "LEFT", "RIGHT", "SELECT", "HALT",
    # remote_control mission commands
    "ARM_TOGGLE", "GRIP_TOGGLE",
    # AI_controlled mission commands
    "AI_CMD:FORWARD", "AI_CMD:BACKWARD", "AI_CMD:SPIN_LEFT", "AI_CMD:SPIN_RIGHT",
    "AI_CMD:STOP", "AI_CMD:ARM_UP", "AI_CMD:ARM_DOWN",
    "AI_CMD:GRIP_OPEN", "AI_CMD:GRIP_CLOSE", "AI_CMD:SNAPSHOT",
    # MOTOR:left:right, SERVO:ch:delta, AI_CMD:FORWARD:slow etc. are
    # validated separately due to dynamic/variable-length values
}

# How long a connected client can go without sending anything before the
# server gives up on it and frees the slot for a new connection. Without
# this, a connection that dies without a clean TCP close (WiFi drop, NAT/
# router hiccup, laptop sleep) never triggers recv()'s "disconnected" path —
# it just keeps timing out and looping forever.
CLIENT_IDLE_TIMEOUT = 15.0


class CommandReceiverServer:
    """TCP server that receives commands from the controller client."""

    def __init__(self):
        self.host          = config.SERVER_HOST
        self.port          = config.SERVER_PORT
        self.command_queue = Queue(maxsize=config.MAX_COMMAND_QUEUE_SIZE)
        self.halt_flag     = False  # Set immediately on HALT, never queued

        self.server_socket  = None
        self.client_socket  = None
        self.client_address = None  # IP of the current controller — missions that
                                     # need to open their own outbound connection
                                     # back to the controller (e.g. AI telemetry)
                                     # read this instead of hardcoding an address.
        self.server_thread  = None
        self.running        = False

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
            self.server_socket.listen(2)
            self.server_socket.settimeout(1.0)
            logger.info(f"Listening on {self.host}:{self.port}")

            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    logger.info(f"Client connected: {addr}")

                    # Only one controller is authoritative at a time. If a
                    # previous connection is still around — most likely a
                    # zombie that never sent a clean disconnect — evict it
                    # immediately instead of leaving two sockets alive.
                    old_socket = self.client_socket
                    self.client_socket  = client_socket
                    self.client_address = addr[0]
                    if old_socket is not None:
                        try:
                            old_socket.close()
                        except Exception:
                            pass

                    # Handled on its own thread so a stuck/zombie client can
                    # never block this loop from accepting the next
                    # connection — previously accept() wasn't reached again
                    # until the current client fully timed out or errored,
                    # which a connection that dies without a clean TCP close
                    # (WiFi drop, NAT hiccup, sleep/wake) never triggers.
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True,
                    ).start()

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
        buffer     = ""
        last_data  = time.time()
        try:
            client_socket.settimeout(0.5)
            while self.running and self.client_socket is client_socket:
                try:
                    data = client_socket.recv(1024).decode("utf-8")
                    if not data:
                        logger.info(f"Client {addr} disconnected")
                        break

                    last_data = time.time()
                    buffer += data
                    lines  = buffer.split("\n")
                    buffer = lines[-1]

                    for line in lines[:-1]:
                        command = line.strip().upper()
                        if command:
                            self._process_command(command)

                except socket.timeout:
                    if time.time() - last_data > CLIENT_IDLE_TIMEOUT:
                        logger.warning(f"Client {addr} idle for {CLIENT_IDLE_TIMEOUT}s — dropping")
                        break
                    continue
                except Exception as e:
                    logger.error(f"Client read error: {e}")
                    break
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
            # Don't clobber a newer connection's slot if we were already
            # evicted by _run_server before this thread noticed.
            if self.client_socket is client_socket:
                self.client_socket  = None
                self.client_address = None
            logger.info(f"Client {addr} closed")

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    def _validate_two_int_command(self, command: str) -> bool:
        """Return True if command has the form PREFIX:int:int."""
        parts = command.split(":")
        if len(parts) != 3:
            logger.warning(f"Malformed command: {command}")
            return False
        try:
            int(parts[1])
            int(parts[2])
            return True
        except ValueError:
            logger.warning(f"Malformed command: {command}")
            return False

    def _validate_ai_cmd(self, command: str) -> bool:
        """AI_CMD: has several shapes — plain, :SLOW/:FAST (motor) or
        :SLOW/:MID/:FAST (servo) modifier, CURVE:left:right with two ints,
        or GOAL:dist_cm:ir:tolerance_cm:max_duration_s with four numbers.
        Simple keyword commands are checked against VALID_COMMANDS; the
        rest are validated here."""
        parts = command.split(":")

        if len(parts) == 3 and parts[1] in ("FORWARD", "BACKWARD") and parts[2] in ("SLOW", "FAST"):
            return True

        if len(parts) == 3 and parts[1] in ("ARM_UP", "ARM_DOWN", "GRIP_OPEN", "GRIP_CLOSE") \
                and parts[2] in ("SLOW", "MID", "FAST"):
            return True

        if len(parts) == 4 and parts[1] == "CURVE":
            try:
                int(parts[2])
                int(parts[3])
                return True
            except ValueError:
                pass

        if len(parts) == 6 and parts[1] == "GOAL":
            try:
                float(parts[2])  # dist_cm (-1 = no goal)
                int(parts[3])    # ir (-1 = no goal, else 0-7 bitmask)
                float(parts[4])  # tolerance_cm
                float(parts[5])  # max_duration_s (<=0 = disabled)
                return True
            except ValueError:
                pass

        logger.warning(f"Malformed command: {command}")
        return False

    def _process_command(self, command: str):
        command = command.strip().upper()

        # HALT bypasses the queue — set flag immediately
        if command == "HALT":
            self.halt_flag = True
            logger.warning("HALT received")
            return

        if command.startswith("MOTOR:") or command.startswith("SERVO:"):
            if not self._validate_two_int_command(command):
                return

        elif command.startswith("AI_CMD:"):
            if command not in VALID_COMMANDS and not self._validate_ai_cmd(command):
                return

        elif command not in VALID_COMMANDS:
            logger.warning(f"Unknown command: {command}")
            return

        try:
            self.command_queue.put_nowait(command)
            logger.debug(f"Queued: {command}")
        except Full:
            # MOTOR and SERVO are high-frequency streams — silently drop when full
            if not command.startswith("MOTOR:") and not command.startswith("SERVO:"):
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
