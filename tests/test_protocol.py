"""
Automated unit tests for 4-byte network byte-order message framing protocol.
"""

import json
import socket
import struct
import unittest
import threading
from shared.protocol import send_message, receive_message, MAX_CONTROL_MSG_SIZE


class TestProtocolFraming(unittest.TestCase):
    def setUp(self):
        # Create a socketpair for testing in-memory loopback socket stream
        self.server_sock, self.client_sock = socket.socketpair()

    def tearDown(self):
        self.server_sock.close()
        self.client_sock.close()

    def test_send_and_receive_valid_json(self):
        msg_sent = {"command": "HELLO", "client_name": "TestClient", "id": 42}
        send_message(self.client_sock, msg_sent)

        msg_received = receive_message(self.server_sock)
        self.assertEqual(msg_received, msg_sent)

    def test_malformed_json_payload(self):
        # Send a 4-byte length prefix followed by non-JSON invalid string
        invalid_bytes = b"NOT_JSON_DATA"
        header = struct.pack(">I", len(invalid_bytes))
        self.client_sock.sendall(header + invalid_bytes)

        with self.assertRaises(ValueError) as ctx:
            receive_message(self.server_sock)
        self.assertIn("Invalid JSON payload", str(ctx.exception))

    def test_oversized_message_protection(self):
        # Send length prefix exceeding MAX_CONTROL_MSG_SIZE limit
        fake_huge_len = MAX_CONTROL_MSG_SIZE + 100
        header = struct.pack(">I", fake_huge_len)
        self.client_sock.sendall(header)

        with self.assertRaises(ValueError) as ctx:
            receive_message(self.server_sock)
        self.assertIn("exceeds limit", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
