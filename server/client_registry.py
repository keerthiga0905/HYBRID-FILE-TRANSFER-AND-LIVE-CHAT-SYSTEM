"""
Client Registry Module - Thread-safe tracking of online/offline UDP client presence,
endpoints (IP/Port), and heartbeat timestamps.
"""

import time
import threading
from typing import Dict, List, Any, Optional
from shared.utils import get_timestamp
from server.logger import log_event


class ClientRegistry:
    """
    Thread-safe registry for managing active UDP clients and presence status.
    """

    def __init__(self, offline_timeout: float = 15.0):
        self.offline_timeout = offline_timeout
        self.clients: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register_client(self, username: str, ip: str, port: int) -> Dict[str, Any]:
        """Registers a user or updates endpoint and sets status to ONLINE."""
        username = username.strip()
        with self._lock:
            client_data = {
                "username": username,
                "ip": ip,
                "port": port,
                "endpoint": f"{ip}:{port}",
                "last_seen": time.time(),
                "last_seen_fmt": get_timestamp(),
                "status": "ONLINE"
            }
            self.clients[username] = client_data
            log_event(f"UDP Client Registered: {username} at {ip}:{port}")
            return client_data

    def update_heartbeat(self, username: str, ip: str, port: int) -> bool:
        """Updates last_seen timestamp for client heartbeat."""
        username = username.strip()
        with self._lock:
            if username in self.clients:
                self.clients[username]["last_seen"] = time.time()
                self.clients[username]["last_seen_fmt"] = get_timestamp()
                self.clients[username]["ip"] = ip
                self.clients[username]["port"] = port
                self.clients[username]["endpoint"] = f"{ip}:{port}"
                self.clients[username]["status"] = "ONLINE"
                return True
            else:
                # Auto register if not in registry
                self.clients[username] = {
                    "username": username,
                    "ip": ip,
                    "port": port,
                    "endpoint": f"{ip}:{port}",
                    "last_seen": time.time(),
                    "last_seen_fmt": get_timestamp(),
                    "status": "ONLINE"
                }
                return True

    def mark_offline(self, username: str) -> None:
        """Explicitly marks user OFFLINE."""
        with self._lock:
            if username in self.clients:
                self.clients[username]["status"] = "OFFLINE"
                log_event(f"User marked OFFLINE: {username}")

    def check_timeouts(self) -> List[str]:

        """
        Iterates clients and marks OFFLINE any client whose last_seen exceeds offline_timeout.
        Returns list of newly timed-out usernames.
        """
        now = time.time()
        newly_offline = []
        with self._lock:
            for username, data in self.clients.items():
                if data["status"] == "ONLINE" and (now - data["last_seen"]) > self.offline_timeout:
                    data["status"] = "OFFLINE"
                    newly_offline.append(username)
                    log_event(f"Presence Timeout: User '{username}' marked OFFLINE (No heartbeat for {self.offline_timeout}s)")
        return newly_offline

    def get_users_list(self) -> List[Dict[str, Any]]:
        """Returns list of registered users with online/offline status."""
        with self._lock:
            users = []
            for username, data in self.clients.items():
                users.append({
                    "username": data["username"],
                    "endpoint": data["endpoint"],
                    "status": data["status"],
                    "last_seen": data["last_seen_fmt"]
                })
            return users


# Singleton server registry
registry = ClientRegistry(offline_timeout=15.0)
