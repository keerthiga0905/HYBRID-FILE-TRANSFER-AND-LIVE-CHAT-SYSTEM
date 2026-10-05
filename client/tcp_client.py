"""
TCP Client Module - Handles connection creation, framed message sending/receiving,
and TCP stream socket communication with the Server.
"""

import socket
from typing import Dict, Any, Optional
from shared.config import DEFAULT_HOST, TCP_PORT
from shared.protocol import send_message, receive_message
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

    def connect(self) -> bool:
        """
        Creates AF_INET SOCK_STREAM IPv4 TCP socket and initiates 3-way handshake with server.
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)  # Reset to blocking mode
            self.is_connected = True
            print_success("TCP CONNECTION ESTABLISHED")
            return True
        except (socket.error, ConnectionRefusedError) as e:
            print_error(f"Could not connect to TCP Server at {self.host}:{self.port} - {e}")
            self.is_connected = False
            self.sock = None
            return False

    def send_hello(self, client_name: str = "Client") -> Optional[Dict[str, Any]]:
        """Sends HELLO command JSON message to server and receives framed response."""
        if not self.is_connected or not self.sock:
            print_error("TCP Client is not connected!")
            return None

        hello_request = {
            "command": "HELLO",
            "client_name": client_name
        }

        try:
            send_message(self.sock, hello_request)
            resp = receive_message(self.sock)
            if resp:
                print_info("Server response:", tag="Server")
                if resp.get("status") == "SUCCESS":
                    print_success(f"HELLO received")
                    print_success(f"{resp.get('message', 'Connection is working')}")
            return resp
        except (socket.error, ValueError) as e:
            print_error(f"TCP communication error: {e}")
            self.disconnect()
            return None

    def disconnect(self) -> None:
        """Closes TCP connection gracefully."""
        if self.sock and self.is_connected:
            try:
                quit_request = {"command": "QUIT"}
                send_message(self.sock, quit_request)
                self.sock.close()
            except Exception:
                pass
            self.is_connected = False
            self.sock = None
            print_info("Disconnected from TCP Server", tag="TCP")
