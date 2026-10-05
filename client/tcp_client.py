"""
TCP Client Module - Handles connection creation, framed message sending/receiving,
and TCP stream socket communication with the Server.
"""

import socket
from shared.config import DEFAULT_HOST, TCP_PORT
from shared.protocol import ProtocolMessage, send_framed_msg, receive_framed_msg
from shared.utils import print_success, print_error, print_info


class TCPClient:
    """
    TCP Client class managing socket connection to the TCP Server.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = TCP_PORT):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.is_connected = False
        self._buffer = ""

    def connect(self) -> bool:
        """
        Creates AF_INET SOCK_STREAM socket and initiates TCP 3-way handshake with server.
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)  # 5 second timeout for connection
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)  # Reset blocking mode
            self.is_connected = True
            print_success(f"Connected to TCP Server at {self.host}:{self.port}")
            return True
        except (socket.error, ConnectionRefusedError) as e:
            print_error(f"Could not connect to TCP Server at {self.host}:{self.port} - {e}")
            self.is_connected = False
            self.sock = None
            return False

    def ping(self) -> ProtocolMessage | None:
        """Sends PING control message and waits for PONG response."""
        if not self.is_connected or not self.sock:
            print_error("TCP Client is not connected!")
            return None

        try:
            ping_msg = ProtocolMessage("PING")
            send_framed_msg(self.sock, ping_msg)
            print_info("Sent TCP PING header to server...", tag="TCP")

            resp, self._buffer = receive_framed_msg(self.sock, self._buffer)
            if resp:
                print_success(f"Received from Server: {resp.command} {' '.join(resp.args)}")
            return resp
        except socket.error as e:
            print_error(f"TCP communication error: {e}")
            self.disconnect()
            return None

    def disconnect(self) -> None:
        """Closes TCP connection gracefully."""
        if self.sock and self.is_connected:
            try:
                quit_msg = ProtocolMessage("QUIT")
                send_framed_msg(self.sock, quit_msg)
                self.sock.close()
            except Exception:
                pass
            self.is_connected = False
            self.sock = None
            print_info("Disconnected from TCP Server", tag="TCP")
