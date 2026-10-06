"""
UDP Client Module - Connectionless datagram socket client for UDP live chat, presence & heartbeat.
Includes Application-Layer Reliability: Sequence numbers, ACK tracking, 1s Timeout Retransmissions (3 retries max),
and Duplicate Message Detection.
"""

import json
import socket
import threading
import time
from typing import Dict, Any, List, Optional
from shared.config import DEFAULT_HOST, UDP_PORT, MAX_UDP_PAYLOAD, ACK_TIMEOUT, MAX_RETRIES
from shared.utils import print_success, print_error, print_info, print_warning, get_timestamp


class UDPClient:
    """
    UDP Client implementing application-layer reliability over connectionless datagram sockets.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = UDP_PORT, username: str = "Keerthi"):
        self.host = host
        self.port = port
        self.username = username
        self.sock: socket.socket | None = None
        self.is_connected = False

        self.is_heartbeat_running = False
        self.heartbeat_thread: threading.Thread | None = None
        self.receiver_thread: threading.Thread | None = None

        self.messages_history: List[Dict[str, Any]] = []
        self.pending_acks: Dict[int, Dict[str, Any]] = {}
        self.processed_sequences: set = set()
        self.pending_responses: Dict[str, Dict[str, Any]] = {}

        self.seq_counter = 100
        self.simulated_loss_rate = 0.0
        self._lock = threading.Lock()

    def set_simulated_loss_rate(self, rate: float) -> None:
        """Sets the client-side simulated packet loss rate."""
        with self._lock:
            self.simulated_loss_rate = max(0.0, min(0.5, rate))
            print_warning(f"[SIMULATION] Client UDP Loss Rate set to {self.simulated_loss_rate * 100:.1f}%")

    def connect(self) -> bool:
        """Creates AF_INET SOCK_DGRAM UDP IPv4 socket."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(1.0)
            self.is_connected = True
            print_success(f"UDP Socket initialized for {self.host}:{self.port}")

            # Start receiver thread as sole reader of UDP socket
            self.receiver_thread = threading.Thread(
                target=self._receive_loop,
                daemon=True,
                name="UDPReceiverThread"
            )
            self.receiver_thread.start()
            return True
        except socket.error as e:
            print_error(f"Could not create UDP socket: {e}")
            self.is_connected = False
            return False

    def _receive_loop(self) -> None:
        """Daemon thread continuously receiving and routing all UDP datagram packets from server."""
        while self.is_connected and self.sock:
            try:
                data, _ = self.sock.recvfrom(MAX_UDP_PAYLOAD)
                if not data:
                    continue

                try:
                    from shared.stats import global_stats
                    global_stats.record_udp_recv(len(data))
                except Exception:
                    pass

                try:
                    payload = json.loads(data.decode("utf-8"))
                    msg_type = payload.get("type", "")

                    with self._lock:
                        if msg_type in ["JOIN_ACK", "USERS_LIST", "LEAVE_ACK"]:
                            self.pending_responses[msg_type] = payload

                        elif msg_type == "ACK":
                            seq = int(payload.get("sequence", 0))
                            try:
                                from shared.stats import global_stats
                                global_stats.record_udp_ack()
                            except Exception:
                                pass

                            if seq in self.pending_acks:
                                self.pending_acks[seq]["status"] = "DELIVERED"
                                print_success(f"UDP ACK [{seq}] Received!")
                                # Update history entry status
                                for m in self.messages_history:
                                    if m.get("sequence") == seq:
                                        m["status"] = "Delivered"

                        elif msg_type == "BROADCAST":
                            seq = int(payload.get("sequence", 0))

                            # Duplicate message detection safeguard
                            if seq in self.processed_sequences:
                                print_warning(f"Duplicate UDP message [seq={seq}] detected - Ignored display.")
                                continue

                            self.processed_sequences.add(seq)
                            record = {
                                "sequence": seq,
                                "sender": payload.get("sender", "Unknown"),
                                "message": payload.get("message", ""),
                                "timestamp": payload.get("timestamp", get_timestamp()),
                                "status": "Delivered"
                            }
                            self.messages_history.append(record)
                            print_info(f"UDP Chat [{record['sender']}]: {record['message']}", tag="UDP")

                except Exception:
                    pass

            except (socket.timeout, socket.error):
                if not self.is_connected:
                    break

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
            with self._lock:
                self.pending_responses.pop("JOIN_ACK", None)

            raw_bytes = json.dumps(join_payload).encode("utf-8")
            self.sock.sendto(raw_bytes, (self.host, self.port))

            start_time = time.time()
            while time.time() - start_time < 3.0:
                with self._lock:
                    if "JOIN_ACK" in self.pending_responses:
                        response = self.pending_responses.pop("JOIN_ACK")
                        if response.get("status") == "SUCCESS":
                            print_success(f"UDP User '{self.username}' joined chat server successfully!")
                            self.start_heartbeat()
                            return response
                time.sleep(0.05)

            print_warning("UDP JOIN request timeout")
            return None

        except socket.error as e:
            print_warning(f"UDP JOIN request error: {e}")
            return None

    def send_chat_message(self, message_text: str) -> Dict[str, Any]:
        """
        Sends a MSG UDP datagram to the server with Application-Layer Reliability
        (ACK tracking & retransmission handling).
        """
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "UDP Client is not connected"}

        text = message_text.strip()
        if not text:
            return {"success": False, "error": "Empty message"}

        if len(text) > 1024:
            text = text[:1024]

        with self._lock:
            self.seq_counter += 1
            seq = self.seq_counter

        msg_payload = {
            "type": "MSG",
            "sequence": seq,
            "sender": self.username,
            "message": text,
            "timestamp": get_timestamp()
        }

        local_record = {
            "sequence": seq,
            "sender": self.username,
            "message": text,
            "timestamp": get_timestamp(),
            "status": "Sent"
        }

        with self._lock:
            self.messages_history.append(local_record)
            self.pending_acks[seq] = {
                "payload": msg_payload,
                "retries": 0,
                "status": "PENDING"
            }

        # Send initial datagram
        try:
            raw_bytes = json.dumps(msg_payload).encode("utf-8")
            self.sock.sendto(raw_bytes, (self.host, self.port))
            try:
                from shared.stats import global_stats
                global_stats.record_udp_send(len(raw_bytes))
            except Exception:
                pass
            print_info(f"Sent UDP Chat MSG [seq={seq}]: '{text}'", tag="UDP")
        except Exception as e:
            print_error(f"Error sending UDP message: {e}")
            return {"success": False, "error": str(e)}

        # Launch retransmission timer thread for this message
        retry_thread = threading.Thread(
            target=self._retransmit_monitor,
            args=(seq,),
            daemon=True,
            name=f"UDPRetryThread-{seq}"
        )
        retry_thread.start()

        return {"success": True, "sequence": seq, "message": text}

    def _retransmit_monitor(self, seq: int) -> None:
        """
        Monitors ACK status for `seq`. Retransmits after ACK_TIMEOUT (1s) up to MAX_RETRIES (3 times).
        """
        retries = 0
        while retries < MAX_RETRIES:
            time.sleep(ACK_TIMEOUT)

            with self._lock:
                if seq not in self.pending_acks:
                    break

                ack_info = self.pending_acks[seq]
                if ack_info["status"] == "DELIVERED":
                    break

                # ACK timed out - Retransmit packet
                retries += 1
                ack_info["retries"] = retries
                ack_info["status"] = "RETRYING"

                try:
                    from shared.stats import global_stats
                    global_stats.record_udp_retransmit()
                except Exception:
                    pass

                # Update status in chat history
                for m in self.messages_history:
                    if m.get("sequence") == seq:
                        m["status"] = f"Retrying ({retries}/{MAX_RETRIES})"

                print_warning(f"UDP ACK Timeout for [seq={seq}]. Retransmitting attempt {retries}/{MAX_RETRIES}...")

                try:
                    if self.sock and self.is_connected:
                        raw_bytes = json.dumps(ack_info["payload"]).encode("utf-8")
                        self.sock.sendto(raw_bytes, (self.host, self.port))
                        try:
                            from shared.stats import global_stats
                            global_stats.record_udp_send(len(raw_bytes))
                        except Exception:
                            pass
                except Exception as e:
                    print_error(f"Retransmit error: {e}")

        # Check final status after retries
        with self._lock:
            if seq in self.pending_acks and self.pending_acks[seq]["status"] != "DELIVERED":
                self.pending_acks[seq]["status"] = "FAILED"
                try:
                    from shared.stats import global_stats
                    global_stats.record_udp_failure()
                except Exception:
                    pass
                for m in self.messages_history:
                    if m.get("sequence") == seq:
                        m["status"] = "Delivery Failed"
                print_error(f"UDP Delivery Failed for message [seq={seq}] after {MAX_RETRIES} retries.")

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

    def _heartbeat_loop(self, interval: float) -> None:
        """Loop running in daemon thread sending HEARTBEAT datagrams over main client socket."""
        while self.is_heartbeat_running and self.is_connected and self.sock:
            try:
                hb_payload = {
                    "type": "HEARTBEAT",
                    "username": self.username
                }
                raw_bytes = json.dumps(hb_payload).encode("utf-8")
                self.sock.sendto(raw_bytes, (self.host, self.port))
            except Exception:
                pass

            time.sleep(interval)

    def get_online_users(self) -> List[Dict[str, Any]]:
        """Sends GET_USERS UDP datagram to fetch online user list."""
        if not self.is_connected or not self.sock:
            return []

        try:
            with self._lock:
                self.pending_responses.pop("USERS_LIST", None)

            req = {"type": "GET_USERS", "username": self.username}
            self.sock.sendto(json.dumps(req).encode("utf-8"), (self.host, self.port))

            start_time = time.time()
            while time.time() - start_time < 2.0:
                with self._lock:
                    if "USERS_LIST" in self.pending_responses:
                        resp = self.pending_responses.pop("USERS_LIST")
                        return resp.get("users", [])
                time.sleep(0.05)
            return []
        except Exception:
            return []

    def get_chat_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.messages_history)

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
            except Exception:
                pass
        self.is_connected = False
        self.sock = None
        print_info("Left UDP Chat & Presence", tag="UDP")

    disconnect = leave_chat
    stop = leave_chat
