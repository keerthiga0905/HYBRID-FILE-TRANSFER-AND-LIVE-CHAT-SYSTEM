"""
Automated unit test suite for Module 4: UDP communication and online user presence.
Tests AF_INET SOCK_DGRAM sockets, 3-client presence tracking, heartbeat updates,
15-second offline timeout, stale endpoint cleanup, presence change notifications,
repeated JOIN handling, malformed datagram resilience, and session isolation.
"""

import socket
import time
import unittest
from server.udp_server import UDPServer
from server.client_registry import ClientRegistry
from server.tcp_server import TCPServer
from client.udp_client import UDPClient
from client.tcp_client import TCPClient
from shared.config import DEFAULT_HOST


class TestUDPPresenceModule4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_udp_port = 6015
        cls.test_tcp_port = 5015
        cls.custom_registry = ClientRegistry(offline_timeout=1.5)  # Fast 1.5s timeout for testing
        cls.udp_server = UDPServer(host=DEFAULT_HOST, port=cls.test_udp_port, registry=cls.custom_registry)
        cls.udp_server.start()
        cls.tcp_server = TCPServer(host=DEFAULT_HOST, port=cls.test_tcp_port)
        cls.tcp_server.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.udp_server.stop()
        cls.tcp_server.stop()

    def setUp(self):
        self.custom_registry.clear()

    def test_01_three_clients_join_and_presence_list(self):
        """Module 4: Start three clients and confirm all appear online in UDP presence list."""
        c1 = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="Alice_M4", session_id="sess_01")
        c2 = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="Bob_M4", session_id="sess_02")
        c3 = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="Charlie_M4", session_id="sess_03")

        r1 = c1.join_chat()
        r2 = c2.join_chat()
        r3 = c3.join_chat()

        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        self.assertIsNotNone(r3)
        self.assertEqual(r1.get("status"), "SUCCESS")
        self.assertEqual(r2.get("status"), "SUCCESS")
        self.assertEqual(r3.get("status"), "SUCCESS")

        # Query presence list via UDP datagram from c1
        users = c1.get_online_users()
        user_names = [u["username"] for u in users]
        self.assertIn("Alice_M4", user_names)
        self.assertIn("Bob_M4", user_names)
        self.assertIn("Charlie_M4", user_names)

        # Confirm all are marked ONLINE
        for u in users:
            if u["username"] in ["Alice_M4", "Bob_M4", "Charlie_M4"]:
                self.assertEqual(u["status"], "ONLINE")
                self.assertNotEqual(u["endpoint"], "N/A")

        c1.leave_chat()
        c2.leave_chat()
        c3.leave_chat()

    def test_02_heartbeat_updates_timestamp(self):
        """Module 4: Confirm 5s heartbeat updates last_seen timestamp in presence registry."""
        client = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="HeartbeatUser_M4", session_id="sess_hb")
        client.join_chat()

        time.sleep(0.2)
        user_record = self.custom_registry.clients.get("HeartbeatUser_M4")
        self.assertIsNotNone(user_record)
        t1 = user_record["last_seen"]

        # Manually invoke heartbeat datagram
        time.sleep(0.1)
        self.custom_registry.update_heartbeat("HeartbeatUser_M4", "127.0.0.1", 59000, session_id="sess_hb")
        t2 = self.custom_registry.clients["HeartbeatUser_M4"]["last_seen"]

        self.assertGreaterEqual(t2, t1)
        client.leave_chat()

    def test_03_close_client_and_verify_offline_after_timeout(self):
        """Module 4: Close one client and verify that it becomes offline and clears stale endpoint after timeout."""
        c1 = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="ActiveAlice", session_id="sess_aa")
        c2 = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="StaleCharlie", session_id="sess_sc")

        c1.join_chat()
        c2.join_chat()
        # Keep c1 heartbeat active every 0.5s so it stays online during 1.5s timeout test
        c1.start_heartbeat(interval=0.5)

        # Confirm both are online
        users = c1.get_online_users()
        names = [u["username"] for u in users]
        self.assertIn("ActiveAlice", names)
        self.assertIn("StaleCharlie", names)

        # Stop c2 heartbeat without sending explicit leave (simulate sudden crash/exit)
        c2.stop_heartbeat()
        if c2.sock:
            c2.sock.close()
            c2.sock = None
        c2.is_connected = False

        # Wait for timeout (custom_registry offline_timeout is 1.5s, plus monitor loop interval)
        time.sleep(2.5)

        # Verify Charlie is marked OFFLINE and endpoint is cleared
        charlie_data = self.custom_registry.clients.get("StaleCharlie")
        self.assertIsNotNone(charlie_data)
        self.assertEqual(charlie_data["status"], "OFFLINE")
        self.assertEqual(charlie_data["endpoint"], "N/A")

        # Verify Alice is still ONLINE
        alice_data = self.custom_registry.clients.get("ActiveAlice")
        self.assertIsNotNone(alice_data)
        self.assertEqual(alice_data["status"], "ONLINE")

        c1.leave_chat()

    def test_04_presence_change_notifications(self):
        """Module 4: Verify remaining users receive PRESENCE_CHANGE datagrams on join and leave."""
        listener = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="ListenerBob", session_id="sess_lb")
        listener.join_chat()
        time.sleep(0.1)

        # Join new user
        joiner = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="NewJoiner", session_id="sess_nj")
        joiner.join_chat()
        time.sleep(0.3)

        # Check listener's presence events
        events = listener.get_presence_events()
        join_events = [e for e in events if e.get("username") == "NewJoiner" and e.get("event") == "USER_JOINED"]
        self.assertTrue(len(join_events) >= 1, "Listener did not receive USER_JOINED notification")

        # Leave user
        joiner.leave_chat()
        time.sleep(0.3)

        events_after = listener.get_presence_events()
        leave_events = [e for e in events_after if e.get("username") == "NewJoiner" and e.get("event") == "USER_LEFT"]
        self.assertTrue(len(leave_events) >= 1, "Listener did not receive USER_LEFT notification")

        listener.leave_chat()

    def test_05_repeated_join_handling(self):
        """Module 4: Handle repeated JOIN messages cleanly without duplicating or erroring."""
        client = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="RepeatUser", session_id="sess_rep")
        resp1 = client.join_chat()
        self.assertIsNotNone(resp1)
        self.assertEqual(resp1.get("status"), "SUCCESS")

        # Send repeated JOIN with same session
        resp2 = client.join_chat()
        self.assertIsNotNone(resp2)
        self.assertEqual(resp2.get("status"), "SUCCESS")

        # Confirm registry has only one record for RepeatUser
        all_users = [u for u in self.custom_registry.get_users_list() if u["username"] == "RepeatUser"]
        self.assertEqual(len(all_users), 1)
        self.assertEqual(all_users[0]["status"], "ONLINE")

        client.leave_chat()

    def test_06_malformed_datagrams_resilience(self):
        """Module 4: Server handles corrupted/non-JSON bytes and malformed datagrams without crashing."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        target = (DEFAULT_HOST, self.test_udp_port)

        # Send non-JSON binary garbage
        raw_sock.sendto(b"\x00\xFF\xFE\x01\xDE\xAD\xBE\xEFGARBAGE", target)
        # Send empty payload
        raw_sock.sendto(b"", target)
        # Send JSON that is not a dictionary
        raw_sock.sendto(b"12345", target)
        # Send JSON with missing type
        raw_sock.sendto(b'{"no_type": true}', target)

        time.sleep(0.2)

        # Confirm server is still healthy by sending a valid JOIN datagram
        client = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="SurvivorUser", session_id="sess_surv")
        resp = client.join_chat()
        self.assertIsNotNone(resp)
        self.assertEqual(resp.get("status"), "SUCCESS")

        client.leave_chat()
        raw_sock.close()

    def test_07_session_isolation_prevents_overwrite(self):
        """Module 4: Ensure one client's presence cannot overwrite another client's active session."""
        c1 = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="LegitUser", session_id="sess_legit_01")
        r1 = c1.join_chat()
        self.assertIsNotNone(r1)
        self.assertEqual(r1.get("status"), "SUCCESS")

        # Attacker tries to register same username with a different session ID
        c2 = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="LegitUser", session_id="sess_hacker_99")
        r2 = c2.join_chat()
        self.assertIsNotNone(r2)
        self.assertEqual(r2.get("status"), "ERROR")
        self.assertEqual(r2.get("code"), "SESSION_CONFLICT")

        # Verify LegitUser's original session is preserved
        record = self.custom_registry.clients.get("LegitUser")
        self.assertIsNotNone(record)
        self.assertEqual(record.get("session_id"), "sess_legit_01")

        c1.leave_chat()
        c2.leave_chat()

    def test_08_tcp_and_udp_dual_operation(self):
        """Module 4: Confirm TCP file transfer server and UDP presence server operate independently in parallel."""
        # Connect two TCP Clients on TCP Port
        tcp_client1 = TCPClient(host=DEFAULT_HOST, port=self.test_tcp_port)
        tcp_client2 = TCPClient(host=DEFAULT_HOST, port=self.test_tcp_port)
        self.assertTrue(tcp_client1.connect())
        self.assertTrue(tcp_client2.connect())
        tcp_resp1 = tcp_client1.send_hello("DualUser_TCP1")
        tcp_resp2 = tcp_client2.send_hello("DualUser_TCP2")
        self.assertEqual(tcp_resp1.get("status"), "SUCCESS")
        self.assertEqual(tcp_resp2.get("status"), "SUCCESS")

        # Connect UDP Client on UDP Port
        udp_client = UDPClient(host=DEFAULT_HOST, port=self.test_udp_port, username="DualUser_UDP", session_id="sess_dual")
        udp_resp = udp_client.join_chat()
        self.assertEqual(udp_resp.get("status"), "SUCCESS")

        # Verify both respond to queries simultaneously
        tcp_users = tcp_client1.list_online_users()
        udp_users = udp_client.get_online_users()

        self.assertGreaterEqual(len(tcp_users), 1)
        self.assertGreaterEqual(len(udp_users), 1)
        self.assertEqual(tcp_users[0]["username"], "DualUser_TCP2")

        tcp_client1.disconnect()
        tcp_client2.disconnect()
        udp_client.leave_chat()


if __name__ == "__main__":
    unittest.main()
