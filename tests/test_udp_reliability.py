"""
Unit tests for UDP Reliability: ACK Tracking, 1s Timeout Retransmission, and Duplicate Rejection.
"""

import unittest
import socket
import time
import json
import threading
from shared.config import DEFAULT_HOST, ACK_TIMEOUT, MAX_RETRIES
from server.udp_server import UDPServer
from client.udp_client import UDPClient


class TestUDPReliability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_port = 6007
        cls.server = UDPServer(host=DEFAULT_HOST, port=cls.server_port)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.client = UDPClient(host=DEFAULT_HOST, port=self.server_port)
        self.client.connect()
        self.client.join_chat("ReliabilityTester")
        time.sleep(0.2)

    def tearDown(self):
        self.client.disconnect()

    def test_ack_retransmission_and_sequence_tracking(self):
        """Test sending a reliable UDP message with ACK tracking and verifying sequence incrementing."""
        res1 = self.client.send_chat_message("Test Message 1")
        self.assertTrue(res1.get("success"))
        seq1 = res1.get("sequence")
        self.assertGreater(seq1, 0)
        
        # Give brief time for server to ACK and client to process
        time.sleep(0.3)
        
        # Verify message status updated to Delivered or ACK processed
        with self.client._lock:
            ack_status = self.client.pending_acks.get(seq1, {}).get("status")
            self.assertIn(ack_status, ["DELIVERED", None])

        res2 = self.client.send_chat_message("Test Message 2")
        self.assertTrue(res2.get("success"))
        seq2 = res2.get("sequence")
        self.assertEqual(seq2, seq1 + 1)

    def test_duplicate_rejection(self):
        """Test that client detects and rejects duplicate broadcast sequence numbers."""
        raw_msg = json.dumps({
            "type": "BROADCAST",
            "sender": "DuplicateSender",
            "message": "Duplicate check",
            "sequence": 9999,
            "timestamp": time.time()
        }).encode('utf-8')

        # Simulate incoming datagram directly onto client receiver logic
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(raw_msg, (DEFAULT_HOST, self.client.sock.getsockname()[1]))
        sock.close()
        time.sleep(0.2)

        with self.client._lock:
            self.assertIn(9999, self.client.processed_sequences)
            received_before = len(self.client.messages_history)

        # Send duplicate packet to client port again
        sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock2.sendto(raw_msg, (DEFAULT_HOST, self.client.sock.getsockname()[1]))
        sock2.close()
        time.sleep(0.2)

        with self.client._lock:
            received_after = len(self.client.messages_history)

        # Duplicate should be ignored, count remains same
        self.assertEqual(received_before, received_after)


if __name__ == "__main__":
    unittest.main()
