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
from shared.config import DEFAULT_HOST, STORAGE_DIR, UPLOADS_DIR, DOWNLOADS_DIR, TRANSFERS_DIR
from shared.checksum import calculate_sha256
from server.file_manager import get_safe_transfer_path, save_transfer_metadata


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

    def test_03_peer_upload_resume_from_partial_staging(self):
        """Module 3: Interrupted peer transfer upload - resume from 1MB offset on server relay."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        client_a.send_hello("Alice_ResumeUp")
        client_b.send_hello("Bob_ResumeUp")

        filename = self.test_file_2mb.name
        filesize = self.test_file_2mb.stat().st_size
        orig_hash = calculate_sha256(self.test_file_2mb)

        # Alice creates transfer offer
        offer = client_a.offer_peer_transfer("Bob_ResumeUp", str(self.test_file_2mb))
        self.assertTrue(offer.get("success"))
        tid = offer.get("transfer_id")

        # Bob accepts
        inc = client_b.check_incoming_transfers()
        self.assertEqual(len(inc), 1)
        acc = client_b.respond_to_transfer(tid, "ACCEPT")
        self.assertTrue(acc.get("success"))

        # Simulate interruption: Write first 1MB to server staging .part file
        staged_final = get_safe_transfer_path(tid, filename)
        staged_part = staged_final.parent / (staged_final.name + ".part")
        staged_part.parent.mkdir(parents=True, exist_ok=True)
        with open(staged_part, "wb") as f:
            f.write(self.file_content[: 1024 * 1024])

        save_transfer_metadata(tid, filename, {
            "transfer_id": tid,
            "filename": filename,
            "filesize": filesize,
            "checksum": orig_hash,
            "bytes_stored": 1024 * 1024,
            "status": "INTERRUPTED",
            "sender": "Alice_ResumeUp",
            "receiver": "Bob_ResumeUp"
        })

        # Alice reconnects or calls resume_peer_upload
        res = client_a.resume_peer_upload(tid, str(self.test_file_2mb))
        self.assertTrue(res.get("success"), f"Peer upload resume failed: {res}")
        self.assertEqual(res.get("offset_resumed"), 1024 * 1024, "Server did not resume from verified 1MB offset")
        self.assertEqual(res.get("status"), "STAGED_ON_SERVER")

        # Verify staged file on server is complete, .part was renamed, and SHA-256 matches
        self.assertTrue(staged_final.exists(), "Staged file not renamed to final filename on server")
        self.assertFalse(staged_part.exists(), "Partial .part file was not renamed after successful verification")
        self.assertEqual(calculate_sha256(staged_final), orig_hash)

        # Verify Bob receives FILE_READY_FOR_RECEIVE notification
        bob_inbox = client_b.check_incoming_transfers()
        self.assertTrue(any(item.get("type") == "FILE_READY_FOR_RECEIVE" and item.get("transfer_id") == tid for item in bob_inbox))

        client_a.disconnect()
        client_b.disconnect()

    def test_04_peer_download_resume_from_partial_client_file(self):
        """Module 3: Interrupted peer transfer download - resume from 1MB offset on client."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        client_a.send_hello("Alice_ResumeDl")
        client_b.send_hello("Bob_ResumeDl")

        filename = self.test_file_2mb.name
        filesize = self.test_file_2mb.stat().st_size
        orig_hash = calculate_sha256(self.test_file_2mb)

        # Alice offers, Bob accepts, Alice uploads complete file
        offer = client_a.offer_peer_transfer("Bob_ResumeDl", str(self.test_file_2mb))
        tid = offer.get("transfer_id")
        client_b.check_incoming_transfers()
        client_b.respond_to_transfer(tid, "ACCEPT")
        up_res = client_a.stream_peer_upload(tid, str(self.test_file_2mb))
        self.assertTrue(up_res.get("success"))

        # Simulate partial download on Bob: write 1MB to Bob's download .part file
        bob_dest = DOWNLOADS_DIR / filename
        bob_part = DOWNLOADS_DIR / f"{filename}.part"
        if bob_dest.exists():
            bob_dest.unlink()
        with open(bob_part, "wb") as f:
            f.write(self.file_content[: 1024 * 1024])

        # Bob resumes download
        dl_res = client_b.resume_peer_download(tid, filename, filesize, orig_hash)
        self.assertTrue(dl_res.get("success"), f"Peer download resume failed: {dl_res}")
        self.assertEqual(dl_res.get("offset_resumed"), 1024 * 1024, "Client did not resume from verified 1MB offset")
        self.assertTrue(dl_res.get("checksum_verified"), "Downloaded file SHA-256 verification failed")

        # Verify final file is intact, .part is renamed, and byte-for-byte identical
        self.assertTrue(bob_dest.exists(), "Final file missing from downloads directory")
        self.assertFalse(bob_part.exists(), "Partial .part file was not renamed after successful verification")
        self.assertEqual(calculate_sha256(bob_dest), orig_hash)

        client_a.disconnect()
        client_b.disconnect()

    def test_05_permission_validation_rejects_unauthorized_resume(self):
        """Module 3: Security - Validate sender/receiver permissions before resuming."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_c = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        self.assertTrue(client_c.connect())
        client_a.send_hello("Alice_Perm")
        client_b.send_hello("Bob_Perm")
        client_c.send_hello("Charlie_Hacker")

        offer = client_a.offer_peer_transfer("Bob_Perm", str(self.test_file_2mb))
        tid = offer.get("transfer_id")
        client_b.check_incoming_transfers()
        client_b.respond_to_transfer(tid, "ACCEPT")

        # Charlie (unauthorized third-party) attempts to upload on Alice's transfer
        unauth_up = client_c.stream_peer_upload(tid, str(self.test_file_2mb))
        self.assertFalse(unauth_up.get("success"), "Server allowed unauthorized user to upload")
        self.assertIn("Unauthorized", unauth_up.get("error", ""))

        # Alice uploads legitimately
        client_a.stream_peer_upload(tid, str(self.test_file_2mb))

        # Charlie attempts to download Bob's file
        unauth_dl = client_c.stream_peer_download(tid, self.test_file_2mb.name, self.test_file_2mb.stat().st_size, "hash")
        self.assertFalse(unauth_dl.get("success"), "Server allowed unauthorized user to download")
        self.assertIn("Unauthorized", unauth_dl.get("error", ""))

        client_a.disconnect()
        client_b.disconnect()
        client_c.disconnect()

    def test_06_checksum_failure_rejection_no_rename(self):
        """Module 3: Integrity - If checksum fails, do not report success and do not rename .part."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        client_a.send_hello("Alice_Corrupt")
        client_b.send_hello("Bob_Corrupt")

        filename = self.test_file_2mb.name
        filesize = self.test_file_2mb.stat().st_size
        orig_hash = calculate_sha256(self.test_file_2mb)

        offer = client_a.offer_peer_transfer("Bob_Corrupt", str(self.test_file_2mb))
        tid = offer.get("transfer_id")
        client_b.check_incoming_transfers()
        client_b.respond_to_transfer(tid, "ACCEPT")

        # Simulate corrupt partial staging on server (1MB of bad bytes)
        staged_final = get_safe_transfer_path(tid, filename)
        staged_part = staged_final.parent / (staged_final.name + ".part")
        with open(staged_part, "wb") as f:
            f.write(b"Z" * (1024 * 1024))

        # Alice resumes upload with remaining 1MB of real data
        corrupt_up = client_a.resume_peer_upload(tid, str(self.test_file_2mb))
        # Checksum must fail!
        self.assertFalse(corrupt_up.get("success"), "Server reported success despite corrupted SHA-256")
        self.assertFalse(staged_final.exists(), "Corrupted .part file was incorrectly renamed to final filename!")
        self.assertTrue(staged_part.exists(), "Corrupted .part file should be preserved for inspection")

        client_a.disconnect()
        client_b.disconnect()

    def test_07_list_transfers_and_cancellation(self):
        """Module 3: Transfer registry list and cancellation with permission enforcement."""
        client_a = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_b = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        client_c = TCPClient(host=DEFAULT_HOST, port=self.test_port)
        self.assertTrue(client_a.connect())
        self.assertTrue(client_b.connect())
        self.assertTrue(client_c.connect())
        client_a.send_hello("Alice_Cancel")
        client_b.send_hello("Bob_Cancel")
        client_c.send_hello("Charlie_Other")

        offer = client_a.offer_peer_transfer("Bob_Cancel", str(self.test_file_2mb))
        tid = offer.get("transfer_id")

        # Test LIST_TRANSFERS
        transfers = client_a.list_all_transfers()
        self.assertIsNotNone(transfers)
        match = next((t for t in transfers if t.get("transfer_id") == tid), None)
        self.assertIsNotNone(match, f"Transfer {tid} missing from LIST_TRANSFERS")
        self.assertEqual(match.get("sender"), "Alice_Cancel")
        self.assertEqual(match.get("receiver"), "Bob_Cancel")
        self.assertEqual(match.get("filename"), self.test_file_2mb.name)

        # Charlie (third-party) attempts to cancel Alice's transfer -> Permission Denied
        unauth_cancel = client_c.cancel_transfer(tid)
        self.assertFalse(unauth_cancel.get("success"), "Unauthorized user allowed to cancel transfer")
        self.assertIn("Permission denied", unauth_cancel.get("error", ""))

        # Alice cancels her own transfer
        cancel_res = client_a.cancel_transfer(tid)
        self.assertTrue(cancel_res.get("success"), f"Cancel failed: {cancel_res}")

        # Verify status is now CANCELLED
        status_rec = client_a.check_transfer_status(tid)
        self.assertEqual(status_rec.get("status"), "CANCELLED")

        # Verify Bob receives cancellation notice in inbox
        bob_inbox = client_b.check_incoming_transfers()
        self.assertTrue(any(item.get("type") == "TRANSFER_CANCELLED" and item.get("transfer_id") == tid for item in bob_inbox))

        client_a.disconnect()
        client_b.disconnect()
        client_c.disconnect()


if __name__ == "__main__":
    unittest.main()
