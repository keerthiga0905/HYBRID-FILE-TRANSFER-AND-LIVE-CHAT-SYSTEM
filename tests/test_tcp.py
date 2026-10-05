"""
Automated unit tests for TCP Server and TCP Client connection lifecycle (Phase 1).
"""

import time
import unittest
from server.tcp_server import TCPServer
from client.tcp_client import TCPClient
from shared.config import DEFAULT_HOST


class TestTCPConnection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a non-standard port for testing to avoid conflicts
        cls.test_port = 5005
        cls.server = TCPServer(host=DEFAULT_HOST, port=cls.test_port)
        cls.server.start()
        time.sleep(0.5)  # Wait for server thread startup

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_client_connection_and_ping(self):
        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        connected = client.connect()
        self.assertTrue(connected, "Client failed to connect to TCP server")

        resp = client.ping()
        self.assertIsNotNone(resp, "Server failed to respond to PING")
        self.assertEqual(resp.command, "PONG")

        client.disconnect()
        self.assertFalse(client.is_connected, "Client socket should be disconnected")


if __name__ == "__main__":
    unittest.main()
