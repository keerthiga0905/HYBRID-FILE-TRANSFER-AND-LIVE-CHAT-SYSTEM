"""
Client Controller - Manages real Python TCP and UDP Socket Clients for the Product UI.
Maintains state, connection status, real runtime statistics, and activity logs.
"""

import threading
import time
from typing import Dict, Any, List
from shared.config import DEFAULT_HOST, TCP_PORT, UDP_PORT
from shared.utils import get_timestamp
from client.tcp_client import TCPClient


class ClientController:
    """
    Controller singleton bridging the Product Web Interface to actual Python TCP/UDP sockets.
    Does NOT mock networking: triggers real socket methods on TCPClient & UDPClient.
    """

    def __init__(self):
        self.server_host = DEFAULT_HOST
        self.tcp_port = TCP_PORT
        self.udp_port = UDP_PORT
        self.username = "Keerthi"

        self.tcp_client: TCPClient | None = None
        self.is_connected = False
        self.tcp_connected = False
        self.udp_connected = False

        self.activity_logs: List[Dict[str, str]] = []
        self._lock = threading.Lock()

        # Initial log
        self._add_log("INFO", "Application initialized in Product Mode")

    def _add_log(self, level: str, message: str) -> None:
        with self._lock:
            log_entry = {
                "timestamp": get_timestamp(),
                "level": level.upper(),
                "message": message
            }
            self.activity_logs.append(log_entry)
            # Keep last 100 log entries
            if len(self.activity_logs) > 100:
                self.activity_logs.pop(0)

    def connect(self, host: str, tcp_port: int, udp_port: int, username: str) -> Dict[str, Any]:
        """
        Connects to the server using REAL Python TCP socket.
        """
        self.server_host = host.strip() or DEFAULT_HOST
        self.tcp_port = int(tcp_port)
        self.udp_port = int(udp_port)
        self.username = username.strip() or "Keerthi"

        self._add_log("TCP", f"Initiating TCP connection to {self.server_host}:{self.tcp_port}...")

        # Create real TCP client instance
        self.tcp_client = TCPClient(host=self.server_host, port=self.tcp_port)
        connected = self.tcp_client.connect()

        if connected:
            # Perform HELLO handshake over real TCP socket
            resp = self.tcp_client.send_hello(client_name=self.username)
            if resp and resp.get("status") == "SUCCESS":
                self.tcp_connected = True
                self.is_connected = True
                self._add_log("SUCCESS", f"TCP Connection Established! Server ACK: {resp.get('message')}")
                return {
                    "success": True,
                    "message": "Connected to HYBRID TRANSFER Server",
                    "server_host": self.server_host,
                    "tcp_port": self.tcp_port,
                    "udp_port": self.udp_port,
                    "username": self.username,
                    "tcp_connected": True,
                    "udp_connected": False
                }
            else:
                self.tcp_client.disconnect()
                self._add_log("ERROR", "Handshake failed or unexpected response from server")
                return {"success": False, "error": "Server handshake failed"}
        else:
            self._add_log("ERROR", f"Could not connect to {self.server_host}:{self.tcp_port}")
            return {"success": False, "error": f"Failed to connect to {self.server_host}:{self.tcp_port}"}

    def disconnect(self) -> Dict[str, Any]:
        """Closes TCP and UDP connections cleanly."""
        if self.tcp_client:
            self.tcp_client.disconnect()
            self.tcp_client = None

        self.tcp_connected = False
        self.udp_connected = False
        self.is_connected = False
        self._add_log("INFO", "Disconnected from server")
        return {"success": True, "message": "Disconnected cleanly"}

    def get_status(self) -> Dict[str, Any]:
        """Returns real connection state."""
        return {
            "is_connected": self.is_connected,
            "tcp_connected": self.tcp_connected and (self.tcp_client.is_connected if self.tcp_client else False),
            "udp_connected": self.udp_connected,
            "server_host": self.server_host,
            "tcp_port": self.tcp_port,
            "udp_port": self.udp_port,
            "username": self.username
        }

    def get_activity_logs(self) -> List[Dict[str, str]]:

        with self._lock:
            return list(self.activity_logs)


# Singleton instance
controller = ClientController()
