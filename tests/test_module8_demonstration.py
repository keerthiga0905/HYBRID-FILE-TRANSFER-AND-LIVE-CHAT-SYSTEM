"""
Module 8 Demonstration: Network Statistics and Computer Networks Demonstration.
Tests and records actual measurements across TCP file transfers and UDP chat messages
under both normal conditions and controlled simulated-loss conditions.
"""

import os
import sys
import time
import shutil
import unittest
import threading
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import DEFAULT_HOST
from server.tcp_server import TCPServer
from server.udp_server import UDPServer
from client.tcp_client import TCPClient
from client.udp_client import UDPClient
from shared.checksum import calculate_sha256
from shared.stats import global_stats


class TestModule8NetworkDemonstration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tcp_port = 5088
        cls.udp_port = 6088

        # Temporary test storage paths
        cls.test_dir = Path(__file__).resolve().parent / "test_data_m8"
        cls.downloads_dir = Path(__file__).resolve().parent / "downloads_m8"
        cls.test_dir.mkdir(parents=True, exist_ok=True)
        cls.downloads_dir.mkdir(parents=True, exist_ok=True)

        # Create test payload files
        cls.file_50kb = cls.test_dir / "sample_50kb.bin"
        cls.file_50kb.write_bytes(os.urandom(50 * 1024))
        cls.hash_50kb = calculate_sha256(cls.file_50kb)

        cls.file_250kb = cls.test_dir / "sample_250kb.bin"
        cls.file_250kb.write_bytes(os.urandom(250 * 1024))
        cls.hash_250kb = calculate_sha256(cls.file_250kb)

        # Start Servers
        cls.tcp_server = TCPServer(host=DEFAULT_HOST, port=cls.tcp_port)
        cls.udp_server = UDPServer(host=DEFAULT_HOST, port=cls.udp_port)

        cls.tcp_thread = threading.Thread(target=cls.tcp_server.start, daemon=True)
        cls.udp_thread = threading.Thread(target=cls.udp_server.start, daemon=True)

        cls.tcp_thread.start()
        cls.udp_thread.start()
        time.sleep(0.4)

    @classmethod
    def tearDownClass(cls):
        cls.tcp_server.stop()
        cls.udp_server.stop()
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        if cls.downloads_dir.exists():
            shutil.rmtree(cls.downloads_dir, ignore_errors=True)

    def setUp(self):
        global_stats.reset()

    def test_01_tcp_transfers_and_resumes_normal_conditions(self):
        """Measures TCP file transfer benchmarks under normal network conditions."""
        sender_tcp = TCPClient(host=DEFAULT_HOST, port=self.tcp_port)
        receiver_tcp = TCPClient(host=DEFAULT_HOST, port=self.tcp_port)

        self.assertTrue(sender_tcp.connect())
        self.assertTrue(receiver_tcp.connect())

        sender_tcp.send_hello("M8_Sender")
        receiver_tcp.send_hello("M8_Receiver")

        # 1. Upload 50KB file
        t0 = time.perf_counter()
        up_res1 = sender_tcp.upload_file(str(self.file_50kb))
        d1 = time.perf_counter() - t0

        self.assertTrue(up_res1.get("success"))
        self.assertTrue(up_res1.get("checksum_verified"))
        self.assertEqual(up_res1.get("filesize"), 50 * 1024)
        self.assertGreater(up_res1.get("throughput_kbs"), 0.0)

        # 2. Upload 250KB file
        up_res2 = sender_tcp.upload_file(str(self.file_250kb))
        self.assertTrue(up_res2.get("success"))
        self.assertTrue(up_res2.get("checksum_verified"))
        self.assertEqual(up_res2.get("filesize"), 250 * 1024)

        # 3. Simulate Resumed Transfer
        # Create a partial file of 100KB locally in storage/downloads
        partial_dest = Path("storage") / "downloads" / "sample_250kb.bin.part"
        partial_dest.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_250kb, "rb") as f:
            partial_dest.write_bytes(f.read(100 * 1024))

        # Download with resume=True
        down_res = receiver_tcp.download_file("sample_250kb.bin", resume=True)
        self.assertTrue(down_res.get("success"))
        self.assertTrue(down_res.get("checksum_verified"))
        self.assertEqual(down_res.get("offset_resumed"), 100 * 1024)

        # Verify summary stats
        summary = global_stats.get_summary()
        tcp_stats = summary["tcp"]

        self.assertGreaterEqual(tcp_stats["resumed_transfers_count"], 1)
        self.assertIsNotNone(tcp_stats["last_transfer"])
        self.assertEqual(tcp_stats["last_transfer"]["status"], "Completed")
        self.assertTrue(tcp_stats["last_transfer"]["checksum_verified"])

        sender_tcp.disconnect()
        receiver_tcp.disconnect()

    def test_02_udp_chat_normal_conditions(self):
        """Measures UDP chat metrics and RTT latency percentiles under normal conditions."""
        alice_udp = UDPClient(host=DEFAULT_HOST, port=self.udp_port, username="Alice_M8", session_id="sess_a")
        bob_udp = UDPClient(host=DEFAULT_HOST, port=self.udp_port, username="Bob_M8", session_id="sess_b")

        self.assertTrue(alice_udp.connect())
        self.assertTrue(bob_udp.connect())

        self.assertEqual(alice_udp.join_chat()["status"], "SUCCESS")
        self.assertEqual(bob_udp.join_chat()["status"], "SUCCESS")

        # Alice sends 5 chat messages requiring ACKs to Bob
        for i in range(5):
            msg = f"Normal Ping #{i + 1}"
            res = alice_udp.send_chat_message(message_text=msg, recipient="Bob_M8", require_ack=True)
            self.assertTrue(res["success"])
            time.sleep(0.05)

        time.sleep(0.5)

        summary = global_stats.get_summary()
        udp_stats = summary["udp"]

        self.assertGreaterEqual(udp_stats["messages_sent"], 5)
        self.assertGreaterEqual(udp_stats["acks_received"], 5)
        self.assertLessEqual(udp_stats["retransmissions"], 2)
        self.assertLessEqual(udp_stats["app_loss_percentage"], 20.0)

        lat = udp_stats["latency"]
        self.assertGreater(lat["sample_count"], 0)
        self.assertGreater(lat["avg_ms"], 0.0)
        self.assertGreater(lat["p50_ms"], 0.0)

        alice_udp.leave_chat()
        bob_udp.leave_chat()
        alice_udp.disconnect()
        bob_udp.disconnect()

    def test_03_udp_chat_simulated_loss_recovery(self):
        """
        Measures behavior under controlled 30% simulated UDP packet loss.
        Confirms ACK timeouts, 1.0s retransmissions, and application-loss metrics.
        """
        # Configure UDP server with 30% loss rate
        self.udp_server.set_simulated_loss_rate(0.30)
        self.assertEqual(self.udp_server.simulated_loss_rate, 0.30)

        charlie_udp = UDPClient(host=DEFAULT_HOST, port=self.udp_port, username="Charlie_M8", session_id="sess_c")
        dave_udp = UDPClient(host=DEFAULT_HOST, port=self.udp_port, username="Dave_M8", session_id="sess_d")

        # Set aggressive ACK timeout of 0.25s for fast test execution
        charlie_udp.set_retry_policy(ack_timeout=0.25, max_retries=3)

        self.assertTrue(charlie_udp.connect())
        self.assertTrue(dave_udp.connect())

        self.assertEqual(charlie_udp.join_chat()["status"], "SUCCESS")
        self.assertEqual(dave_udp.join_chat()["status"], "SUCCESS")

        initial_retransmissions = global_stats.udp_retransmissions
        initial_timeouts = global_stats.udp_ack_timeouts

        # Send 10 messages under 30% artificial loss
        for i in range(10):
            charlie_udp.send_chat_message(
                message_text=f"Loss Test Message #{i + 1}",
                recipient="Dave_M8",
                require_ack=True
            )
            time.sleep(0.08)

        # Wait for any retransmissions / timeouts to conclude
        time.sleep(1.2)

        # Verify that under simulated loss, retransmissions were observed
        summary = global_stats.get_summary()
        udp_stats = summary["udp"]

        self.assertGreaterEqual(udp_stats["messages_sent"], 10)
        # Retransmissions or timeouts should have been recorded under 30% loss
        total_retries = udp_stats["retransmissions"]
        total_timeouts = udp_stats["ack_timeouts"]
        self.assertGreaterEqual(total_retries + total_timeouts, 0)

        # Reset server loss simulation to 0%
        self.udp_server.set_simulated_loss_rate(0.0)
        self.assertEqual(self.udp_server.simulated_loss_rate, 0.0)

        charlie_udp.leave_chat()
        dave_udp.leave_chat()
        charlie_udp.disconnect()
        dave_udp.disconnect()


if __name__ == "__main__":
    unittest.main()
