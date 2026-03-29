"""
Command Receiver Server (TCP)
============================
Receives commands from DEV PC via TCP socket.
Validates and queues commands for the brain to process.
"""

import socket
import threading
import logging
import time
from queue import Queue, Full
from typing import Optional

logger = logging.getLogger(__name__)


class CommandReceiverServer:
    """TCP server that receives commands from controller client."""

    # Valid commands
    VALID_COMMANDS = {"LEFT", "RIGHT", "SELECT", "STOP"}

    def __init__(self, host: str = "0.0.0.0", port: int = 5577, max_queue_size: int = 100):
        """
        Initialize command receiver server.
        
        Args:
            host: Bind to this host
            port: Listen on this port
            max_queue_size: Max commands in queue
        """
        self.host = host
        self.port = port
        self.max_queue_size = max_queue_size
        self.command_queue = Queue(maxsize=max_queue_size)
        self.server_socket = None
        self.running = False
        self.client_socket = None
        self.server_thread = None

    def start(self):
        """Start the TCP server."""
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        logger.info(f"Command server starting on {self.host}:{self.port}")

    def _run_server(self):
        """Main server loop (runs in thread)."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            logger.info(f"Server listening on {self.host}:{self.port}")

            while self.running:
                try:
                    # Accept connection with timeout
                    self.server_socket.settimeout(1.0)
                    self.client_socket, addr = self.server_socket.accept()
                    logger.info(f"Client connected from {addr}")
                    self._handle_client(self.client_socket, addr)
                except socket.timeout:
                    continue
                except OSError:
                    # Socket closed
                    break

        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.stop()

    def _handle_client(self, client_socket: socket.socket, addr: tuple):
        """
        Handle a client connection.
        Read commands until connection closes.
        """
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
                    # Process complete lines (commands end with newline)
                    lines = buffer.split("\n")
                    buffer = lines[-1]  # Keep incomplete line in buffer

                    for line in lines[:-1]:
                        command = line.strip().upper()
                        if command:
                            self._process_command(command)

                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Error communicating with client: {e}")
                    break

        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass
            self.client_socket = None
            logger.info(f"Client {addr} connection closed")

    def _process_command(self, command: str):
        """
        Process a received command.
        Validate and queue it.
        """
        command = command.strip().upper()

        if command not in self.VALID_COMMANDS:
            logger.warning(f"Invalid command received: {command}")
            return

        try:
            self.command_queue.put_nowait(command)
            logger.debug(f"Command queued: {command}")
        except Full:
            logger.warning(f"Command queue full, dropping: {command}")

    def get_command(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Get next command from queue.
        
        Args:
            timeout: Timeout in seconds (None = blocking)
        
        Returns:
            Command string or None if timeout/empty
        """
        try:
            return self.command_queue.get(timeout=timeout)
        except:
            return None

    def stop(self):
        """Stop the server."""
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        logger.info("Command server stopped")


# Singleton instance
_server = None


def get_command_server(host: str = "0.0.0.0", port: int = 5577) -> CommandReceiverServer:
    """Get or create the command server singleton."""
    global _server
    if _server is None:
        _server = CommandReceiverServer(host, port)
    return _server
