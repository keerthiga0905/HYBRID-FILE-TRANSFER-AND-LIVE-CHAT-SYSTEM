"""
UDP Client Module - Connectionless datagram socket client for UDP live chat, presence & heartbeat.
Includes Application-Layer Reliability: Sequence numbers, ACK tracking, 1s Timeout Retransmissions (3 retries max),
and Duplicate Message Detection.
"""

import json
import socket
import threading
import time
import uuid
from typing import Dict, Any, List, Optional
from shared.config import DEFAULT_HOST, UDP_PORT, MAX_UDP_PAYLOAD, ACK_TIMEOUT, MAX_RETRIES
from shared.utils import print_success, print_error, print_info, print_warning, get_timestamp


class UDPClient:
    """
    UDP Client implementing application-layer reliability over connectionless datagram sockets,
    authenticated session tracking, live chat, heartbeat presence, and presence notifications.
    Includes unique message IDs, sequence tracking, timeout retransmission (3 retries max),
    and duplicate message filtering.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = UDP_PORT,
        username: str = "Keerthi",
        session_id: Optional[str] = None,
        ack_timeout: float = ACK_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.session_id = session_id
        self.ack_timeout = max(0.05, float(ack_timeout))
        self.max_retries = max(0, int(max_retries))
        self.sock: socket.socket | None = None
        self.is_connected = False

        self.is_heartbeat_running = False
        self.heartbeat_thread: threading.Thread | None = None
        self.receiver_thread: threading.Thread | None = None

        self.messages_history: List[Dict[str, Any]] = []
        self.presence_events: List[Dict[str, Any]] = []
        self.pending_acks: Dict[Any, Dict[str, Any]] = {}
        self.processed_sequences: set = set()
        self.processed_msg_ids: set = set()
        self.pending_responses: Dict[str, Dict[str, Any]] = {}

        self.seq_counter = 100
        self.simulated_loss_rate = 0.0
        self._lock = threading.Lock()

    def set_retry_policy(self, ack_timeout: float = ACK_TIMEOUT, max_retries: int = MAX_RETRIES) -> None:
        """
        Configures application-layer reliability policy (timeout duration and retry attempts).
        """
        with self._lock:
            self.ack_timeout = max(0.05, float(ack_timeout))
            self.max_retries = max(0, int(max_retries))
            print_info(f"UDP Retry Policy configured: ACK timeout={self.ack_timeout}s, Max retries={self.max_retries}", tag="UDP")

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

                        elif msg_type == "PRESENCE_CHANGE":
                            self.presence_events.append(payload)
                            if len(self.presence_events) > 50:
                                self.presence_events.pop(0)
                            evt = payload.get("event", "UPDATE")
                            u = payload.get("username", "Unknown")
                            st = payload.get("status", "")
                            print_info(f"UDP Presence Notification: User '{u}' is {st} [{evt}]", tag="UDP")

                        elif msg_type == "ACK":
                            seq = int(payload.get("sequence", 0))
                            msg_id = payload.get("msg_id")
                            try:
                                from shared.stats import global_stats
                                global_stats.record_udp_ack()
                            except Exception:
                                pass

                            matched_key = None
                            if seq in self.pending_acks:
                                matched_key = seq
                            elif msg_id:
                                for k, v in self.pending_acks.items():
                                    if v.get("msg_id") == msg_id:
                                        matched_key = k
                                        break

                            if matched_key is not None:
                                self.pending_acks[matched_key]["status"] = "DELIVERED"
                                print_success(f"UDP ACK [msg_id={msg_id}, seq={seq}] Received!")
                                # Update history entry status
                                for m in self.messages_history:
                                    if (seq and m.get("sequence") == seq) or (msg_id and m.get("msg_id") == msg_id):
                                        m["status"] = "Delivered"

                        elif msg_type == "ERROR":
                            code = payload.get("code", "ERROR")
                            err_msg = payload.get("message", "Unknown error")
                            print_warning(f"UDP Error from Server [{code}]: {err_msg}")

                        elif msg_type in ["BROADCAST", "MSG"]:
                            seq = int(payload.get("sequence", 0))
                            msg_id = str(payload.get("msg_id", f"msg_{seq}"))
                            sender = payload.get("sender", "Unknown")
                            recipient = payload.get("recipient", "ALL")
                            mode = str(payload.get("mode", "GROUP" if msg_type == "BROADCAST" else "PRIVATE")).upper()
                            require_ack = payload.get("require_ack", False)

                            # Check if message already exists in history (e.g. locally added on send)
                            already_present = False
                            for m in self.messages_history:
                                if (m.get("msg_id") == msg_id and msg_id) or (m.get("sequence") == seq and m.get("sender") == sender):
                                    m["status"] = "Delivered"
                                    already_present = True
                                    break

                            if already_present:
                                self.processed_sequences.add(seq)
                                self.processed_msg_ids.add(msg_id)
                                continue

                            # Duplicate sequence / msg_id detection (Requirements 6, 7, 8)
                            is_duplicate = (msg_id in self.processed_msg_ids) or (seq in self.processed_sequences and seq > 0)
                            if is_duplicate:
                                print_warning(f"Duplicate UDP message [msg_id={msg_id}, seq={seq}] detected - Ignored display.")
                                # Requirement 8: If a duplicate arrives, send the ACK again so original sender can stop retrying
                                if require_ack or msg_type == "MSG":
                                    ack_reply = {
                                        "type": "ACK",
                                        "msg_id": msg_id,
                                        "sequence": seq,
                                        "status": "SUCCESS",
                                        "duplicate": True,
                                        "sender": self.username,
                                        "recipient": sender,
                                        "timestamp": get_timestamp()
                                    }
                                    try:
                                        self.sock.sendto(json.dumps(ack_reply).encode("utf-8"), (self.host, self.port))
                                    except Exception:
                                        pass
                                continue

                            self.processed_sequences.add(seq)
                            self.processed_msg_ids.add(msg_id)
                            record = {
                                "msg_id": msg_id,
                                "sequence": seq,
                                "mode": mode,
                                "sender": sender,
                                "recipient": recipient,
                                "message": payload.get("message", ""),
                                "timestamp": payload.get("timestamp", get_timestamp()),
                                "status": "Delivered"
                            }
                            self.messages_history.append(record)
                            if mode == "PRIVATE":
                                print_info(f"UDP Private MSG from [{sender}]: {record['message']}", tag="UDP")
                            else:
                                print_info(f"UDP Group Chat [{sender}]: {record['message']}", tag="UDP")

                            # Send ACK if required (Requirement 3)
                            if require_ack:
                                ack_reply = {
                                    "type": "ACK",
                                    "msg_id": msg_id,
                                    "sequence": seq,
                                    "status": "SUCCESS",
                                    "sender": self.username,
                                    "recipient": sender,
                                    "timestamp": get_timestamp()
                                }
                                try:
                                    self.sock.sendto(json.dumps(ack_reply).encode("utf-8"), (self.host, self.port))
                                except Exception:
                                    pass

                except Exception:
                    pass

            except (socket.timeout, socket.error):
                if not self.is_connected:
                    break

    def join_chat(self, username: Optional[str] = None, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Sends JOIN UDP datagram to server to register presence."""
        if username:
            self.username = username
        if session_id:
            self.session_id = session_id

        if not self.is_connected or not self.sock:
            if not self.connect():
                return None

        join_payload = {
            "type": "JOIN",
            "username": self.username,
            "session_id": self.session_id
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
                            if response.get("session_id"):
                                self.session_id = response.get("session_id")
                            print_success(f"UDP User '{self.username}' joined chat server successfully!")
                            self.start_heartbeat()
                            return response
                        elif response.get("status") == "ERROR":
                            print_warning(f"UDP JOIN rejected: {response.get('message')}")
                            return response
                time.sleep(0.05)

            print_warning("UDP JOIN request timeout")
            return None

        except socket.error as e:
            print_warning(f"UDP JOIN request error: {e}")
            return None

    def send_chat_message(
        self,
        message_text: str,
        recipient: Optional[str] = None,
        require_ack: bool = True,
        msg_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends a MSG UDP datagram to the server with Application-Layer Reliability
        (Unique message ID, sequence tracking, ACK monitoring & timeout retransmission).
        Supports Group and Private messaging.
        Note: An ACK confirms socket/endpoint receipt, NOT that a human has read the message.
        """
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "UDP Client is not connected"}

        text = message_text.strip()
        if not text:
            return {"success": False, "error": "Empty message"}

        if len(text) > 1024:
            text = text[:1024]

        mode = "PRIVATE" if recipient and recipient.upper() not in ["ALL", "GROUP", ""] else "GROUP"
        target_recip = recipient if mode == "PRIVATE" else "ALL"

        with self._lock:
            self.seq_counter += 1
            seq = self.seq_counter
            if not msg_id:
                msg_id = f"msg_{uuid.uuid4().hex[:12]}"

        msg_payload = {
            "type": "MSG",
            "msg_id": msg_id,
            "mode": mode,
            "sequence": seq,
            "sender": self.username,
            "recipient": target_recip,
            "message": text,
            "session_id": self.session_id,
            "require_ack": require_ack,
            "timestamp": get_timestamp()
        }

        local_record = {
            "msg_id": msg_id,
            "sequence": seq,
            "mode": mode,
            "sender": self.username,
            "recipient": target_recip,
            "message": text,
            "timestamp": get_timestamp(),
            "status": "Sent"
        }

        with self._lock:
            self.processed_sequences.add(seq)
            self.processed_msg_ids.add(msg_id)
            self.messages_history.append(local_record)
            if require_ack:
                self.pending_acks[seq] = {
                    "msg_id": msg_id,
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
            prefix = f"Private to [{target_recip}]" if mode == "PRIVATE" else "Group"
            print_info(f"Sent UDP Chat MSG ({prefix}) [msg_id={msg_id}, seq={seq}]: '{text}'", tag="UDP")
        except Exception as e:
            print_error(f"Error sending UDP message: {e}")
            return {"success": False, "error": str(e), "msg_id": msg_id, "sequence": seq}

        # Launch retransmission timer thread if delivery confirmation required
        if require_ack:
            retry_thread = threading.Thread(
                target=self._retransmit_monitor,
                args=(seq, msg_id),
                daemon=True,
                name=f"UDPRetryThread-{seq}"
            )
            retry_thread.start()

        return {
            "success": True,
            "msg_id": msg_id,
            "sequence": seq,
            "message": text,
            "status": "Sent"
        }

    def _retransmit_monitor(self, seq: int, msg_id: str) -> None:
        """
        Monitors ACK status for message [seq, msg_id].
        Retransmits after `ack_timeout` (default 1.0s) up to `max_retries` (default 3 times).
        Thread-safe and non-blocking: runs concurrently without blocking other chat actions.
        """
        retries = 0
        while retries < self.max_retries:
            time.sleep(self.ack_timeout)

            with self._lock:
                if seq not in self.pending_acks:
                    break

                ack_info = self.pending_acks[seq]
                if ack_info["status"] in ["DELIVERED", "ACKNOWLEDGED"]:
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
                    if m.get("sequence") == seq or m.get("msg_id") == msg_id:
                        m["status"] = f"Retrying ({retries}/{self.max_retries})"

                print_warning(f"UDP ACK Timeout for [msg_id={msg_id}, seq={seq}]. Retransmitting attempt {retries}/{self.max_retries}...")

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
            if seq in self.pending_acks and self.pending_acks[seq]["status"] not in ["DELIVERED", "ACKNOWLEDGED"]:
                self.pending_acks[seq]["status"] = "FAILED"
                try:
                    from shared.stats import global_stats
                    global_stats.record_udp_failure()
                except Exception:
                    pass
                for m in self.messages_history:
                    if m.get("sequence") == seq or m.get("msg_id") == msg_id:
                        m["status"] = "Delivery Failed"
                print_error(f"UDP Delivery Failed for message [msg_id={msg_id}, seq={seq}] after {self.max_retries} retries.")

    def start_heartbeat(self, interval: float = 5.0) -> None:
        """Launches background thread sending HEARTBEAT datagrams."""
        if self.is_heartbeat_running:
            self.stop_heartbeat()
            time.sleep(0.05)

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
                    "username": self.username,
                    "session_id": self.session_id
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

            req = {"type": "GET_USERS", "username": self.username, "session_id": self.session_id}
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

    def send_private_message(self, recipient: str, message_text: str) -> Dict[str, Any]:
        """Convenience method to send a private UDP chat message to a specific user."""
        return self.send_chat_message(message_text=message_text, recipient=recipient)

    def send_group_message(self, message_text: str) -> Dict[str, Any]:
        """Convenience method to send a group UDP chat message to all online users."""
        return self.send_chat_message(message_text=message_text, recipient="ALL")

    def get_chat_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.messages_history)

    def get_private_messages(self, peer: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filters chat history for private messages (optionally with a specific peer)."""
        with self._lock:
            privates = [m for m in self.messages_history if m.get("mode") == "PRIVATE"]
            if peer:
                return [m for m in privates if m.get("sender") == peer or m.get("recipient") == peer]
            return privates

    def get_group_messages(self) -> List[Dict[str, Any]]:
        """Filters chat history for group messages."""
        with self._lock:
            return [m for m in self.messages_history if m.get("mode") == "GROUP"]

    def get_presence_events(self) -> List[Dict[str, Any]]:
        """Returns list of received UDP presence change notifications."""
        with self._lock:
            return list(self.presence_events)

    def stop_heartbeat(self) -> None:
        """Stops background heartbeat loop."""
        self.is_heartbeat_running = False

    def leave_chat(self) -> None:
        """Sends LEAVE UDP datagram, stops heartbeat, and safely closes UDP socket."""
        self.stop_heartbeat()
        sock_to_close = self.sock
        if sock_to_close and self.is_connected:
            try:
                leave_req = {
                    "type": "LEAVE",
                    "username": self.username,
                    "session_id": self.session_id
                }
                sock_to_close.sendto(json.dumps(leave_req).encode("utf-8"), (self.host, self.port))
            except Exception:
                pass
        self.is_connected = False
        self.sock = None
        if sock_to_close:
            try:
                sock_to_close.close()
            except Exception:
                pass
        print_info("Left UDP Chat & Presence", tag="UDP")

    disconnect = leave_chat
    stop = leave_chat
