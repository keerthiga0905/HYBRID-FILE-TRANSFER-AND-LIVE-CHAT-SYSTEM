"""
UDP Server Module - Connectionless datagram socket for Live Chat & Online Presence tracking.
Operates on Port 6000/UDP. Manages UDP datagram receipt, chat broadcast, and presence registry updates.
"""

import json
import random
import socket
import threading
import time
from typing import Dict, Any, Optional
from shared.config import DEFAULT_HOST, UDP_PORT, MAX_UDP_PAYLOAD, DEFAULT_SIMULATED_LOSS_RATE
from shared.utils import print_info, print_success, print_error, print_warning, get_timestamp
from server.logger import log_event
from server.client_registry import registry as default_registry


class UDPServer:
    """
    UDP Server implementing connectionless datagram socket handling & chat message broadcasting.
    Supports simulated packet loss mode for reliability demonstration.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = UDP_PORT, registry: Optional[Any] = None):
        self.host = host
        self.port = port
        self.registry = registry if registry is not None else default_registry
        self.udp_socket: socket.socket | None = None
        self.is_running = False
        self._lock = threading.Lock()
        self.message_counter = 100
        self.simulated_loss_rate = DEFAULT_SIMULATED_LOSS_RATE
        self.processed_msg_ids: set[str] = set()
        self.processed_messages: set[tuple[str, int]] = set()

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
                    if isinstance(payload, dict):
                        self._handle_datagram(payload, addr)
                    else:
                        print_warning(f"Received non-dict UDP datagram from {addr}")
                except (json.JSONDecodeError, UnicodeDecodeError) as err:
                    print_warning(f"Received malformed UDP datagram from {addr}: {err}")

            except socket.error:
                if not self.is_running:
                    break

    def _handle_datagram(self, payload: Dict[str, Any], addr: tuple[str, int]) -> None:
        """Processes incoming UDP payload commands."""
        msg_type = payload.get("type", "").upper()
        username = payload.get("username", payload.get("sender", "Unknown")).strip()
        session_id = payload.get("session_id")

        if msg_type == "JOIN":
            if not username or len(username) < 2:
                response = {
                    "type": "JOIN_ACK",
                    "status": "ERROR",
                    "message": "Invalid username. Must be at least 2 characters."
                }
                self._send_response(response, addr)
                return

            client_data = self.registry.register_client(username, addr[0], addr[1], session_id=session_id)
            if client_data is None:
                # Session conflict detected - do not overwrite another client's session
                response = {
                    "type": "JOIN_ACK",
                    "status": "ERROR",
                    "code": "SESSION_CONFLICT",
                    "message": f"Username '{username}' is already active in another session."
                }
                self._send_response(response, addr)
                return

            print_info(f"UDP User JOIN: '{username}' (Session: {client_data.get('session_id')}) from {addr[0]}:{addr[1]}", tag="UDP")
            log_event(f"UDP User JOIN: '{username}' (Session: {client_data.get('session_id')}) ({addr[0]}:{addr[1]})")

            response = {
                "type": "JOIN_ACK",
                "status": "SUCCESS",
                "session_id": client_data.get("session_id"),
                "message": f"Welcome '{username}' to UDP Chat Server",
                "users": self.registry.get_users_list()
            }
            self._send_response(response, addr)

            # Broadcast presence notification to other connected clients
            broadcast_presence = {
                "type": "PRESENCE_CHANGE",
                "event": "USER_JOINED",
                "username": username,
                "session_id": client_data.get("session_id"),
                "status": "ONLINE",
                "users": self.registry.get_users_list(),
                "timestamp": get_timestamp()
            }
            self._broadcast_to_online_users(broadcast_presence, sender_addr=addr)

        elif msg_type == "HEARTBEAT":
            ok = self.registry.update_heartbeat(username, addr[0], addr[1], session_id=session_id)
            if not ok:
                response = {
                    "type": "HEARTBEAT_ACK",
                    "status": "ERROR",
                    "code": "SESSION_CONFLICT",
                    "message": f"Heartbeat rejected: session mismatch for '{username}'"
                }
            else:
                response = {
                    "type": "HEARTBEAT_ACK",
                    "status": "SUCCESS",
                    "username": username,
                    "server_time": time.time()
                }
            self._send_response(response, addr)

        elif msg_type == "MSG":
            seq = int(payload.get("sequence", 0))
            msg_id = str(payload.get("msg_id", f"msg_{seq}"))
            text = str(payload.get("message", "")).strip()
            mode = str(payload.get("mode", "GROUP")).upper()
            recipient = str(payload.get("recipient", "ALL")).strip()
            require_ack = payload.get("require_ack", True)

            # Module 6: Duplicate detection and ACK re-send (Req 6 & Req 8)
            with self._lock:
                is_duplicate = (msg_id in self.processed_msg_ids) or ((username, seq) in self.processed_messages and seq > 0)

            if is_duplicate:
                print_warning(f"UDP Duplicate MSG detected from '{username}' [msg_id={msg_id}, seq={seq}]. Re-sending ACK.")
                # If a duplicate arrives, send the ACK again so original sender stops retrying
                ack_msg = {
                    "type": "ACK",
                    "msg_id": msg_id,
                    "sequence": seq,
                    "status": "SUCCESS",
                    "mode": mode,
                    "recipient": recipient,
                    "duplicate": True,
                    "timestamp": get_timestamp()
                }
                self._send_response(ack_msg, addr)
                return

            # 1. Sender validation against registered session and endpoint (anti-spoofing)
            sender_data = self.registry.clients.get(username)
            if not sender_data or sender_data.get("status") != "ONLINE":
                err_resp = {
                    "type": "ERROR",
                    "code": "UNAUTHORIZED_SENDER",
                    "message": f"Sender '{username}' is not registered or not online."
                }
                self._send_response(err_resp, addr)
                return

            if sender_data.get("session_id") and session_id and sender_data["session_id"] != session_id:
                err_resp = {
                    "type": "ERROR",
                    "code": "SESSION_MISMATCH",
                    "message": "Sender session ID does not match registered session."
                }
                self._send_response(err_resp, addr)
                return

            if sender_data.get("ip") and sender_data.get("port"):
                if (sender_data["ip"], sender_data["port"]) != addr:
                    err_resp = {
                        "type": "ERROR",
                        "code": "ENDPOINT_SPOOF",
                        "message": "Sender IP/Port does not match registered endpoint."
                    }
                    self._send_response(err_resp, addr)
                    return

            # 2. Message validation & size limit (1024 characters)
            if not text:
                err_resp = {
                    "type": "ERROR",
                    "code": "EMPTY_MESSAGE",
                    "message": "Cannot send empty message."
                }
                self._send_response(err_resp, addr)
                return

            if len(text) > 1024:
                text = text[:1024]

            self.registry.update_heartbeat(username, addr[0], addr[1], session_id=session_id)

            # Record processed message to prevent duplicate processing
            with self._lock:
                self.processed_msg_ids.add(msg_id)
                if seq > 0:
                    self.processed_messages.add((username, seq))
                if len(self.processed_msg_ids) > 2000:
                    self.processed_msg_ids.clear()
                    self.processed_messages.clear()

            # 3. Route Private vs Group Message
            if mode == "PRIVATE" or (recipient and recipient.upper() not in ["ALL", "GROUP", ""]):
                # Private Chat Routing
                if recipient == username:
                    err_resp = {
                        "type": "ERROR",
                        "code": "SELF_MESSAGE",
                        "message": "Cannot send private message to yourself."
                    }
                    self._send_response(err_resp, addr)
                    return

                target_data = self.registry.clients.get(recipient)
                if not target_data or target_data.get("status") != "ONLINE":
                    err_resp = {
                        "type": "ERROR",
                        "code": "RECIPIENT_OFFLINE",
                        "message": f"User '{recipient}' is not online."
                    }
                    self._send_response(err_resp, addr)
                    return

                if not target_data.get("ip") or not target_data.get("port"):
                    err_resp = {
                        "type": "ERROR",
                        "code": "RECIPIENT_UNAVAILABLE",
                        "message": f"User '{recipient}' endpoint is unavailable."
                    }
                    self._send_response(err_resp, addr)
                    return

                # Send ACK to sender with msg_id & sequence (Req 2 & Req 3)
                ack_msg = {
                    "type": "ACK",
                    "msg_id": msg_id,
                    "sequence": seq,
                    "status": "SUCCESS",
                    "mode": "PRIVATE",
                    "recipient": recipient,
                    "timestamp": get_timestamp()
                }
                self._send_response(ack_msg, addr)

                # Deliver private message ONLY to the target recipient
                private_packet = {
                    "type": "MSG",
                    "mode": "PRIVATE",
                    "msg_id": msg_id,
                    "sequence": seq,
                    "sender": username,
                    "recipient": recipient,
                    "message": text,
                    "require_ack": require_ack,
                    "timestamp": get_timestamp()
                }
                try:
                    raw_bytes = json.dumps(private_packet).encode("utf-8")
                    self.udp_socket.sendto(raw_bytes, (target_data["ip"], target_data["port"]))
                    print_info(f"UDP Private MSG routed: '{username}' -> '{recipient}' [msg_id={msg_id}, seq={seq}]", tag="UDP")
                    log_event(f"UDP Private MSG: '{username}' -> '{recipient}' [msg_id={msg_id}, seq={seq}]: {text}")
                except Exception as e:
                    log_event(f"Error routing private UDP message to {recipient}: {e}", "error")

            else:
                # Group Chat Broadcast
                ack_msg = {
                    "type": "ACK",
                    "msg_id": msg_id,
                    "sequence": seq,
                    "status": "SUCCESS",
                    "mode": "GROUP",
                    "recipient": "ALL",
                    "timestamp": get_timestamp()
                }
                self._send_response(ack_msg, addr)

                # Broadcast to all online users (excluding sender)
                broadcast_packet = {
                    "type": "BROADCAST",
                    "mode": "GROUP",
                    "msg_id": msg_id,
                    "sequence": seq,
                    "sender": username,
                    "recipient": "ALL",
                    "message": text,
                    "require_ack": require_ack,
                    "timestamp": get_timestamp()
                }
                self._broadcast_to_online_users(broadcast_packet, sender_addr=addr)
                print_info(f"UDP Group MSG from '{username}' [msg_id={msg_id}, seq={seq}]: '{text}'", tag="UDP")
                log_event(f"UDP Group MSG from '{username}' [msg_id={msg_id}, seq={seq}]: {text}")

        elif msg_type == "ACK":
            # Module 6: Forward client-to-client ACK if targeted to specific peer
            target_recip = payload.get("recipient")
            if target_recip and target_recip.upper() not in ["ALL", "GROUP", ""]:
                target_data = self.registry.clients.get(target_recip)
                if target_data and target_data.get("status") == "ONLINE" and target_data.get("ip") and target_data.get("port"):
                    try:
                        self.udp_socket.sendto(json.dumps(payload).encode("utf-8"), (target_data["ip"], target_data["port"]))
                    except Exception as e:
                        log_event(f"Error forwarding ACK to {target_recip}: {e}", "warning")

        elif msg_type == "GET_USERS":
            response = {
                "type": "USERS_LIST",
                "users": self.registry.get_users_list(),
                "online_users": self.registry.get_online_users()
            }
            self._send_response(response, addr)

        elif msg_type == "LEAVE":
            self.registry.mark_offline(username)
            print_info(f"UDP User LEAVE: '{username}'", tag="UDP")
            response = {"type": "LEAVE_ACK", "status": "SUCCESS"}
            self._send_response(response, addr)

            # Notify remaining users of presence change
            broadcast_presence = {
                "type": "PRESENCE_CHANGE",
                "event": "USER_LEFT",
                "username": username,
                "status": "OFFLINE",
                "users": self.registry.get_users_list(),
                "timestamp": get_timestamp()
            }
            self._broadcast_to_online_users(broadcast_presence, sender_addr=addr)

    def _send_response(self, response_data: Dict[str, Any], addr: tuple[str, int]) -> None:
        """Sends a JSON formatted UDP datagram back to client endpoint."""
        try:
            raw_bytes = json.dumps(response_data).encode("utf-8")
            self.udp_socket.sendto(raw_bytes, addr)
        except Exception as e:
            log_event(f"Error sending UDP datagram to {addr}: {e}", "error")

    def _broadcast_to_online_users(self, broadcast_data: Dict[str, Any], sender_addr: tuple[str, int] | None = None) -> None:
        """Broadcasts UDP datagram to all registered online clients with active endpoints."""
        raw_bytes = json.dumps(broadcast_data).encode("utf-8")
        with self.registry._lock:
            for user, data in self.registry.clients.items():
                if data.get("status") == "ONLINE" and data.get("ip") and data.get("port"):
                    target_endpoint = (data["ip"], data["port"])
                    # Avoid echoing message back to sender endpoint if requested
                    if sender_addr and target_endpoint == sender_addr:
                        continue
                    try:
                        self.udp_socket.sendto(raw_bytes, target_endpoint)
                    except Exception as e:
                        log_event(f"Broadcast error to {user} at {target_endpoint}: {e}", "warning")

    def _presence_monitor_loop(self) -> None:
        """Periodically checks for client heartbeat timeouts every 1.5 seconds."""
        while self.is_running:
            time.sleep(1.5)
            timed_out_users = self.registry.check_timeouts()
            for user in timed_out_users:
                print_warning(f"UDP User '{user}' marked OFFLINE (Heartbeat timeout)")
                broadcast_packet = {
                    "type": "PRESENCE_CHANGE",
                    "event": "TIMEOUT",
                    "username": user,
                    "status": "OFFLINE",
                    "users": self.registry.get_users_list(),
                    "timestamp": get_timestamp()
                }
                self._broadcast_to_online_users(broadcast_packet)

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
