"""
Automated unit test suite for UDP Live Chat Datagram Messaging & Server Broadcast (Phase 5).
Tests MSG datagram handling, sequence numbering, server broadcast to online clients, and message size limits.
"""

import time
import unittest
from server.udp_server import UDPServer
from client.udp_client import UDPClient
from shared.config import DEFAULT_HOST


class TestUDPChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 6006
        cls.server = UDPServer(host=DEFAULT_HOST, port=cls.test_port)
        cls.server.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_01_send_and_broadcast_chat_message(self):
        """Verify client sends UDP MSG datagram and receives server broadcast."""
        client_a = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Alice")
        client_b = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Bob")

        self.assertIsNotNone(client_a.join_chat())
        self.assertIsNotNone(client_b.join_chat())
        time.sleep(0.2)

        # Alice sends chat message over UDP datagram
        res = client_a.send_chat_message("Hello from Alice over UDP!")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("message"), "Hello from Alice over UDP!")

        time.sleep(0.5)

        # Verify Bob received broadcast datagram
        b_messages = client_b.get_chat_history()
        self.assertTrue(len(b_messages) > 0, "Bob did not receive UDP broadcast datagram")
        self.assertEqual(b_messages[0]["sender"], "Alice")
        self.assertEqual(b_messages[0]["message"], "Hello from Alice over UDP!")

        client_a.leave_chat()
        client_b.leave_chat()

    def test_02_oversized_message_truncation(self):
        """Verify server truncates oversized chat messages exceeding 1024 character limit."""
        client = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="LongTextUser")
        client.join_chat()

        huge_message = "Z" * 2000
        res = client.send_chat_message(huge_message)
        self.assertTrue(res.get("success"))
        self.assertEqual(len(res.get("message")), 1024, "Client should truncate message to 1024 chars")

        client.leave_chat()


if __name__ == "__main__":
    unittest.main()
