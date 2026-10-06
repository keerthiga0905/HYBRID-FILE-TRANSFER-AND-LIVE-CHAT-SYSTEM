"""
UDP Server Module - Connectionless datagram socket for Live Chat & Online Presence tracking.
Operates on Port 6000/UDP. Manages UDP datagram receipt, chat broadcast, and presence registry updates.
"""

import json
import random
import socket
import threading
import time
from typing import Dict, Any
from shared.config import DEFAULT_HOST, UDP_PORT, MAX_UDP_PAYLOAD, DEFAULT_SIMULATED_LOSS_RATE
from shared.utils import print_info, print_success, print_error, print_warning, get_timestamp
from server.logger import log_event
from server.client_registry import registry


class UDPServer:
    """
    UDP Server implementing connectionless datagram socket handling & chat message broadcasting.
    Supports simulated packet loss mode for reliability demonstration.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = UDP_PORT):
        self.host = host
        self.port = port
        self.udp_socket: socket.socket | None = None
        self.is_running = False
        self._lock = threading.Lock()
        self.message_counter = 100
        self.simulated_loss_rate = DEFAULT_SIMULATED_LOSS_RATE

    def set_simulated_loss_rate(self, rate: float) -> None:
        """Sets the simulated packet loss rate (0.0 = 0% to 0.5 = 50%)."""
        with self._lock:
            self.simulated_loss_rate = max(0.0, min(0.5, rate))
            print_warning(f"[SIMULATION] UDP Packet Loss Rate set to {self.simulated_loss_rate * 100:.1f}%")

    def start(self) -> None:
        """Initializes UDP IPv4 socket, binds to port 6000, and launches receive loop."""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.udp_socket.bind((self.host, self.port))
            self.is_running = True
            log_event(f"UDP Chat & Presence Server listening on {self.host}:{self.port}")
            print_success(f"UDP Chat & Presence Server listening on {self.host}:{self.port}")

            recv_thread = threading.Thread(target=self._receive_loop, daemon=True, name="UDPReceiveLoop")
            recv_thread.start()

            presence_thread = threading.Thread(target=self._presence_monitor_loop, daemon=True, name="UDPPresenceMonitor")
            presence_thread.start()

        except Exception as e:
            print_error(f"Failed to start UDP Server: {e}")
            log_event(f"UDP Server startup error: {e}", "error")
            raise e

    def _receive_loop(self) -> None:
        """Continuously receives UDP datagrams without establishing TCP connections."""
        while self.is_running:
            try:
                data, addr = self.udp_socket.recvfrom(MAX_UDP_PAYLOAD)
                if not data:
                    continue

                # Simulated Packet Loss Mode Safeguard
                if self.simulated_loss_rate > 0.0 and random.random() < self.simulated_loss_rate:
                    print_warning(f"[SIMULATED LOSS] Artificially dropped incoming UDP packet from {addr}!")
                    log_event(f"[SIMULATED LOSS] Dropped UDP datagram from {addr}")
                    try:
                        from shared.stats import global_stats
                        global_stats.record_udp_failure()
                    except Exception:
                        pass
                    continue

                try:
                    payload = json.loads(data.decode("utf-8"))
                    self._handle_datagram(payload, addr)
                except (json.JSONDecodeError, UnicodeDecodeError) as err:
                    print_warning(f"Received invalid UDP datagram from {addr}: {err}")

            except socket.error:
                if not self.is_running:
                    break

    def _handle_datagram(self, payload: Dict[str, Any], addr: tuple[str, int]) -> None:
        """Processes incoming UDP payload commands."""
        msg_type = payload.get("type", "").upper()
        username = payload.get("username", payload.get("sender", "Unknown")).strip()

        if msg_type == "JOIN":
            registry.register_client(username, addr[0], addr[1])
            print_info(f"UDP User JOIN: '{username}' from {addr[0]}:{addr[1]}", tag="UDP")
            log_event(f"UDP User JOIN: '{username}' ({addr[0]}:{addr[1]})")

            response = {
                "type": "JOIN_ACK",
                "status": "SUCCESS",
                "message": f"Welcome '{username}' to UDP Chat Server",
                "users": registry.get_users_list()
            }
            self._send_response(response, addr)

        elif msg_type == "HEARTBEAT":
            registry.update_heartbeat(username, addr[0], addr[1])
            response = {
                "type": "HEARTBEAT_ACK",
                "status": "SUCCESS",
                "username": username,
                "server_time": time.time()
            }
            self._send_response(response, addr)

        elif msg_type == "MSG":
            seq = payload.get("sequence", 0)
            text = str(payload.get("message", "")).strip()

            # Enforce 1024 character message limit
            if len(text) > 1024:
                text = text[:1024]

            registry.update_heartbeat(username, addr[0], addr[1])
            print_info(f"UDP Chat MSG from '{username}' [seq={seq}]: '{text}'", tag="UDP")
            log_event(f"UDP Chat MSG from '{username}' [seq={seq}]: {text}")

            # Send ACK to sender
            ack_msg = {
                "type": "ACK",
                "sequence": seq,
                "status": "SUCCESS"
            }
            self._send_response(ack_msg, addr)

            # Broadcast message to all online clients
            broadcast_packet = {
                "type": "BROADCAST",
                "sequence": seq,
                "sender": username,
                "message": text,
                "timestamp": get_timestamp()
            }
            self._broadcast_to_online_users(broadcast_packet, sender_addr=addr)

        elif msg_type == "GET_USERS":
            response = {
                "type": "USERS_LIST",
                "users": registry.get_users_list()
            }
            self._send_response(response, addr)

        elif msg_type == "LEAVE":
            registry.mark_offline(username)
            print_info(f"UDP User LEAVE: '{username}'", tag="UDP")
            response = {"type": "LEAVE_ACK", "status": "SUCCESS"}
            self._send_response(response, addr)

    def _send_response(self, response_data: Dict[str, Any], addr: tuple[str, int]) -> None:
        """Sends a JSON formatted UDP datagram back to client endpoint."""
        try:
            raw_bytes = json.dumps(response_data).encode("utf-8")
            self.udp_socket.sendto(raw_bytes, addr)
        except Exception as e:
            log_event(f"Error sending UDP datagram to {addr}: {e}", "error")

    def _broadcast_to_online_users(self, broadcast_data: Dict[str, Any], sender_addr: tuple[str, int]) -> None:
        """Broadcasts UDP datagram to all registered online clients."""
        raw_bytes = json.dumps(broadcast_data).encode("utf-8")
        with registry._lock:
            for user, data in registry.clients.items():
                if data["status"] == "ONLINE":
                    try:
                        self.udp_socket.sendto(raw_bytes, (data["ip"], data["port"]))
                    except Exception as e:
                        log_event(f"Broadcast error to {user}: {e}", "warning")

    def _presence_monitor_loop(self) -> None:
        """Periodically checks for client heartbeat timeouts every 3 seconds."""
        while self.is_running:
            time.sleep(3.0)
            timed_out_users = registry.check_timeouts()
            for user in timed_out_users:
                print_warning(f"UDP User '{user}' marked OFFLINE (Heartbeat timeout)")

    def stop(self) -> None:
        """Stops UDP server and closes socket."""
        self.is_running = False
        if self.udp_socket:
            try:
                self.udp_socket.close()
            except Exception:
                pass
        print_info("UDP Chat Server stopped", tag="UDP")
        log_event("UDP Server stopped")
