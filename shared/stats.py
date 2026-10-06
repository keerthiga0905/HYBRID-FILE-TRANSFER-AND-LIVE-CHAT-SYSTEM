"""
Network Stats Tracker - Measures live throughput, RTT latency, packet counts,
and UDP reliability statistics across TCP and UDP sockets.
"""

import time
import threading
from typing import Dict, Any


class NetworkStatsTracker:
    """
    Thread-safe network metrics collector for TCP file transfer & UDP live chat.
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

        # UDP Reliability Metrics
        self.udp_acks_received = 0
        self.udp_retransmissions = 0
        self.udp_packets_failed = 0

        # Latency (RTT) measurements in ms
        self.last_tcp_rtt_ms = 0.0
        self.last_udp_rtt_ms = 0.0

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

    def record_tcp_send(self, bytes_count: int) -> None:
        with self._lock:
            self.tcp_bytes_sent += bytes_count
            self.tcp_packets_sent += 1

    def record_tcp_recv(self, bytes_count: int) -> None:
        with self._lock:
            self.tcp_bytes_received += bytes_count
            self.tcp_packets_received += 1

    def record_udp_send(self, bytes_count: int) -> None:
        with self._lock:
            self.udp_bytes_sent += bytes_count
            self.udp_packets_sent += 1

    def record_udp_recv(self, bytes_count: int) -> None:
        with self._lock:
            self.udp_bytes_received += bytes_count
            self.udp_packets_received += 1

    def record_udp_ack(self) -> None:
        with self._lock:
            self.udp_acks_received += 1

    def record_udp_retransmit(self) -> None:
        with self._lock:
            self.udp_retransmissions += 1

    def record_udp_failure(self) -> None:
        with self._lock:
            self.udp_packets_failed += 1

    def update_tcp_rtt(self, rtt_ms: float) -> None:
        with self._lock:
            self.last_tcp_rtt_ms = round(rtt_ms, 2)

    def update_udp_rtt(self, rtt_ms: float) -> None:
        with self._lock:
            self.last_udp_rtt_ms = round(rtt_ms, 2)

    def get_summary(self) -> Dict[str, Any]:
        """Calculates instantaneous throughput & aggregates metrics."""
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

            # Calculate UDP Packet Loss / Success Rate
            total_udp_sent = max(1, self.udp_packets_sent)
            udp_loss_pct = round((self.udp_packets_failed / total_udp_sent) * 100.0, 2)
            udp_success_pct = round(100.0 - udp_loss_pct, 2)

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
                    "reliability": "100% (Guaranteed OS-level ACK)"
                },
                "udp": {
                    "bytes_sent": self.udp_bytes_sent,
                    "bytes_received": self.udp_bytes_received,
                    "packets_sent": self.udp_packets_sent,
                    "packets_received": self.udp_packets_received,
                    "acks_received": self.udp_acks_received,
                    "retransmissions": self.udp_retransmissions,
                    "packets_failed": self.udp_packets_failed,
                    "send_speed_kbs": self.udp_send_speed_kbs,
                    "recv_speed_kbs": self.udp_recv_speed_kbs,
                    "rtt_ms": self.last_udp_rtt_ms,
                    "loss_percentage": udp_loss_pct,
                    "success_percentage": udp_success_pct
                }
            }


# Singleton global instance
global_stats = NetworkStatsTracker()
