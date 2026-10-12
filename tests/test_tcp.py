"""
Automated unit test suite for Phase 1 TCP Server & Client socket communication.
Tests single connection, multi-client concurrency, clean disconnect, and malformed packet resilience.
"""

import socket
import struct
import time
import unittest
from server.tcp_server import TCPServer
from client.tcp_client import TCPClient
from shared.config import DEFAULT_HOST


class TestTCPPhase1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 5002
        cls.server = TCPServer(host=DEFAULT_HOST, port=cls.test_port)
        cls.server.start()
        time.sleep(0.3)  # Allow thread startup time

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_01_server_listening(self):
        """Test 1: Verify TCP server is running and listening."""
        self.assertTrue(self.server.is_running)

    def test_02_single_client_connect_and_hello(self):
        """Test 2: Verify single client connection and HELLO exchange."""
        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client.connect(), "Client failed to connect to TCP server")

        resp = client.send_hello(client_name="ClientA")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.get("status"), "SUCCESS")
        self.assertEqual(resp.get("command"), "HELLO_ACK")

        client.disconnect()
        self.assertFalse(client.is_connected)

    def test_03_and_04_dual_client_concurrency_and_disconnect(self):
        """Test 3 & 4: Verify two clients connected simultaneously, and one disconnecting cleanly."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)

        self.assertTrue(client_a.connect(), "Client A connection failed")
        self.assertTrue(client_b.connect(), "Client B connection failed")

        resp_a = client_a.send_hello("ClientA")
        resp_b = client_b.send_hello("ClientB")

        self.assertEqual(resp_a.get("status"), "SUCCESS")
        self.assertEqual(resp_b.get("status"), "SUCCESS")

        # Disconnect Client A while Client B stays connected
        client_a.disconnect()
        self.assertFalse(client_a.is_connected)
        self.assertTrue(client_b.is_connected)

        # Send another message from Client B to verify server is still responsive
        resp_b2 = client_b.send_hello("ClientB_Repeat")
        self.assertEqual(resp_b2.get("status"), "SUCCESS")

        client_b.disconnect()

    def test_05_malformed_data_resilience(self):
        """Test 5: Verify server handles malformed client payload without crashing."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect((DEFAULT_HOST, self.test_port))

        # Send raw invalid bytes with fake length prefix
        invalid_bytes = b"{this is broken json payload"
        header = struct.pack(">I", len(invalid_bytes))
        raw_sock.sendall(header + invalid_bytes)

        # Read server error response
        error_header = raw_sock.recv(4)
        self.assertEqual(len(error_header), 4)
        (err_len,) = struct.unpack(">I", error_header)
        err_payload = raw_sock.recv(err_len)
        self.assertIn(b"ERROR", err_payload)

        raw_sock.close()

        # Verify server is still alive after malformed payload
        client_verify = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_verify.connect())
        resp = client_verify.send_hello("PostErrorCheck")
        self.assertEqual(resp.get("status"), "SUCCESS")
        client_verify.disconnect()

    def test_06_unique_session_ids_per_client(self):
        """Test 6: Verify each connected client gets a distinct, unique session ID."""
        client_1 = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_2 = TCPClient(host=DEFAULT_HOST, port=self.test_port)

        self.assertTrue(client_1.connect())
        self.assertTrue(client_2.connect())

        resp1 = client_1.send_hello("UserOne")
        resp2 = client_2.send_hello("UserTwo")

        self.assertEqual(resp1.get("status"), "SUCCESS")
        self.assertEqual(resp2.get("status"), "SUCCESS")

        sid1 = resp1.get("session_id")
        sid2 = resp2.get("session_id")

        self.assertIsNotNone(sid1)
        self.assertIsNotNone(sid2)
        self.assertNotEqual(sid1, sid2, "Session IDs must be unique across clients")

        client_1.disconnect()
        client_2.disconnect()

    def test_07_invalid_username_handling(self):
        """Test 7: Verify server rejects invalid usernames (too short, spaces, symbols)."""
        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client.connect())

        # Too short (1 char)
        resp_short = client.send_hello("A")
        self.assertEqual(resp_short.get("status"), "ERROR")
        self.assertEqual(resp_short.get("code"), "INVALID_USERNAME")

        # Invalid characters (e.g. spaces / symbols)
        resp_invalid = client.send_hello("Bad User!@#")
        self.assertEqual(resp_invalid.get("status"), "ERROR")
        self.assertEqual(resp_invalid.get("code"), "INVALID_USERNAME")

        # Valid username succeeds immediately after invalid attempts
        resp_valid = client.send_hello("ValidUser1")
        self.assertEqual(resp_valid.get("status"), "SUCCESS")

        client.disconnect()

    def test_08_duplicate_username_rejection(self):
        """Test 8: Verify server rejects duplicate usernames while active, and frees on disconnect."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)

        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())

        # Client A registers as 'Alice'
        resp_a = client_a.send_hello("Alice")
        self.assertEqual(resp_a.get("status"), "SUCCESS")

        # Client B tries to register as 'Alice' while Client A is active
        resp_b_dup = client_b.send_hello("Alice")
        self.assertEqual(resp_b_dup.get("status"), "ERROR")
        self.assertEqual(resp_b_dup.get("code"), "DUPLICATE_USERNAME")

        # Client A disconnects
        client_a.disconnect()
        time.sleep(0.1)

        # Client B can now register as 'Alice'
        resp_b_retry = client_b.send_hello("Alice")
        self.assertEqual(resp_b_retry.get("status"), "SUCCESS")

        client_b.disconnect()

    def test_09_server_registry_and_disconnect(self):
        """Test 9: Verify server-side registry tracks connected users and cleans up on disconnect."""
        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client.connect())

        resp = client.send_hello("RegistryTestUser")
        self.assertEqual(resp.get("status"), "SUCCESS")
        sid = resp.get("session_id")

        active_users = self.server.get_connected_users()
        user_entry = next((u for u in active_users if u.get("session_id") == sid), None)
        self.assertIsNotNone(user_entry)
        self.assertEqual(user_entry.get("username"), "RegistryTestUser")
        self.assertEqual(user_entry.get("status"), "CONNECTED")

        # Disconnect client
        client.disconnect()
        time.sleep(0.1)

        # Registry should no longer have the user
        active_users_after = self.server.get_connected_users()
        self.assertIsNone(next((u for u in active_users_after if u.get("session_id") == sid), None))


if __name__ == "__main__":
    unittest.main()

