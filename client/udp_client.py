"""
UDP Client Module - Connectionless datagram socket client for UDP presence & heartbeat.
Operates on Port 6000/UDP. Launches background heartbeat sender thread (5s interval).
"""

import json
import socket
import threading
import time
from typing import Dict, Any, List, Optional
from shared.config import DEFAULT_HOST, UDP_PORT, MAX_UDP_PAYLOAD
from shared.utils import print_success, print_error, print_info, print_warning


class UDPClient:
    """
    UDP Client managing datagram sending, receiving, and presence heartbeat thread.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = UDP_PORT, username: str = "Keerthi"):
        self.host = host
        self.port = port
        self.username = username
        self.sock: socket.socket | None = None
        self.is_connected = False
        self.is_heartbeat_running = False
        self.heartbeat_thread: threading.Thread | None = None

    def connect(self) -> bool:
        """Creates AF_INET SOCK_DGRAM UDP IPv4 socket."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(3.0)  # 3s timeout for UDP responses
            self.is_connected = True
            print_success(f"UDP Socket initialized for {self.host}:{self.port}")
            return True
        except socket.error as e:
            print_error(f"Could not create UDP socket: {e}")
            self.is_connected = False
            return False

    def join_chat(self, username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Sends JOIN UDP datagram to server to register presence."""
        if username:
            self.username = username

        if not self.is_connected or not self.sock:
            if not self.connect():
                return None

        join_payload = {
            "type": "JOIN",
            "username": self.username
        }

        try:
            raw_bytes = json.dumps(join_payload).encode("utf-8")
            self.sock.sendto(raw_bytes, (self.host, self.port))

            data, addr = self.sock.recvfrom(MAX_UDP_PAYLOAD)
            response = json.loads(data.decode("utf-8"))

            if response and response.get("status") == "SUCCESS":
                print_success(f"UDP User '{self.username}' joined chat server successfully!")
                self.start_heartbeat()
                return response
            return None

        except (socket.timeout, socket.error) as e:
            print_warning(f"UDP JOIN request timeout/error: {e}")
            return None

    def start_heartbeat(self, interval: float = 5.0) -> None:
        """Launches background thread sending HEARTBEAT datagrams every 5 seconds."""
        if self.is_heartbeat_running:
            return

        self.is_heartbeat_running = True
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(interval,),
            daemon=True,
            name="UDPHeartbeatThread"
        )
        self.heartbeat_thread.start()
        print_info(f"UDP Presence Heartbeat thread started (Interval: {interval}s)", tag="UDP")

    def _heartbeat_loop(self, interval: float) -> None:
        """Loop running in daemon thread sending HEARTBEAT datagrams."""
        hb_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        hb_socket.settimeout(2.0)

        while self.is_heartbeat_running:
            try:
                hb_payload = {
                    "type": "HEARTBEAT",
                    "username": self.username
                }
                raw_bytes = json.dumps(hb_payload).encode("utf-8")
                hb_socket.sendto(raw_bytes, (self.host, self.port))

                # Receive HEARTBEAT_ACK
                try:
                    data, _ = hb_socket.recvfrom(MAX_UDP_PAYLOAD)
                except socket.timeout:
                    pass

            except Exception:
                pass

            time.sleep(interval)

        hb_socket.close()

    def get_online_users(self) -> List[Dict[str, Any]]:
        """Sends GET_USERS UDP datagram to fetch online user list."""
        if not self.is_connected or not self.sock:
            return []

        try:
            req = {"type": "GET_USERS", "username": self.username}
            self.sock.sendto(json.dumps(req).encode("utf-8"), (self.host, self.port))
            data, _ = self.sock.recvfrom(MAX_UDP_PAYLOAD)
            resp = json.loads(data.decode("utf-8"))
            return resp.get("users", [])
        except Exception:
            return []

    def stop_heartbeat(self) -> None:
        """Stops background heartbeat loop."""
        self.is_heartbeat_running = False

    def leave_chat(self) -> None:
        """Sends LEAVE UDP datagram and stops heartbeat."""
        self.stop_heartbeat()
        if self.sock and self.is_connected:
            try:
                leave_req = {"type": "LEAVE", "username": self.username}
                self.sock.sendto(json.dumps(leave_req).encode("utf-8"), (self.host, self.port))
                self.sock.close()
            except Exception:
                pass
        self.is_connected = False
        self.sock = None
        print_info("Left UDP Chat & Presence", tag="UDP")
