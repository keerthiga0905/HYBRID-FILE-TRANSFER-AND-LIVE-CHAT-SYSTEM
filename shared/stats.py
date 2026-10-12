import time
import threading
from typing import Dict, Any, List, Optional


class NetworkStatsTracker:
    """
    Thread-safe network metrics collector for TCP file transfer & UDP live chat.
    Calculates actual throughput, durations, latencies, and reliability metrics
    from measured events and real socket timestamps.
    """

    def __init__(self):
        self._lock = threading.Lock()
        
        # Cumulative Byte Counters
        self.tcp_bytes_sent = 0
        self.tcp_bytes_received = 0
        self.udp_bytes_sent = 0
        self.udp_bytes_received = 0

        # Packet / Chunk Counters
        self.tcp_packets_sent = 0
        self.tcp_packets_received = 0
        self.udp_packets_sent = 0
        self.udp_packets_received = 0

        # TCP Transfer Metrics (Module 8)
        self.tcp_resumed_transfers = 0
        self.tcp_transfers_history: List[Dict[str, Any]] = []
        self.last_tcp_transfer: Optional[Dict[str, Any]] = None

        # UDP Reliability & Message Metrics (Module 8)
        self.udp_messages_sent = 0
        self.udp_messages_received = 0
        self.udp_acks_received = 0
        self.udp_retransmissions = 0
        self.udp_ack_timeouts = 0
        self.udp_packets_failed = 0  # Application-observed message loss

        # Latency (RTT) measurements in ms
        self.last_tcp_rtt_ms = 0.0
        self.last_udp_rtt_ms = 0.0
        self.udp_latencies: List[float] = []

        # Speed calculation sample windows
        self.start_time = time.time()
        self.last_sample_time = time.time()
        self.last_tcp_sent_sample = 0
        self.last_tcp_recv_sample = 0
        self.last_udp_sent_sample = 0
        self.last_udp_recv_sample = 0

        # Instantaneous Speeds (KB/s)
        self.tcp_upload_speed_kbs = 0.0
        self.tcp_download_speed_kbs = 0.0
        self.udp_send_speed_kbs = 0.0
        self.udp_recv_speed_kbs = 0.0

    def reset(self) -> None:
        """Resets all metrics and counters to initial zero state."""
        with self._lock:
            self.tcp_bytes_sent = 0
            self.tcp_bytes_received = 0
            self.udp_bytes_sent = 0
            self.udp_bytes_received = 0
            self.tcp_packets_sent = 0
            self.tcp_packets_received = 0
            self.udp_packets_sent = 0
            self.udp_packets_received = 0
            self.tcp_resumed_transfers = 0
            self.tcp_transfers_history.clear()
            self.last_tcp_transfer = None
            self.udp_messages_sent = 0
            self.udp_messages_received = 0
            self.udp_acks_received = 0
            self.udp_retransmissions = 0
            self.udp_ack_timeouts = 0
            self.udp_packets_failed = 0
            self.last_tcp_rtt_ms = 0.0
            self.last_udp_rtt_ms = 0.0
            self.udp_latencies.clear()
            self.start_time = time.time()
            self.last_sample_time = time.time()
            self.last_tcp_sent_sample = 0
            self.last_tcp_recv_sample = 0
            self.last_udp_sent_sample = 0
            self.last_udp_recv_sample = 0
            self.tcp_upload_speed_kbs = 0.0
            self.tcp_download_speed_kbs = 0.0
            self.udp_send_speed_kbs = 0.0
            self.udp_recv_speed_kbs = 0.0

    def record_tcp_send(self, bytes_count: int) -> None:
        with self._lock:
            self.tcp_bytes_sent += bytes_count
            self.tcp_packets_sent += 1

    def record_tcp_recv(self, bytes_count: int) -> None:
        with self._lock:
            self.tcp_bytes_received += bytes_count
            self.tcp_packets_received += 1

    def record_tcp_resume(self) -> None:
        """Increments cumulative counter of resumed transfers."""
        with self._lock:
            self.tcp_resumed_transfers += 1

    def record_tcp_transfer(
        self,
        filename: str,
        filesize: int,
        duration_sec: float,
        throughput_kbs: float,
        status: str,
        checksum_verified: bool,
        is_resumed: bool,
        direction: str = "Upload"
    ) -> Dict[str, Any]:
        """
        Records individual completed or attempted TCP file transfer benchmark.
        Calculates application-level throughput from actual transferred bytes and duration.
        """
        with self._lock:
            if is_resumed:
                self.tcp_resumed_transfers += 1

            record = {
                "filename": filename,
                "filesize": filesize,
                "duration_sec": round(max(0.0001, duration_sec), 4),
                "throughput_kbs": round(throughput_kbs, 2),
                "throughput_mbs": round(throughput_kbs / 1024.0, 3),
                "status": status,
                "checksum_verified": checksum_verified,
                "is_resumed": is_resumed,
                "direction": direction,
                "timestamp": time.time()
            }
            self.last_tcp_transfer = record
            self.tcp_transfers_history.append(record)
            if len(self.tcp_transfers_history) > 50:
                self.tcp_transfers_history.pop(0)

            return record

    def record_udp_send(self, bytes_count: int) -> None:
        with self._lock:
            self.udp_bytes_sent += bytes_count
            self.udp_packets_sent += 1

    def record_udp_recv(self, bytes_count: int) -> None:
        with self._lock:
            self.udp_bytes_received += bytes_count
            self.udp_packets_received += 1

    def record_udp_message_sent(self) -> None:
        """Records an application-level UDP chat message sent."""
        with self._lock:
            self.udp_messages_sent += 1

    def record_udp_message_received(self) -> None:
        """Records an application-level UDP chat message received."""
        with self._lock:
            self.udp_messages_received += 1

    def record_udp_ack(self) -> None:
        """Records an application ACK received for a sent UDP message."""
        with self._lock:
            self.udp_acks_received += 1

    def record_udp_retransmit(self) -> None:
        """Records an application-level message retransmission triggered after ACK timeout."""
        with self._lock:
            self.udp_retransmissions += 1

    def record_udp_ack_timeout(self) -> None:
        """Records an ACK timeout expiration event (1.0s deadline elapsed)."""
        with self._lock:
            self.udp_ack_timeouts += 1

    def record_udp_failure(self) -> None:
        """Records application-observed message loss after max retries exhausted."""
        with self._lock:
            self.udp_packets_failed += 1

    def record_udp_latency(self, latency_ms: float) -> None:
        """
        Records RTT latency in milliseconds measured from socket send time
        to ACK receipt time.
        """
        with self._lock:
            rtt = round(max(0.01, latency_ms), 2)
            self.last_udp_rtt_ms = rtt
            self.udp_latencies.append(rtt)
            if len(self.udp_latencies) > 1000:
                self.udp_latencies.pop(0)

    def update_tcp_rtt(self, rtt_ms: float) -> None:
        with self._lock:
            self.last_tcp_rtt_ms = round(rtt_ms, 2)

    def update_udp_rtt(self, rtt_ms: float) -> None:
        self.record_udp_latency(rtt_ms)

    def get_summary(self) -> Dict[str, Any]:
        """Calculates instantaneous throughput & aggregates telemetry metrics."""
        with self._lock:
            now = time.time()
            elapsed = max(0.001, now - self.last_sample_time)

            if elapsed >= 1.0:
                # Calculate instantaneous speed over last interval
                tcp_sent_diff = self.tcp_bytes_sent - self.last_tcp_sent_sample
                tcp_recv_diff = self.tcp_bytes_received - self.last_tcp_recv_sample
                udp_sent_diff = self.udp_bytes_sent - self.last_udp_sent_sample
                udp_recv_diff = self.udp_bytes_received - self.last_udp_recv_sample

                self.tcp_upload_speed_kbs = round((tcp_sent_diff / 1024.0) / elapsed, 2)
                self.tcp_download_speed_kbs = round((tcp_recv_diff / 1024.0) / elapsed, 2)
                self.udp_send_speed_kbs = round((udp_sent_diff / 1024.0) / elapsed, 2)
                self.udp_recv_speed_kbs = round((udp_recv_diff / 1024.0) / elapsed, 2)

                self.last_sample_time = now
                self.last_tcp_sent_sample = self.tcp_bytes_sent
                self.last_tcp_recv_sample = self.tcp_bytes_received
                self.last_udp_sent_sample = self.udp_bytes_sent
                self.last_udp_recv_sample = self.udp_bytes_received

            # Calculate UDP Latency Percentiles (Min, Max, Avg, P50, P90, P95)
            sample_count = len(self.udp_latencies)
            if sample_count > 0:
                sorted_lats = sorted(self.udp_latencies)
                min_lat = sorted_lats[0]
                max_lat = sorted_lats[-1]
                avg_lat = round(sum(sorted_lats) / sample_count, 2)
                p50_lat = sorted_lats[int((sample_count - 1) * 0.50)]
                p90_lat = sorted_lats[int((sample_count - 1) * 0.90)]
                p95_lat = sorted_lats[int((sample_count - 1) * 0.95)]
            else:
                min_lat = 0.0
                max_lat = 0.0
                avg_lat = 0.0
                p50_lat = 0.0
                p90_lat = 0.0
                p95_lat = 0.0

            # Calculate Application-Observed Message Loss vs Physical Loss
            total_msgs_sent = max(1, self.udp_messages_sent)
            app_loss_pct = round((self.udp_packets_failed / total_msgs_sent) * 100.0, 2)
            app_success_pct = round(100.0 - app_loss_pct, 2)

            return {
                "uptime_seconds": int(now - self.start_time),
                "tcp": {
                    "bytes_sent": self.tcp_bytes_sent,
                    "bytes_received": self.tcp_bytes_received,
                    "packets_sent": self.tcp_packets_sent,
                    "packets_received": self.tcp_packets_received,
                    "upload_speed_kbs": self.tcp_upload_speed_kbs,
                    "download_speed_kbs": self.tcp_download_speed_kbs,
                    "rtt_ms": self.last_tcp_rtt_ms,
                    "resumed_transfers_count": self.tcp_resumed_transfers,
                    "last_transfer": self.last_tcp_transfer,
                    "transfers_history": list(self.tcp_transfers_history[-10:]),
                    "os_managed_note": (
                        "TCP reliability, segment retransmissions, sliding-window flow control, "
                        "and in-order byte stream delivery are handled exclusively by the OS kernel network stack. "
                        "User-space applications read complete byte streams without observing individual TCP ACKs."
                    ),
                    "reliability": "100% (Kernel OS-level ACK)"
                },
                "udp": {
                    "bytes_sent": self.udp_bytes_sent,
                    "bytes_received": self.udp_bytes_received,
                    "packets_sent": self.udp_packets_sent,
                    "packets_received": self.udp_packets_received,
                    "messages_sent": self.udp_messages_sent,
                    "messages_received": self.udp_messages_received,
                    "acks_received": self.udp_acks_received,
                    "retransmissions": self.udp_retransmissions,
                    "ack_timeouts": self.udp_ack_timeouts,
                    "packets_failed": self.udp_packets_failed,
                    "app_loss_count": self.udp_packets_failed,
                    "app_loss_percentage": app_loss_pct,
                    "app_success_percentage": app_success_pct,
                    "send_speed_kbs": self.udp_send_speed_kbs,
                    "recv_speed_kbs": self.udp_recv_speed_kbs,
                    "rtt_ms": self.last_udp_rtt_ms,
                    "loss_percentage": app_loss_pct,
                    "success_percentage": app_success_pct,
                    "latency": {
                        "sample_count": sample_count,
                        "min_ms": min_lat,
                        "max_ms": max_lat,
                        "avg_ms": avg_lat,
                        "p50_ms": p50_lat,
                        "p90_ms": p90_lat,
                        "p95_ms": p95_lat
                    },
                    "app_loss_distinction_note": (
                        "Application-observed message loss measures application messages that remained unacknowledged "
                        "after MAX_RETRIES (3 attempts). This does not directly prove a physical layer 2/3 frame was dropped; "
                        "network delays, receiver busy states, or socket buffer overflows appear identical from user space."
                    )
                }
            }


# Singleton global instance
global_stats = NetworkStatsTracker()
