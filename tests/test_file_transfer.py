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

    def test_05_peer_transfer_text_file(self):
        """Verify peer transfer of a small text file between Alice and Bob."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        client_a.send_hello("Alice_Txt")
        client_b.send_hello("Bob_Txt")

        # Create small text file
        test_txt = STORAGE_DIR / "sample_note.txt"
        test_txt.write_text("Hello Bob! This is a test text file transferred over TCP socket.\nTimestamp: 2026-10-12", encoding="utf-8")
        orig_hash = calculate_sha256(test_txt)
        orig_size = test_txt.stat().st_size

        # Alice sends offer to Bob
        offer = client_a.offer_peer_transfer("Bob_Txt", str(test_txt))
        self.assertTrue(offer.get("success"))
        tid = offer.get("transfer_id")

        # Bob checks incoming transfers and accepts
        incoming = client_b.check_incoming_transfers()
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0]["transfer_id"], tid)

        accept_resp = client_b.respond_to_transfer(tid, "ACCEPT")
        self.assertTrue(accept_resp.get("success"))

        # Alice streams file now that it is accepted
        send_res = client_a.stream_peer_upload(tid, str(test_txt))
        self.assertTrue(send_res.get("success"))

        # Bob downloads
        download_res = client_b.stream_peer_download(tid, test_txt.name, orig_size, orig_hash)
        self.assertTrue(download_res.get("success"))
        self.assertTrue(download_res.get("checksum_verified"))

        saved_path = Path(download_res["saved_path"])
        self.assertTrue(saved_path.exists())
        self.assertEqual(saved_path.stat().st_size, orig_size)
        self.assertEqual(calculate_sha256(saved_path), orig_hash)
        self.assertEqual(saved_path.read_text(encoding="utf-8"), test_txt.read_text(encoding="utf-8"))

        client_a.disconnect()
        client_b.disconnect()
        if test_txt.exists():
            test_txt.unlink()
        if saved_path.exists():
            saved_path.unlink()

    def test_06_peer_transfer_image_file(self):
        """Verify peer transfer of a binary image (PNG) file between two clients."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        client_a.send_hello("Alice_Img")
        client_b.send_hello("Bob_Img")

        # Create dummy binary PNG file
        test_png = STORAGE_DIR / "sample_image.png"
        png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + os.urandom(16384)
        test_png.write_bytes(png_data)
        orig_hash = calculate_sha256(test_png)
        orig_size = len(png_data)

        # Alice offers transfer
        offer = client_a.offer_peer_transfer("Bob_Img", str(test_png))
        self.assertTrue(offer.get("success"))
        tid = offer["transfer_id"]

        # Bob accepts
        resp = client_b.respond_to_transfer(tid, "ACCEPT")
        self.assertTrue(resp.get("success"))

        # Alice streams to relay
        send_res = client_a.stream_peer_upload(tid, str(test_png))
        self.assertTrue(send_res.get("success"))

        # Bob downloads from relay
        dl_res = client_b.stream_peer_download(tid, test_png.name, orig_size, orig_hash)
        self.assertTrue(dl_res.get("success"))
        self.assertTrue(dl_res.get("checksum_verified"))

        saved_path = Path(dl_res["saved_path"])
        self.assertTrue(saved_path.exists())
        self.assertEqual(saved_path.stat().st_size, orig_size)
        self.assertEqual(calculate_sha256(saved_path), orig_hash)
        self.assertEqual(saved_path.read_bytes(), png_data)

        client_a.disconnect()
        client_b.disconnect()
        if test_png.exists():
            test_png.unlink()
        if saved_path.exists():
            saved_path.unlink()

    def test_07_peer_transfer_pdf_file(self):
        """Verify peer transfer of a PDF document between two clients."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        client_a.send_hello("Alice_Pdf")
        client_b.send_hello("Bob_Pdf")

        # Create dummy PDF document
        test_pdf = STORAGE_DIR / "project_report.pdf"
        pdf_data = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n" + os.urandom(65536) + b"\n%%EOF"
        test_pdf.write_bytes(pdf_data)
        orig_hash = calculate_sha256(test_pdf)
        orig_size = len(pdf_data)

        offer = client_a.offer_peer_transfer("Bob_Pdf", str(test_pdf))
        self.assertTrue(offer.get("success"))
        tid = offer["transfer_id"]

        client_b.respond_to_transfer(tid, "ACCEPT")
        send_res = client_a.stream_peer_upload(tid, str(test_pdf))
        self.assertTrue(send_res.get("success"))

        dl_res = client_b.stream_peer_download(tid, test_pdf.name, orig_size, orig_hash)
        self.assertTrue(dl_res.get("success"))
        self.assertTrue(dl_res.get("checksum_verified"))

        saved_path = Path(dl_res["saved_path"])
        self.assertEqual(saved_path.stat().st_size, orig_size)
        self.assertEqual(calculate_sha256(saved_path), orig_hash)

        client_a.disconnect()
        client_b.disconnect()
        if test_pdf.exists():
            test_pdf.unlink()
        if saved_path.exists():
            saved_path.unlink()

    def test_08_peer_transfer_large_file(self):
        """Verify peer transfer of a large binary file (2 MB > 500 TCP chunks) with SHA-256 integrity."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        client_a.send_hello("Alice_Large")
        client_b.send_hello("Bob_Large")

        # Create 2 MB binary file
        test_large = STORAGE_DIR / "large_archive.zip"
        chunk_pattern = b"CHUNKS_OF_4096_BYTES_PADDING_TEST_PAYLOAD_ABCDEF" * 80  # ~3840 bytes
        with open(test_large, "wb") as f:
            for _ in range(512):
                f.write(chunk_pattern)

        orig_size = test_large.stat().st_size
        orig_hash = calculate_sha256(test_large)

        offer = client_a.offer_peer_transfer("Bob_Large", str(test_large))
        self.assertTrue(offer.get("success"))
        tid = offer["transfer_id"]

        client_b.respond_to_transfer(tid, "ACCEPT")
        send_res = client_a.stream_peer_upload(tid, str(test_large))
        self.assertTrue(send_res.get("success"))

        dl_res = client_b.stream_peer_download(tid, test_large.name, orig_size, orig_hash)
        self.assertTrue(dl_res.get("success"))
        self.assertTrue(dl_res.get("checksum_verified"))

        saved_path = Path(dl_res["saved_path"])
        self.assertEqual(saved_path.stat().st_size, orig_size)
        self.assertEqual(calculate_sha256(saved_path), orig_hash)

        client_a.disconnect()
        client_b.disconnect()
        if test_large.exists():
            test_large.unlink()
        if saved_path.exists():
            saved_path.unlink()

    def test_09_peer_transfer_rejection(self):
        """Verify sender handles receiver rejection cleanly and aborts transfer without data transmission."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        client_a.send_hello("Alice_Rej")
        client_b.send_hello("Bob_Rej")

        test_file = STORAGE_DIR / "unwanted_file.docx"
        test_file.write_text("Confidential Draft", encoding="utf-8")

        offer = client_a.offer_peer_transfer("Bob_Rej", str(test_file))
        self.assertTrue(offer.get("success"))
        tid = offer["transfer_id"]

        # Bob rejects the offer
        rej_res = client_b.respond_to_transfer(tid, "REJECT", reason="Not authorized")
        self.assertTrue(rej_res.get("success"))
        self.assertEqual(rej_res.get("decision"), "REJECT")

        # Verify status on server
        status = client_a.check_transfer_status(tid)
        self.assertIsNotNone(status)
        self.assertEqual(status.get("status"), "REJECTED")

        # Attempting upload on rejected transfer fails
        send_attempt = client_a.stream_peer_upload(tid, str(test_file))
        self.assertFalse(send_attempt.get("success"))

        client_a.disconnect()
        client_b.disconnect()
        if test_file.exists():
            test_file.unlink()

    def test_10_peer_transfer_offline_receiver(self):
        """Verify error is returned immediately when receiver is offline/unknown."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        client_a.send_hello("Alice_OfflineTest")

        test_file = STORAGE_DIR / "sample.txt"
        test_file.write_text("Hello", encoding="utf-8")

        offer = client_a.offer_peer_transfer("NonExistentUser_99", str(test_file))
        self.assertFalse(offer.get("success"))
        self.assertEqual(offer.get("code"), "RECEIVER_OFFLINE")

        client_a.disconnect()
        if test_file.exists():
            test_file.unlink()

    def test_11_peer_transfer_custom_downloads_directory(self):
        """Verify receiver can save file into a configurable custom downloads directory."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        client_a.send_hello("Alice_CustomDir")
        client_b.send_hello("Bob_CustomDir")

        test_file = STORAGE_DIR / "custom_doc.txt"
        test_file.write_text("Testing custom downloads destination directory path", encoding="utf-8")
        orig_hash = calculate_sha256(test_file)
        orig_size = test_file.stat().st_size

        custom_inbox = STORAGE_DIR / "custom_inbox"
        custom_inbox.mkdir(parents=True, exist_ok=True)

        offer = client_a.offer_peer_transfer("Bob_CustomDir", str(test_file))
        self.assertTrue(offer.get("success"))
        tid = offer["transfer_id"]

        client_b.respond_to_transfer(tid, "ACCEPT")
        client_a.stream_peer_upload(tid, str(test_file))

        dl_res = client_b.stream_peer_download(
            transfer_id=tid,
            filename=test_file.name,
            filesize=orig_size,
            expected_checksum=orig_hash,
            custom_downloads_dir=custom_inbox
        )
        self.assertTrue(dl_res.get("success"))
        saved_path = Path(dl_res["saved_path"])
        self.assertEqual(saved_path.parent.resolve(), custom_inbox.resolve())
        self.assertEqual(calculate_sha256(saved_path), orig_hash)

        client_a.disconnect()
        client_b.disconnect()
        if test_file.exists():
            test_file.unlink()
        if saved_path.exists():
            saved_path.unlink()


if __name__ == "__main__":
    unittest.main()

