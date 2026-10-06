"""
Unit tests for Network Monitor Statistics Tracker.
"""

import unittest
import time
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

    def test_record_udp_reliability_metrics(self):
        """Test recording UDP packet count, ACKs, retransmissions, and loss rate."""
        self.tracker.record_udp_send(512)
        self.tracker.record_udp_send(512)
        self.tracker.record_udp_ack()
        self.tracker.record_udp_retransmit()
        self.tracker.record_udp_failure()

        summary = self.tracker.get_summary()
        self.assertEqual(summary["udp"]["bytes_sent"], 1024)
        self.assertEqual(summary["udp"]["acks_received"], 1)
        self.assertEqual(summary["udp"]["retransmissions"], 1)
        self.assertEqual(summary["udp"]["packets_failed"], 1)
        self.assertGreater(summary["udp"]["loss_percentage"], 0.0)


if __name__ == "__main__":
    unittest.main()
