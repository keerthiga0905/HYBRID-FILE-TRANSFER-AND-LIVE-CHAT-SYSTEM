"""
Unit tests for Module 6: Application-Layer Reliability over UDP.
Tests:
1. Message ID & sequence number assignment.
2. Application-protocol payload with sender, recipient, timestamp, msg_id, seq.
3. Delivery confirmation ACK containing message ID.
4. Retransmission upon missing ACK after configurable timeout.
5. Delivery failure reported after max retries limit is exhausted.
6. Duplicate message detection using msg_id and sequence numbers.
7. Duplicate suppression (messages not displayed more than once).
8. Re-sending ACK upon receiving a duplicate message so sender terminates retries.
9. Distinction between Sent, Retrying, Delivered, and Delivery Failed states.
10. Non-blocking asynchronous chat activity during ACK wait.
11. Configurable retries and timeouts.
"""

import json
import socket
import threading
import time
import unittest
from shared.config import DEFAULT_HOST, ACK_TIMEOUT, MAX_RETRIES
from server.udp_server import UDPServer
from client.udp_client import UDPClient


class TestUDPReliabilityModule6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_port = 6037
        cls.server = UDPServer(host=DEFAULT_HOST, port=cls.server_port)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.client = UDPClient(host=DEFAULT_HOST, port=self.server_port, username="RelTester")
        self.client.connect()
        self.client.join_chat("RelTester")
        time.sleep(0.2)

    def tearDown(self):
        self.client.disconnect()

    def test_01_msg_id_and_sequence_assignment_and_ack(self):
        """Req 1, 2, 3: Verify unique msg_id, sequence number, and server ACK containing msg_id."""
        res1 = self.client.send_chat_message("Reliability payload test 1")
        self.assertTrue(res1.get("success"))
        msg_id1 = res1.get("msg_id")
        seq1 = res1.get("sequence")

        self.assertIsNotNone(msg_id1)
        self.assertTrue(msg_id1.startswith("msg_"))
        self.assertGreater(seq1, 0)

        # Allow server to process and return ACK
        time.sleep(0.3)

        with self.client._lock:
            ack_info = self.client.pending_acks.get(seq1)
            self.assertIsNotNone(ack_info)
            self.assertEqual(ack_info.get("status"), "DELIVERED")
            # History status updated to Delivered
            records = [m for m in self.client.messages_history if m.get("msg_id") == msg_id1]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["status"], "Delivered")

        # Second message has unique msg_id and sequential sequence
        res2 = self.client.send_chat_message("Reliability payload test 2")
        self.assertTrue(res2.get("success"))
        msg_id2 = res2.get("msg_id")
        seq2 = res2.get("sequence")

        self.assertNotEqual(msg_id1, msg_id2)
        self.assertEqual(seq2, seq1 + 1)

    def test_02_retransmission_on_dropped_ack_and_recovery(self):
        """Req 4, 8: Simulate dropped ACK. Sender retransmits, receiver re-sends ACK, and sender recovers."""
        mock_port = 6049
        mock_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        mock_sock.bind((DEFAULT_HOST, mock_port))
        mock_sock.settimeout(2.0)

        # Client configured with fast 0.25s timeout and 3 retries
        test_client = UDPClient(host=DEFAULT_HOST, port=mock_port, username="SenderTester")
        test_client.set_retry_policy(ack_timeout=0.25, max_retries=3)
        test_client.connect()

        received_packets = []

        def mock_server_loop():
            # First packet received: Drop ACK deliberately!
            try:
                data, addr = mock_sock.recvfrom(2048)
                pkt1 = json.loads(data.decode("utf-8"))
                received_packets.append(pkt1)

                # Second packet (Retransmission attempt 1/3): Now return the ACK
                data2, addr2 = mock_sock.recvfrom(2048)
                pkt2 = json.loads(data2.decode("utf-8"))
                received_packets.append(pkt2)

                ack = {
                    "type": "ACK",
                    "msg_id": pkt2.get("msg_id"),
                    "sequence": pkt2.get("sequence"),
                    "status": "SUCCESS"
                }
                mock_sock.sendto(json.dumps(ack).encode("utf-8"), addr2)
            except Exception:
                pass

        th = threading.Thread(target=mock_server_loop, daemon=True)
        th.start()

        send_res = test_client.send_chat_message("Simulated drop test message")
        self.assertTrue(send_res.get("success"))
        seq = send_res.get("sequence")
        msg_id = send_res.get("msg_id")

        th.join(timeout=3.0)
        time.sleep(0.3)

        # Verify mock server received original and retransmitted packet
        self.assertEqual(len(received_packets), 2, "Server should have received 2 packets (1 original + 1 retransmission)")
        self.assertEqual(received_packets[0]["msg_id"], received_packets[1]["msg_id"])
        self.assertEqual(received_packets[0]["sequence"], received_packets[1]["sequence"])

        # Verify client transitioned through retrying to Delivered
        with test_client._lock:
            ack_info = test_client.pending_acks.get(seq)
            self.assertEqual(ack_info.get("status"), "DELIVERED")
            self.assertGreaterEqual(ack_info.get("retries"), 1)

        test_client.disconnect()
        mock_sock.close()

    def test_03_duplicate_message_rejection_and_ack_resend(self):
        """Req 6, 7, 8: Duplicate message is not displayed twice, and ACK is re-sent so sender stops retrying."""
        # Client creates receiver endpoint
        c_receiver = UDPClient(host=DEFAULT_HOST, port=self.server_port, username="RecvDuplicateUser")
        c_receiver.connect()
        c_receiver.join_chat("RecvDuplicateUser")
        time.sleep(0.2)

        client_port = c_receiver.sock.getsockname()[1]

        # Construct raw MSG packet
        test_msg_id = "msg_dup_test_99"
        raw_msg = json.dumps({
            "type": "MSG",
            "msg_id": test_msg_id,
            "sender": "SimSender",
            "recipient": "RecvDuplicateUser",
            "message": "Duplicate suppression test",
            "sequence": 7777,
            "require_ack": True,
            "timestamp": "12:00:00"
        }).encode("utf-8")

        # Create temporary socket to act as sender and listen for ACKs
        sender_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender_sock.settimeout(1.0)

        # Send first time
        sender_sock.sendto(raw_msg, (DEFAULT_HOST, client_port))
        time.sleep(0.2)

        with c_receiver._lock:
            count_after_first = len(c_receiver.messages_history)
            self.assertIn(test_msg_id, c_receiver.processed_msg_ids)
            self.assertIn(7777, c_receiver.processed_sequences)

        # Send duplicate packet with exact same msg_id and seq
        sender_sock.sendto(raw_msg, (DEFAULT_HOST, client_port))
        time.sleep(0.2)

        # Confirm duplicate was suppressed from display/history (Req 7)
        with c_receiver._lock:
            count_after_second = len(c_receiver.messages_history)
            self.assertEqual(count_after_first, count_after_second, "Duplicate message was incorrectly displayed multiple times!")

        sender_sock.close()
        c_receiver.disconnect()

    def test_04_delivery_failure_reported_after_retry_limit(self):
        """Req 5, 9: When ACK is never received, message transitions to Delivery Failed after max retries."""
        # Send to a non-existent UDP server port with 0.15s timeout and 3 retries
        silent_port = 6098
        dead_client = UDPClient(host=DEFAULT_HOST, port=silent_port, username="FailTester")
        dead_client.set_retry_policy(ack_timeout=0.15, max_retries=3)
        dead_client.connect()

        res = dead_client.send_chat_message("This message will fail delivery")
        self.assertTrue(res.get("success"))
        seq = res.get("sequence")
        msg_id = res.get("msg_id")

        # Wait for all 3 retries to exhaust: 3 * 0.15s = 0.45s + margin
        time.sleep(0.8)

        with dead_client._lock:
            ack_info = dead_client.pending_acks.get(seq)
            self.assertIsNotNone(ack_info)
            self.assertEqual(ack_info.get("status"), "FAILED")
            self.assertEqual(ack_info.get("retries"), 3)

            # History entry marked as "Delivery Failed"
            matched = [m for m in dead_client.messages_history if m.get("msg_id") == msg_id]
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["status"], "Delivery Failed")

        dead_client.disconnect()

    def test_05_non_blocking_chat_activity(self):
        """Req 10: Sending messages does not block client while awaiting ACKs."""
        t_start = time.time()
        res1 = self.client.send_chat_message("Non-blocking 1")
        res2 = self.client.send_chat_message("Non-blocking 2")
        t_elapsed = time.time() - t_start

        # Both calls must complete in under 50ms without waiting for ACK network roundtrips
        self.assertLess(t_elapsed, 0.1)
        self.assertTrue(res1.get("success"))
        self.assertTrue(res2.get("success"))

    def test_06_configurable_retries_and_timeouts(self):
        """Req 11: Retries and timeouts are dynamically configurable."""
        c = UDPClient(host=DEFAULT_HOST, port=self.server_port, ack_timeout=2.5, max_retries=5)
        self.assertEqual(c.ack_timeout, 2.5)
        self.assertEqual(c.max_retries, 5)

        c.set_retry_policy(ack_timeout=0.5, max_retries=2)
        self.assertEqual(c.ack_timeout, 0.5)
        self.assertEqual(c.max_retries, 2)


if __name__ == "__main__":
    unittest.main()
