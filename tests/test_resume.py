"""
Automated unit test suite for TCP Interrupted File Transfer RESUME Engine (Phase 3).
Tests partial upload resume, partial download resume, mathematical offset correctness, and SHA-256 verification.
"""

import os
import time
import unittest
from pathlib import Path
from server.tcp_server import TCPServer
from client.tcp_client import TCPClient
from shared.config import DEFAULT_HOST, STORAGE_DIR, UPLOADS_DIR, DOWNLOADS_DIR
from shared.checksum import calculate_sha256


class TestTCPFileResume(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 5004
        cls.server = TCPServer(host=DEFAULT_HOST, port=cls.test_port)
        cls.server.start()
        time.sleep(0.3)

        # Create a 2 MB test file
        cls.test_file_2mb = STORAGE_DIR / "resume_test_2mb.dat"
        cls.file_content = b"X" * (2 * 1024 * 1024)  # 2 MB content
        with open(cls.test_file_2mb, "wb") as f:
            f.write(cls.file_content)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        if cls.test_file_2mb.exists():
            cls.test_file_2mb.unlink()

    def test_01_upload_resume_from_partial_file(self):
        """Simulate interrupted upload (50% written to server .part) and perform RESUME_UPLOAD."""
        filename = "resume_test_2mb.dat"
        part_path_on_server = UPLOADS_DIR / f"{filename}.part"

        # Simulate 1MB (50%) already uploaded on server
        with open(part_path_on_server, "wb") as f:
            f.write(self.file_content[: 1024 * 1024])

        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client.connect())
        client.send_hello("ResumeUploader")

        # Perform RESUME upload
        res = client.upload_file(str(self.test_file_2mb), resume=True)
        self.assertTrue(res.get("success"), f"Resume upload failed: {res}")
        self.assertEqual(res.get("offset_resumed"), 1024 * 1024, "Server did not resume from expected 1MB offset")
        self.assertTrue(res.get("checksum_verified"), "Final 2MB file SHA-256 verification failed")

        final_server_file = UPLOADS_DIR / filename
        self.assertTrue(final_server_file.exists(), "Final resumed file missing on server")

        # Verify complete file SHA-256
        client_hash = calculate_sha256(self.test_file_2mb)
        server_hash = calculate_sha256(final_server_file)
        self.assertEqual(client_hash, server_hash)

        client.disconnect()

    def test_02_download_resume_from_partial_file(self):
        """Simulate interrupted download (50% written to client .part) and perform RESUME_DOWNLOAD."""
        filename = "resume_test_2mb.dat"
        # Ensure server has complete 2MB file
        server_file = UPLOADS_DIR / filename
        with open(server_file, "wb") as f:
            f.write(self.file_content)

        part_path_on_client = DOWNLOADS_DIR / f"{filename}.part"
        # Simulate 1MB (50%) already downloaded on client
        with open(part_path_on_client, "wb") as f:
            f.write(self.file_content[: 1024 * 1024])

        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client.connect())
        client.send_hello("ResumeDownloader")

        # Perform RESUME download
        res = client.download_file(filename, resume=True)
        self.assertTrue(res.get("success"), f"Resume download failed: {res}")
        self.assertEqual(res.get("offset_resumed"), 1024 * 1024, "Client did not request resume from expected 1MB offset")
        self.assertTrue(res.get("checksum_verified"), "Final downloaded file SHA-256 verification failed")

        final_client_file = DOWNLOADS_DIR / filename
        self.assertTrue(final_client_file.exists(), "Final resumed file missing in storage/downloads/")

        client_hash = calculate_sha256(self.test_file_2mb)
        download_hash = calculate_sha256(final_client_file)
        self.assertEqual(client_hash, download_hash)

        client.disconnect()


if __name__ == "__main__":
    unittest.main()
