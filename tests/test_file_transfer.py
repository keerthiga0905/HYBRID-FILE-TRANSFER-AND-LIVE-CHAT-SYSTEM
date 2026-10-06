"""
Automated unit tests for TCP File Transfer Engine (Phase 2).
Tests file listing, streaming upload, streaming download, SHA-256 checksum integrity, and Path Traversal security.
"""

import os
import time
import unittest
from pathlib import Path
from server.tcp_server import TCPServer
from client.tcp_client import TCPClient
from shared.config import DEFAULT_HOST, STORAGE_DIR, UPLOADS_DIR, DOWNLOADS_DIR
from shared.checksum import calculate_sha256


class TestFileTransfer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 5003
        cls.server = TCPServer(host=DEFAULT_HOST, port=cls.test_port)
        cls.server.start()
        time.sleep(0.3)

        # Create temporary test file for upload
        cls.test_file = STORAGE_DIR / "sample_test_1mb.dat"
        with open(cls.test_file, "wb") as f:
            f.write(b"A" * (1024 * 1024))  # 1 MB test file

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        if cls.test_file.exists():
            cls.test_file.unlink()

    def test_01_file_upload_and_sha256_verification(self):
        """Verify 1MB TCP streaming file upload and SHA-256 checksum integrity."""
        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client.connect())
        client.send_hello("Uploader")

        res = client.upload_file(str(self.test_file))
        self.assertTrue(res.get("success"), f"Upload failed: {res}")
        self.assertTrue(res.get("checksum_verified"), "Checksum verification failed")

        uploaded_path = UPLOADS_DIR / "sample_test_1mb.dat"
        self.assertTrue(uploaded_path.exists(), "Uploaded file does not exist on server")

        # Verify server file content hash matches client hash
        client_hash = calculate_sha256(self.test_file)
        server_hash = calculate_sha256(uploaded_path)
        self.assertEqual(client_hash, server_hash)

        client.disconnect()

    def test_02_file_listing(self):
        """Verify TCP LIST command returns uploaded files."""
        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client.connect())
        client.send_hello("Lister")

        files = client.list_files()
        self.assertIsNotNone(files)
        filenames = [f["filename"] for f in files]
        self.assertIn("sample_test_1mb.dat", filenames)

        client.disconnect()

    def test_03_file_download_and_sha256_verification(self):
        """Verify TCP streaming download and client SHA-256 integrity verification."""
        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client.connect())
        client.send_hello("Downloader")

        res = client.download_file("sample_test_1mb.dat")
        self.assertTrue(res.get("success"), f"Download failed: {res}")
        self.assertTrue(res.get("checksum_verified"))

        downloaded_path = DOWNLOADS_DIR / "sample_test_1mb.dat"
        self.assertTrue(downloaded_path.exists(), "Downloaded file missing from storage/downloads/")

        client_hash = calculate_sha256(self.test_file)
        download_hash = calculate_sha256(downloaded_path)
        self.assertEqual(client_hash, download_hash)

        client.disconnect()

    def test_04_path_traversal_rejection(self):
        """Verify path traversal attempts (../../secret.txt) are rejected for security."""
        client = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client.connect())

        # Attempt downloading path outside storage
        res = client.download_file("../../secret.txt")
        self.assertFalse(res.get("success"))

        client.disconnect()


if __name__ == "__main__":
    unittest.main()
