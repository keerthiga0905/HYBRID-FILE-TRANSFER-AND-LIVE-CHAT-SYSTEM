"""
Unit tests for Module 8 Network Statistics & Computer Networks Demonstration Tracker.
Verifies TCP transfer benchmarking, UDP reliability telemetry, latency percentiles,
and application-loss distinctions.
"""

import unittest
from shared.stats import NetworkStatsTracker


class TestNetworkStats(unittest.TestCase):
    def setUp(self):
        self.tracker = NetworkStatsTracker()

    def test_record_tcp_metrics(self):
        """Test recording TCP sent and received byte throughput."""
        self.tracker.record_tcp_send(4096)
        self.tracker.record_tcp_send(4096)
        self.tracker.record_tcp_recv(2048)

        summary = self.tracker.get_summary()
        self.assertEqual(summary["tcp"]["bytes_sent"], 8192)
        self.assertEqual(summary["tcp"]["bytes_received"], 2048)
        self.assertEqual(summary["tcp"]["packets_sent"], 2)
        self.assertEqual(summary["tcp"]["packets_received"], 1)

    def test_record_tcp_transfer_benchmarks(self):
        """Module 8: Test TCP transfer duration, application throughput, SHA-256, and resume tracking."""
        # Initial transfer (fresh upload)
        rec1 = self.tracker.record_tcp_transfer(
            filename="document.pdf",
            filesize=1048576,  # 1 MB
            duration_sec=0.25,
            throughput_kbs=4194.3,
            status="Completed",
            checksum_verified=True,
            is_resumed=False,
            direction="Upload"
        )
        self.assertEqual(rec1["filename"], "document.pdf")
        self.assertEqual(rec1["duration_sec"], 0.25)
        self.assertTrue(rec1["checksum_verified"])
        self.assertFalse(rec1["is_resumed"])

        # Second transfer (resumed download)
        rec2 = self.tracker.record_tcp_transfer(
            filename="video.mp4",
            filesize=10485760,  # 10 MB
            duration_sec=1.5,
            throughput_kbs=3495.2,
            status="Completed",
            checksum_verified=True,
            is_resumed=True,
            direction="Download"
        )
        self.assertTrue(rec2["is_resumed"])

        summary = self.tracker.get_summary()
        tcp_stats = summary["tcp"]
        self.assertEqual(tcp_stats["resumed_transfers_count"], 1)
        self.assertEqual(tcp_stats["last_transfer"]["filename"], "video.mp4")
        self.assertEqual(len(tcp_stats["transfers_history"]), 2)
        self.assertIn("OS kernel network stack", tcp_stats["os_managed_note"])

    def test_record_udp_message_and_reliability_metrics(self):
        """Module 8: Test UDP messages sent/received, ACKs, retransmissions, timeouts, and loss."""
        # 10 messages sent, 8 ACKs received, 2 retransmissions, 2 ACK timeouts, 1 failed message
        for _ in range(10):
            self.tracker.record_udp_message_sent()
            self.tracker.record_udp_send(256)

        for _ in range(8):
            self.tracker.record_udp_message_received()
            self.tracker.record_udp_recv(256)
            self.tracker.record_udp_ack()

        self.tracker.record_udp_ack_timeout()
        self.tracker.record_udp_retransmit()
        self.tracker.record_udp_ack_timeout()
        self.tracker.record_udp_retransmit()
        self.tracker.record_udp_failure()

        summary = self.tracker.get_summary()
        udp_stats = summary["udp"]

        self.assertEqual(udp_stats["messages_sent"], 10)
        self.assertEqual(udp_stats["messages_received"], 8)
        self.assertEqual(udp_stats["acks_received"], 8)
        self.assertEqual(udp_stats["retransmissions"], 2)
        self.assertEqual(udp_stats["ack_timeouts"], 2)
        self.assertEqual(udp_stats["app_loss_count"], 1)
        self.assertEqual(udp_stats["app_loss_percentage"], 10.0)
        self.assertEqual(udp_stats["app_success_percentage"], 90.0)
        self.assertIn("Application-observed message loss", udp_stats["app_loss_distinction_note"])

    def test_udp_latency_percentiles(self):
        """Module 8: Test average and percentile (Min, Max, Avg, P50, P90, P95) RTT latency."""
        # Record 20 samples from 1.0ms to 20.0ms
        sample_rtts = [float(i) for i in range(1, 21)]
        for rtt in sample_rtts:
            self.tracker.record_udp_latency(rtt)

        summary = self.tracker.get_summary()
        lat = summary["udp"]["latency"]

        self.assertEqual(lat["sample_count"], 20)
        self.assertEqual(lat["min_ms"], 1.0)
        self.assertEqual(lat["max_ms"], 20.0)
        self.assertEqual(lat["avg_ms"], 10.5)
        self.assertEqual(lat["p50_ms"], 10.0)
        self.assertEqual(lat["p90_ms"], 18.0)
        self.assertEqual(lat["p95_ms"], 19.0)

    def test_empty_latency_handling(self):
        """Test default values when no latency samples have been recorded yet."""
        summary = self.tracker.get_summary()
        lat = summary["udp"]["latency"]
        self.assertEqual(lat["sample_count"], 0)
        self.assertEqual(lat["avg_ms"], 0.0)
        self.assertEqual(lat["p50_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
