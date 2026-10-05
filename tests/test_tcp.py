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


if __name__ == "__main__":
    unittest.main()
