"""
Client Controller - Manages real Python TCP and UDP Socket Clients for the Product UI.
Maintains state, TCP/UDP connection status, real transfer history, live chat messages, online user registry, and activity logs.
"""

import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from shared.config import DEFAULT_HOST, TCP_PORT, UDP_PORT, DOWNLOADS_DIR, UPLOADS_DIR
from shared.utils import get_timestamp
from client.tcp_client import TCPClient
from client.udp_client import UDPClient


class ClientController:
    """
    Controller singleton bridging the Product Web Interface to actual Python TCP and UDP sockets.
    Triggers real socket methods on TCPClient & UDPClient.
    """

    def __init__(self):
        self.server_host = DEFAULT_HOST
        self.tcp_port = TCP_PORT
        self.udp_port = UDP_PORT
        self.username = "Keerthi"

        self.tcp_client: TCPClient | None = None
        self.udp_client: UDPClient | None = None

        self.is_connected = False
        self.tcp_connected = False
        self.udp_connected = False
        self.simulated_loss_rate = 0.0

        self.activity_logs: List[Dict[str, str]] = []
        self.transfer_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        self._add_log("INFO", "Application initialized in Product Mode")

    def set_simulated_loss(self, rate: float) -> Dict[str, Any]:
        """Sets simulated UDP packet loss percentage (0.0 to 0.5)."""
        valid_rate = max(0.0, min(0.5, float(rate)))
        self.simulated_loss_rate = valid_rate
        if self.udp_client:
            self.udp_client.set_simulated_loss_rate(valid_rate)
        pct = valid_rate * 100.0
        self._add_log("WARN" if valid_rate > 0 else "INFO", f"Simulated UDP Packet Loss set to {pct:.1f}%")
        return {"success": True, "simulated_loss_rate": valid_rate, "loss_percentage": pct}

    def _add_log(self, level: str, message: str) -> None:
        with self._lock:
            log_entry = {
                "timestamp": get_timestamp(),
                "level": level.upper(),
                "message": message
            }
            self.activity_logs.append(log_entry)
            if len(self.activity_logs) > 100:
                self.activity_logs.pop(0)

    def connect(self, host: str, tcp_port: int, udp_port: int, username: str) -> Dict[str, Any]:
        """Connects to the server using REAL Python TCP and UDP sockets."""
        self.server_host = host.strip() or DEFAULT_HOST
        self.tcp_port = int(tcp_port)
        self.udp_port = int(udp_port)
        self.username = username.strip() or "Keerthi"

        self._add_log("TCP", f"Initiating TCP connection to {self.server_host}:{self.tcp_port}...")

        # Step 1: Connect TCP Socket
        self.tcp_client = TCPClient(host=self.server_host, port=self.tcp_port)
        tcp_ok = self.tcp_client.connect()

        if tcp_ok:
            resp = self.tcp_client.send_hello(client_name=self.username)
            if resp and resp.get("status") == "SUCCESS":
                self.tcp_connected = True
                self.is_connected = True
                self._add_log("SUCCESS", f"TCP Connection Established! Server ACK: {resp.get('message')}")
            else:
                self.tcp_client.disconnect()
                self._add_log("ERROR", "TCP Handshake failed")
                return {"success": False, "error": "TCP Server handshake failed"}
        else:
            self._add_log("ERROR", f"Could not connect to TCP {self.server_host}:{self.tcp_port}")
            return {"success": False, "error": f"Failed to connect to TCP Server at {self.server_host}:{self.tcp_port}"}

        # Step 2: Connect & Join UDP Socket
        self._add_log("UDP", f"Initiating UDP socket for {self.server_host}:{self.udp_port}...")
        self.udp_client = UDPClient(host=self.server_host, port=self.udp_port, username=self.username)
        if self.udp_client.connect():
            udp_resp = self.udp_client.join_chat(self.username)
            if udp_resp:
                self.udp_connected = True
                self._add_log("SUCCESS", "UDP Chat & Presence Joined! Started 5s Heartbeat Thread.")
            else:
                self._add_log("WARN", "UDP Join request timed out")

        return {
            "success": True,
            "message": "Connected to HYBRID TRANSFER Server",
            "server_host": self.server_host,
            "tcp_port": self.tcp_port,
            "udp_port": self.udp_port,
            "username": self.username,
            "tcp_connected": self.tcp_connected,
            "udp_connected": self.udp_connected
        }

    def list_files(self) -> List[Dict[str, Any]]:
        """Lists files available on server over TCP socket."""
        if not self.tcp_connected or not self.tcp_client:
            return []
        files = self.tcp_client.list_files() or []
        self._add_log("TCP", f"Fetched file repository list: {len(files)} files found")
        return files

    def upload_file(self, filepath: str, resume: bool = False) -> Dict[str, Any]:
        """Performs streaming TCP file upload to server."""
        if not self.tcp_connected or not self.tcp_client:
            return {"success": False, "error": "Not connected to TCP server"}

        mode_str = "RESUME Upload" if resume else "Upload"
        self._add_log("TCP", f"Starting TCP {mode_str} for '{filepath}'...")
        res = self.tcp_client.upload_file(filepath, resume=resume)

        record = {
            "timestamp": get_timestamp(),
            "filename": res.get("filename", filepath),
            "direction": "Upload (Resumed)" if resume else "Upload",
            "protocol": "TCP",
            "size": res.get("filesize", 0),
            "offset_resumed": res.get("offset_resumed", 0),
            "status": "Completed" if res.get("success") else "Failed",
            "checksum_verified": res.get("checksum_verified", False)
        }
        with self._lock:
            self.transfer_history.insert(0, record)

        if res.get("success"):
            self._add_log("SUCCESS", f"Upload completed & SHA-256 verified for '{record['filename']}'")
        else:
            self._add_log("ERROR", f"Upload failed for '{record['filename']}': {res.get('error')}")

        return res

    def download_file(self, filename: str, resume: bool = False) -> Dict[str, Any]:
        """Performs streaming TCP file download from server."""
        if not self.tcp_connected or not self.tcp_client:
            return {"success": False, "error": "Not connected to TCP server"}

        mode_str = "RESUME Download" if resume else "Download"
        self._add_log("TCP", f"Starting TCP {mode_str} for '{filename}'...")
        res = self.tcp_client.download_file(filename, resume=resume)

        record = {
            "timestamp": get_timestamp(),
            "filename": filename,
            "direction": "Download (Resumed)" if resume else "Download",
            "protocol": "TCP",
            "size": res.get("filesize", 0),
            "offset_resumed": res.get("offset_resumed", 0),
            "status": "Completed" if res.get("success") else "Failed",
            "checksum_verified": res.get("checksum_verified", False)
        }
        with self._lock:
            self.transfer_history.insert(0, record)

        if res.get("success"):
            self._add_log("SUCCESS", f"Download completed & SHA-256 verified for '{filename}'")
        else:
            self._add_log("ERROR", f"Download failed for '{filename}': {res.get('error')}")

        return res

    def send_chat_message(self, message: str) -> Dict[str, Any]:
        """Sends UDP MSG datagram to server."""
        if not self.udp_connected or not self.udp_client:
            return {"success": False, "error": "Not connected to UDP server"}

        res = self.udp_client.send_chat_message(message)
        if res.get("success"):
            self._add_log("UDP", f"Sent UDP Chat Message [seq={res.get('sequence')}]: '{message}'")
        return res

    def get_chat_history(self) -> List[Dict[str, Any]]:
        """Returns received chat messages."""
        if self.udp_client:
            return self.udp_client.get_chat_history()
        return []

    def get_online_users(self) -> List[Dict[str, Any]]:
        """Returns list of online users from UDP server presence registry."""
        if self.udp_client and self.udp_connected:
            users = self.udp_client.get_online_users()
            if users:
                return users
        return [{"username": self.username, "endpoint": "127.0.0.1", "status": "ONLINE", "last_seen": get_timestamp()}]

    def list_partial_files(self) -> List[Dict[str, Any]]:
        """Lists partial .part files available for transfer resume."""
        partials = []
        if DOWNLOADS_DIR.exists():
            for item in DOWNLOADS_DIR.iterdir():
                if item.is_file() and item.name.endswith(".part"):
                    clean_name = item.name[:-5]
                    partials.append({
                        "filename": clean_name,
                        "type": "Download",
                        "bytes_received": item.stat().st_size,
                        "part_path": str(item)
                    })
        return partials

    def get_transfers(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.transfer_history)

    def disconnect(self) -> Dict[str, Any]:
        """Closes TCP and UDP sockets cleanly."""
        if self.tcp_client:
            self.tcp_client.disconnect()
            self.tcp_client = None

        if self.udp_client:
            self.udp_client.leave_chat()
            self.udp_client = None

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
            "udp_connected": self.udp_connected and (self.udp_client.is_connected if self.udp_client else False),
            "server_host": self.server_host,
            "tcp_port": self.tcp_port,
            "udp_port": self.udp_port,
            "username": self.username
        }

    def get_activity_logs(self) -> List[Dict[str, str]]:
        with self._lock:
            return list(self.activity_logs)

    def get_network_stats(self) -> Dict[str, Any]:
        """Returns live network stats summary (throughput, latency RTT, packets, reliability)."""
        from shared.stats import global_stats
        return global_stats.get_summary()


# Singleton instance
controller = ClientController()
