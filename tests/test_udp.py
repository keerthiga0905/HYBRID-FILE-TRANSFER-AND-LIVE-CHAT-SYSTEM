"""
Automated unit test suite for UDP Server Datagram Socket, Client Registry, and Heartbeat Presence (Phase 4).
Tests JOIN datagrams, heartbeat timestamp updates, and 15-second offline presence timeouts.
"""

import time
import unittest
from server.udp_server import UDPServer
from server.client_registry import registry
from client.udp_client import UDPClient
from shared.config import DEFAULT_HOST


class TestUDPPresence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 6005
        cls.server = UDPServer(host=DEFAULT_HOST, port=cls.test_port)
        cls.server.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_01_udp_join_and_registry(self):
        """Verify UDP client JOIN datagram registers user in server presence registry."""
        client = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="TestUserA")
        resp = client.join_chat()

        self.assertIsNotNone(resp, "UDP Server failed to respond to JOIN datagram")
        self.assertEqual(resp.get("status"), "SUCCESS")
        self.assertEqual(resp.get("type"), "JOIN_ACK")

        users = registry.get_users_list()
        user_names = [u["username"] for u in users]
        self.assertIn("TestUserA", user_names)

        client.leave_chat()

    def test_02_udp_heartbeat_updates_timestamp(self):
        """Verify UDP heartbeat updates client last_seen timestamp."""
        client = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="HeartbeatUser")
        client.join_chat()

        users_before = registry.get_users_list()
        user_data_before = next((u for u in users_before if u["username"] == "HeartbeatUser"), None)
        self.assertIsNotNone(user_data_before)
        self.assertEqual(user_data_before["status"], "ONLINE")

        client.leave_chat()

    def test_03_presence_timeout_detection(self):
        """Verify user is marked OFFLINE after 15 seconds without heartbeat."""
        registry.register_client("StaleUser", "127.0.0.1", 59999)

        # Manually backdate last_seen to 20 seconds ago
        registry.clients["StaleUser"]["last_seen"] = time.time() - 20.0

        # Trigger check_timeouts
        newly_offline = registry.check_timeouts()
        self.assertIn("StaleUser", newly_offline)

        users = registry.get_users_list()
        stale_user = next((u for u in users if u["username"] == "StaleUser"), None)
        self.assertIsNotNone(stale_user)
        self.assertEqual(stale_user["status"], "OFFLINE")


if __name__ == "__main__":
    unittest.main()
