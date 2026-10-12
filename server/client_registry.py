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
    Thread-safe registry for managing active UDP clients, authenticated sessions, and presence status.
    Guarantees session isolation so one client cannot overwrite another client's active session.
    """

    def __init__(self, offline_timeout: float = 15.0):
        self.offline_timeout = offline_timeout
        self.clients: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register_client(self, username: str, ip: str, port: int, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Registers a user or updates endpoint and sets status to ONLINE.
        If the username is currently active in another session, registration is rejected
        to ensure one client's presence does not overwrite another's session.
        """
        username = username.strip()
        with self._lock:
            existing = self.clients.get(username)
            if existing:
                # Check for session conflict: if already online and session_id doesn't match
                if existing.get("status") == "ONLINE":
                    existing_sess = existing.get("session_id")
                    if existing_sess and session_id and existing_sess != session_id:
                        log_event(f"Session conflict rejected for user '{username}': existing session [{existing_sess}] != incoming [{session_id}]", "warning")
                        return None
                
            client_data = {
                "username": username,
                "session_id": session_id or (existing.get("session_id") if existing else None),
                "ip": ip,
                "port": port,
                "endpoint": f"{ip}:{port}",
                "last_seen": time.time(),
                "last_seen_fmt": get_timestamp(),
                "status": "ONLINE"
            }
            self.clients[username] = client_data
            log_event(f"UDP Client Registered: {username} (Session: {client_data['session_id']}) at {ip}:{port}")
            return client_data

    def update_heartbeat(self, username: str, ip: str, port: int, session_id: Optional[str] = None) -> bool:
        """
        Updates last_seen timestamp for client heartbeat.
        Enforces session matching so third parties cannot spoof or hijack heartbeats.
        """
        username = username.strip()
        with self._lock:
            if username in self.clients:
                existing = self.clients[username]
                existing_sess = existing.get("session_id")
                if existing.get("status") == "ONLINE" and existing_sess and session_id and existing_sess != session_id:
                    return False

                existing["last_seen"] = time.time()
                existing["last_seen_fmt"] = get_timestamp()
                existing["ip"] = ip
                existing["port"] = port
                existing["endpoint"] = f"{ip}:{port}"
                existing["status"] = "ONLINE"
                if session_id:
                    existing["session_id"] = session_id
                return True
            else:
                # Auto register if not in registry
                self.clients[username] = {
                    "username": username,
                    "session_id": session_id,
                    "ip": ip,
                    "port": port,
                    "endpoint": f"{ip}:{port}",
                    "last_seen": time.time(),
                    "last_seen_fmt": get_timestamp(),
                    "status": "ONLINE"
                }
                return True

    def mark_offline(self, username: str) -> None:
        """Explicitly marks user OFFLINE and clears stale UDP endpoint."""
        with self._lock:
            if username in self.clients:
                self.clients[username]["status"] = "OFFLINE"
                self.clients[username]["endpoint"] = "N/A"
                self.clients[username]["ip"] = None
                self.clients[username]["port"] = None
                log_event(f"User marked OFFLINE: {username}")

    def remove_stale_endpoint(self, username: str) -> None:
        """Removes stale network endpoint (IP/Port) for an offline or timed-out user."""
        with self._lock:
            if username in self.clients:
                self.clients[username]["endpoint"] = "N/A"
                self.clients[username]["ip"] = None
                self.clients[username]["port"] = None

    def check_timeouts(self) -> List[str]:
        """
        Iterates clients and marks OFFLINE any client whose last_seen exceeds offline_timeout.
        Cleans up stale endpoints and returns list of newly timed-out usernames.
        """
        now = time.time()
        newly_offline = []
        with self._lock:
            for username, data in self.clients.items():
                if data["status"] == "ONLINE" and (now - data["last_seen"]) > self.offline_timeout:
                    data["status"] = "OFFLINE"
                    data["endpoint"] = "N/A"
                    data["ip"] = None
                    data["port"] = None
                    newly_offline.append(username)
                    log_event(f"Presence Timeout: User '{username}' marked OFFLINE (No heartbeat for {self.offline_timeout}s)")
        return newly_offline

    def get_users_list(self) -> List[Dict[str, Any]]:
        """Returns list of registered users with session, endpoint, and online/offline status."""
        with self._lock:
            users = []
            for username, data in self.clients.items():
                users.append({
                    "username": data["username"],
                    "session_id": data.get("session_id", "N/A"),
                    "endpoint": data.get("endpoint", "N/A"),
                    "status": data["status"],
                    "last_seen": data["last_seen_fmt"]
                })
            return users

    def get_online_users(self) -> List[Dict[str, Any]]:
        """Returns only users currently ONLINE."""
        with self._lock:
            return [
                {
                    "username": data["username"],
                    "session_id": data.get("session_id", "N/A"),
                    "endpoint": data.get("endpoint", "N/A"),
                    "status": data["status"],
                    "last_seen": data["last_seen_fmt"]
                }
                for data in self.clients.values()
                if data.get("status") == "ONLINE"
            ]

    def clear(self) -> None:
        """Clears all registry records (used for test isolation)."""
        with self._lock:
            self.clients.clear()


# Singleton server registry
registry = ClientRegistry(offline_timeout=15.0)
