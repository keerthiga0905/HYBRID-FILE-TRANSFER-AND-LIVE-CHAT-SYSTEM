"""
Automated unit test suite for Module 5: Complete UDP Live Chat System.
Tests 3-client live chat, group chat broadcast, private messaging isolation,
asynchronous message receipt, multi-client concurrency, message size limits,
offline recipient validation, and server-side sender anti-spoofing validation.
"""

import json
import socket
import threading
import time
import unittest
from server.udp_server import UDPServer
from server.client_registry import ClientRegistry
from client.udp_client import UDPClient
from shared.config import DEFAULT_HOST


class TestUDPChatModule5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 6025
        cls.custom_registry = ClientRegistry(offline_timeout=15.0)
        cls.server = UDPServer(host=DEFAULT_HOST, port=cls.test_port, registry=cls.custom_registry)
        cls.server.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.custom_registry.clear()

    def test_01_three_clients_group_chat_broadcast(self):
        """Module 5: Start three clients and verify group messaging broadcasts to all peers with timestamp."""
        c_alice = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Alice_Chat", session_id="s_alice")
        c_bob = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Bob_Chat", session_id="s_bob")
        c_charlie = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Charlie_Chat", session_id="s_charlie")

        self.assertIsNotNone(c_alice.join_chat())
        self.assertIsNotNone(c_bob.join_chat())
        self.assertIsNotNone(c_charlie.join_chat())
        time.sleep(0.2)

        # Alice sends group message
        group_text = "Hello everyone in group chat!"
        send_res = c_alice.send_group_message(group_text)
        self.assertTrue(send_res.get("success"))

        time.sleep(0.4)

        # Verify Bob received group message
        bob_msgs = c_bob.get_group_messages()
        self.assertTrue(len(bob_msgs) > 0, "Bob did not receive group message")
        self.assertEqual(bob_msgs[0]["sender"], "Alice_Chat")
        self.assertEqual(bob_msgs[0]["message"], group_text)
        self.assertIn(":", bob_msgs[0]["timestamp"])

        # Verify Charlie received group message
        charlie_msgs = c_charlie.get_group_messages()
        self.assertTrue(len(charlie_msgs) > 0, "Charlie did not receive group message")
        self.assertEqual(charlie_msgs[0]["sender"], "Alice_Chat")
        self.assertEqual(charlie_msgs[0]["message"], group_text)

        c_alice.leave_chat()
        c_bob.leave_chat()
        c_charlie.leave_chat()

    def test_02_private_chat_routing_and_confidentiality(self):
        """Module 5: Verify private message is forwarded ONLY to intended recipient and isolated from third parties."""
        c_alice = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Alice_Priv", session_id="s_ap")
        c_bob = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Bob_Priv", session_id="s_bp")
        c_charlie = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Charlie_Eavesdropper", session_id="s_ce")

        self.assertIsNotNone(c_alice.join_chat())
        self.assertIsNotNone(c_bob.join_chat())
        self.assertIsNotNone(c_charlie.join_chat())
        time.sleep(0.2)

        # Alice sends private message to Bob
        secret_text = "Top secret message only for Bob's eyes."
        priv_res = c_alice.send_private_message(recipient="Bob_Priv", message_text=secret_text)
        self.assertTrue(priv_res.get("success"))

        time.sleep(0.4)

        # Verify Bob received private message
        bob_privates = c_bob.get_private_messages()
        self.assertTrue(len(bob_privates) > 0, "Bob did not receive private message")
        self.assertEqual(bob_privates[0]["sender"], "Alice_Priv")
        self.assertEqual(bob_privates[0]["recipient"], "Bob_Priv")
        self.assertEqual(bob_privates[0]["message"], secret_text)

        # Verify Charlie did NOT receive the private message (Confidentiality enforced)
        charlie_privates = c_charlie.get_private_messages()
        self.assertEqual(len(charlie_privates), 0, "Security Failure: Charlie received Alice's private message to Bob!")

        c_alice.leave_chat()
        c_bob.leave_chat()
        c_charlie.leave_chat()

    def test_03_concurrent_chat_messaging(self):
        """Module 5: Handle messages from multiple clients concurrently without drops or corruption."""
        clients = [
            UDPClient(host=DEFAULT_HOST, port=self.test_port, username=f"Concurrent_{i}", session_id=f"s_c_{i}")
            for i in range(3)
        ]
        for c in clients:
            self.assertIsNotNone(c.join_chat())
        time.sleep(0.2)

        results = []

        def send_worker(client, msg):
            res = client.send_group_message(msg)
            results.append(res.get("success", False))

        threads = [
            threading.Thread(target=send_worker, args=(clients[0], "Message from C0")),
            threading.Thread(target=send_worker, args=(clients[1], "Message from C1")),
            threading.Thread(target=send_worker, args=(clients[2], "Message from C2")),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 3)
        self.assertTrue(all(results), "Not all concurrent messages succeeded")

        time.sleep(0.4)
        for c in clients:
            c.leave_chat()

    def test_04_anti_spoofing_sender_validation(self):
        """Module 5: Prevent messages from spoofing another username; validate sender against session and endpoint."""
        legit_alice = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Alice_Legit", session_id="s_legit_alice")
        self.assertIsNotNone(legit_alice.join_chat())

        victim_bob = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Bob_Victim", session_id="s_bob_vic")
        self.assertIsNotNone(victim_bob.join_chat())
        time.sleep(0.2)

        # Attacker crafts raw UDP datagram claiming sender is 'Alice_Legit' with fake session from different socket
        attacker_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        attacker_sock.settimeout(1.0)
        spoofed_payload = {
            "type": "MSG",
            "mode": "PRIVATE",
            "sequence": 9999,
            "sender": "Alice_Legit",  # Spoofed username
            "session_id": "fake_hacker_session",
            "recipient": "Bob_Victim",
            "message": "I am sending a fake spoofed message!"
        }

        attacker_sock.sendto(json.dumps(spoofed_payload).encode("utf-8"), (DEFAULT_HOST, self.test_port))

        # Check server rejection response to attacker
        try:
            data, _ = attacker_sock.recvfrom(1024)
            resp = json.loads(data.decode("utf-8"))
            self.assertEqual(resp.get("type"), "ERROR")
            self.assertIn(resp.get("code"), ["SESSION_MISMATCH", "ENDPOINT_SPOOF"])
        except socket.timeout:
            self.fail("Server did not respond to spoofed datagram")

        time.sleep(0.3)

        # Verify Bob never received the spoofed message
        bob_msgs = victim_bob.get_private_messages()
        spoofed_received = [m for m in bob_msgs if "fake spoofed" in m.get("message", "")]
        self.assertEqual(len(spoofed_received), 0, "Anti-spoofing failed: Bob received a spoofed message!")

        attacker_sock.close()
        legit_alice.leave_chat()
        victim_bob.leave_chat()

    def test_05_offline_recipient_rejection(self):
        """Module 5: Validate recipient identity; reject private messages sent to offline or nonexistent users."""
        alice = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Alice_Query", session_id="s_aq")
        self.assertIsNotNone(alice.join_chat())
        time.sleep(0.1)

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        raw_sock.settimeout(1.5)

        # Register raw_sock as sender in custom_registry to pass anti-spoofing check
        client_addr = ("127.0.0.1", 59444)
        raw_sock.bind(client_addr)
        self.custom_registry.register_client("RawAlice", "127.0.0.1", 59444, session_id="s_raw")

        req = {
            "type": "MSG",
            "mode": "PRIVATE",
            "sequence": 501,
            "sender": "RawAlice",
            "session_id": "s_raw",
            "recipient": "GhostUser_Offline",
            "message": "Are you there?"
        }
        raw_sock.sendto(json.dumps(req).encode("utf-8"), (DEFAULT_HOST, self.test_port))

        data, _ = raw_sock.recvfrom(1024)
        resp = json.loads(data.decode("utf-8"))
        self.assertEqual(resp.get("type"), "ERROR")
        self.assertEqual(resp.get("code"), "RECIPIENT_OFFLINE")

        raw_sock.close()
        alice.leave_chat()

    def test_06_message_size_validation_and_truncation(self):
        """Module 5: Truncate oversized chat messages to 1024 character single datagram limit."""
        client = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="TextSizeUser", session_id="s_ts")
        client.join_chat()

        huge_message = "M" * 2500
        res = client.send_group_message(huge_message)
        self.assertTrue(res.get("success"))
        self.assertEqual(len(res.get("message")), 1024, "Client should truncate message to 1024 chars")

        client.leave_chat()

    def test_07_asynchronous_reception_during_activity(self):
        """Module 5: Verify messages are received asynchronously while user is busy with other tasks."""
        c_alice = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Alice_Async", session_id="s_aa")
        c_bob = UDPClient(host=DEFAULT_HOST, port=self.test_port, username="Bob_Async", session_id="s_ba")

        self.assertIsNotNone(c_alice.join_chat())
        self.assertIsNotNone(c_bob.join_chat())
        time.sleep(0.2)

        # Bob is idling / busy doing other work; Alice sends 2 messages
        c_alice.send_private_message(recipient="Bob_Async", message_text="Async Msg 1")
        time.sleep(0.1)
        c_alice.send_private_message(recipient="Bob_Async", message_text="Async Msg 2")

        time.sleep(0.5)

        # Bob checks chat history
        bob_history = c_bob.get_private_messages()
        self.assertEqual(len(bob_history), 2)
        self.assertEqual(bob_history[0]["message"], "Async Msg 1")
        self.assertEqual(bob_history[1]["message"], "Async Msg 2")

        c_alice.leave_chat()
        c_bob.leave_chat()


if __name__ == "__main__":
    unittest.main()
