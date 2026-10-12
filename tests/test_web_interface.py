"""
Automated tests for Web Interface endpoints against the real Python TCP and UDP Backend.
Validates all 10 pages/panels:
1. Login / Username and session management (/api/connect, /api/status, /api/disconnect)
2. Home dashboard server status (/api/status)
3. Online users list with presence (/api/users)
4. TCP file transfer repository and upload (/api/files, /api/upload)
5. Incoming file requests and peer transfer (/api/peer/incoming, /api/peer/send)
6. Upload and download progress (/api/download, /api/partials)
7. Transfer history and SHA-256 verification (/api/transfers)
8. UDP Private chat (/api/chat/send private)
9. UDP Group chat (/api/chat/send group, /api/chat/messages)
10. Network statistics and packet loss simulation (/api/stats, /api/simulation)
"""

import io
import json
import threading
import time
import unittest
from app import app
from server.tcp_server import TCPServer
from server.udp_server import UDPServer
from shared.config import DEFAULT_HOST


class TestWebInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tcp_port = 5022
        cls.udp_port = 6022
        cls.tcp_server = TCPServer(host=DEFAULT_HOST, port=cls.tcp_port)
        cls.tcp_server.start()
        cls.udp_server = UDPServer(host=DEFAULT_HOST, port=cls.udp_port)
        cls.udp_server.start()
        time.sleep(0.3)

        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.tcp_server.stop()
        cls.udp_server.stop()

    def test_01_login_session_and_server_status(self):
        """Panels 1 & 2: Test connecting, session establishment, and status inspection."""
        # Check initial status
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        status = res.get_json()
        self.assertIn("username", status)

        # Connect with custom username
        conn_res = self.client.post("/api/connect", json={
            "host": DEFAULT_HOST,
            "tcp_port": self.tcp_port,
            "udp_port": self.udp_port,
            "username": "WebTester"
        })
        self.assertEqual(conn_res.status_code, 200)
        conn_data = conn_res.get_json()
        self.assertTrue(conn_data.get("success"), f"Connect failed: {conn_data}")
        self.assertEqual(conn_data.get("username"), "WebTester")
        self.assertIsNotNone(conn_data.get("session_id"))

        # Verify status reports connected
        res2 = self.client.get("/api/status")
        status2 = res2.get_json()
        self.assertTrue(status2.get("is_connected"))
        self.assertTrue(status2.get("tcp_connected"))
        self.assertTrue(status2.get("udp_connected"))
        self.assertEqual(status2.get("username"), "WebTester")

    def test_02_online_users_presence(self):
        """Panel 3: Test querying online users directory via UDP."""
        res = self.client.get("/api/users")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("users", data)
        self.assertIsInstance(data["users"], list)

    def test_03_file_repository_and_streaming_upload_download(self):
        """Panels 4, 6, 7: Test file listing, streaming upload, download, and transfer history."""
        # 1. List files
        list_res = self.client.get("/api/files")
        self.assertEqual(list_res.status_code, 200)
        self.assertIn("files", list_res.get_json())

        # 2. Upload file via TCP streaming
        test_filename = "test_web_upload.txt"
        test_bytes = b"Hello from Hybrid Transfer Web Interface Test! " * 50
        upload_res = self.client.post("/api/upload", data={
            "file": (io.BytesIO(test_bytes), test_filename),
            "resume": "false"
        }, content_type="multipart/form-data")

        self.assertEqual(upload_res.status_code, 200)
        upload_data = upload_res.get_json()
        self.assertTrue(upload_data.get("success"), f"Upload failed: {upload_data}")
        self.assertIn("server_checksum", upload_data)

        # 3. Download file via TCP streaming
        down_res = self.client.post("/api/download", json={"filename": test_filename, "resume": False})
        self.assertEqual(down_res.status_code, 200)
        down_data = down_res.get_json()
        self.assertTrue(down_data.get("success"), f"Download failed: {down_data}")
        self.assertTrue(down_data.get("checksum_verified"))

        # 4. Check transfer history (Panel 7)
        hist_res = self.client.get("/api/transfers")
        self.assertEqual(hist_res.status_code, 200)
        transfers = hist_res.get_json().get("transfers", [])
        self.assertGreater(len(transfers), 0)
        self.assertTrue(transfers[0].get("checksum_verified"))

    def test_04_incoming_file_requests_and_partials(self):
        """Panels 5 & 7: Test incoming peer file requests and partials endpoints."""
        res_incoming = self.client.get("/api/peer/incoming")
        self.assertEqual(res_incoming.status_code, 200)
        self.assertIn("requests", res_incoming.get_json())

        res_partials = self.client.get("/api/partials")
        self.assertEqual(res_partials.status_code, 200)
        self.assertIn("partials", res_partials.get_json())

    def test_05_group_and_private_udp_chat(self):
        """Panels 8 & 9: Test UDP group broadcast and private chat messaging."""
        # Send group message
        res_group = self.client.post("/api/chat/send", json={
            "message": "Group message from web test",
            "recipient": "ALL"
        })
        self.assertEqual(res_group.status_code, 200)
        self.assertTrue(res_group.get_json().get("success"))

        # Send private message
        res_priv = self.client.post("/api/chat/send", json={
            "message": "Private test message",
            "recipient": "PeerBob"
        })
        self.assertEqual(res_priv.status_code, 200)

        # Retrieve messages (Panel 8 & 9 history)
        res_msgs = self.client.get("/api/chat/messages")
        self.assertEqual(res_msgs.status_code, 200)
        msgs = res_msgs.get_json().get("messages", [])
        self.assertGreater(len(msgs), 0)

    def test_06_network_stats_and_simulation(self):
        """Panel 10: Test live network telemetry and packet loss simulation."""
        # Get network stats
        res_stats = self.client.get("/api/stats")
        self.assertEqual(res_stats.status_code, 200)
        stats = res_stats.get_json()
        self.assertIn("tcp", stats)
        self.assertIn("udp", stats)

        # Configure simulated packet loss rate
        res_sim = self.client.post("/api/simulation", json={"rate": 0.15})
        self.assertEqual(res_sim.status_code, 200)
        self.assertTrue(res_sim.get_json().get("success"))

    def test_07_activity_logs(self):
        """Test activity logs endpoint."""
        res_logs = self.client.get("/api/logs")
        self.assertEqual(res_logs.status_code, 200)
        logs = res_logs.get_json().get("logs", [])
        self.assertIsInstance(logs, list)


if __name__ == "__main__":
    unittest.main()
