import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import socket
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from shared.config import DEFAULT_HOST, TCP_PORT, CHUNK_SIZE
from shared.protocol import send_message, receive_message
from shared.checksum import calculate_sha256, verify_checksum
from shared.utils import print_success, print_error, print_info, print_warning
from client.file_manager import get_safe_download_path, sanitize_filename, DOWNLOADS_DIR


class TCPClient:
    """
    TCP Client managing socket connection to the TCP Server for file transfers and resumes.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = TCP_PORT):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.is_connected = False
        self.session_id: str | None = None
        self.username: str = ""

    def connect(self) -> bool:
        """Creates AF_INET SOCK_STREAM socket and connects to server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)  # Reset blocking mode
            self.is_connected = True
            print_success("TCP CONNECTION ESTABLISHED")
            return True
        except (socket.error, ConnectionRefusedError) as e:
            print_error(f"Could not connect to TCP Server at {self.host}:{self.port} - {e}")
            self.is_connected = False
            self.sock = None
            return False

    def send_hello(self, client_name: str = "Client") -> Optional[Dict[str, Any]]:
        """Sends HELLO command JSON message to register username and receive unique session ID."""
        if not self.is_connected or not self.sock:
            return None

        hello_request = {"command": "HELLO", "client_name": client_name}
        try:
            send_message(self.sock, hello_request)
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                self.session_id = resp.get("session_id")
                self.username = resp.get("username", client_name)
                print_success(f"Registered as '{self.username}' | Session ID: [{self.session_id}]")
            elif resp and resp.get("status") == "ERROR":
                print_warning(f"Registration rejected: {resp.get('message')}")
            return resp
        except (socket.error, ValueError) as e:
            print_error(f"TCP communication error: {e}")
            self.disconnect()
            return None

    def list_files(self) -> Optional[List[Dict[str, Any]]]:
        """Requests available files list from server."""
        if not self.is_connected or not self.sock:
            return None

        try:
            send_message(self.sock, {"command": "LIST"})
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                return resp.get("files", [])
            return []
        except Exception as e:
            print_error(f"Error fetching file list: {e}")
            return None

    def upload_file(self, file_path_str: str, resume: bool = False, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Dict[str, Any]:
        """
        Streams file upload to server in 4096-byte chunks over TCP.
        Supports resuming partial uploads starting from server-acknowledged byte offset.
        Calculates client SHA-256 and verifies server SHA-256 result.
        """
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "TCP Client is not connected"}

        file_path = Path(file_path_str).resolve()
        if not file_path.exists() or not file_path.is_file():
            return {"success": False, "error": f"Local file not found: {file_path_str}"}

        filename = sanitize_filename(file_path.name)
        filesize = file_path.stat().st_size

        print_info(f"Calculating full file SHA-256 for '{filename}'...", tag="TCP")
        client_checksum = calculate_sha256(file_path)

        cmd = "RESUME_UPLOAD" if resume else "UPLOAD"
        upload_req = {
            "command": cmd,
            "filename": filename,
            "filesize": filesize,
            "checksum": client_checksum
        }

        try:
            send_message(self.sock, upload_req)
            ready_resp = receive_message(self.sock)

            if not ready_resp or ready_resp.get("status") != "READY":
                return {"success": False, "error": f"Server rejected upload: {ready_resp}"}

            offset = int(ready_resp.get("offset", 0)) if resume else 0

            print_info(f"Streaming '{filename}' from byte offset {offset}/{filesize} in 4KB chunks...", tag="TCP")
            sent_bytes = offset
            start_time = datetime.now()

            with open(file_path, "rb") as f:
                if offset > 0:
                    f.seek(offset)

                while chunk := f.read(CHUNK_SIZE):
                    self.sock.sendall(chunk)
                    sent_bytes += len(chunk)
                    try:
                        from shared.stats import global_stats
                        global_stats.record_tcp_send(len(chunk))
                    except Exception:
                        pass
                    if progress_callback:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        speed = ((sent_bytes - offset) / (1024 * 1024)) / (elapsed if elapsed > 0 else 0.001)
                        progress_callback(sent_bytes, filesize, speed)

            # Receive server verification response
            result = receive_message(self.sock)
            if result and result.get("checksum_verified"):
                print_success(f"File '{filename}' uploaded successfully! SHA-256 verified.")
                return {
                    "success": True,
                    "filename": filename,
                    "filesize": filesize,
                    "offset_resumed": offset,
                    "client_checksum": client_checksum,
                    "server_checksum": result.get("server_checksum"),
                    "checksum_verified": True
                }
            else:
                print_error(f"File upload failed checksum verification: {result}")
                return {
                    "success": False,
                    "error": result.get("error", "Checksum verification failed"),
                    "checksum_verified": False
                }

        except Exception as e:
            print_error(f"Error during TCP file upload: {e}")
            return {"success": False, "error": str(e)}

    def download_file(self, filename: str, resume: bool = False, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Dict[str, Any]:
        """
        Streams file download from server in 4096-byte chunks over TCP into storage/downloads/.
        Supports resuming partial downloads starting from local .part file size.
        Verifies SHA-256 integrity after receipt.
        """
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "TCP Client is not connected"}

        clean_name = sanitize_filename(filename)
        dest_path = get_safe_download_path(clean_name)
        part_path = dest_path.parent / (dest_path.name + ".part")

        offset = 0
        if resume and part_path.exists() and part_path.is_file():
            offset = part_path.stat().st_size

        cmd = "RESUME_DOWNLOAD" if resume and offset > 0 else "DOWNLOAD"
        download_req = {"command": cmd, "filename": clean_name, "offset": offset}

        try:
            send_message(self.sock, download_req)
            metadata = receive_message(self.sock)

            if not metadata or metadata.get("status") != "READY":
                return {"success": False, "error": metadata.get("message", "File not found or server error")}

            filesize = int(metadata.get("filesize", 0))
            expected_checksum = metadata.get("checksum", "")

            mode = "ab" if resume and offset > 0 else "wb"
            received_bytes = offset if resume and offset > 0 else 0

            print_info(f"Downloading '{clean_name}' starting from byte offset {received_bytes}/{filesize}...", tag="TCP")
            start_time = datetime.now()

            with open(part_path, mode) as f:
                while received_bytes < filesize:
                    remaining = filesize - received_bytes
                    to_read = min(CHUNK_SIZE, remaining)

                    chunk = self.sock.recv(to_read)
                    if not chunk:
                        raise ConnectionError("Connection lost during file download")

                    f.write(chunk)
                    received_bytes += len(chunk)
                    try:
                        from shared.stats import global_stats
                        global_stats.record_tcp_recv(len(chunk))
                    except Exception:
                        pass

                    if progress_callback:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        speed = ((received_bytes - offset) / (1024 * 1024)) / (elapsed if elapsed > 0 else 0.001)
                        progress_callback(received_bytes, filesize, speed)

            # Compute SHA-256 on downloaded file
            actual_checksum = calculate_sha256(part_path)
            checksum_valid = verify_checksum(expected_checksum, actual_checksum)

            if checksum_valid:
                if dest_path.exists():
                    dest_path.unlink()
                part_path.rename(dest_path)
                print_success(f"File '{clean_name}' downloaded successfully! SHA-256 verified.")
                return {
                    "success": True,
                    "filename": clean_name,
                    "filesize": filesize,
                    "offset_resumed": offset,
                    "download_path": str(dest_path),
                    "checksum": actual_checksum,
                    "checksum_verified": True
                }
            else:
                # Keep partial file for future resume attempt, but return error
                print_error(f"Downloaded file '{clean_name}' failed checksum verification!")
                return {
                    "success": False,
                    "error": "Downloaded file checksum mismatch",
                    "checksum_verified": False
                }
        except Exception as e:
            print_error(f"Error downloading file: {e}")
            return {"success": False, "error": str(e)}

    def list_online_users(self) -> List[Dict[str, Any]]:
        """Requests list of all other online users registered on TCP server."""
        if not self.is_connected or not self.sock:
            return []
        try:
            send_message(self.sock, {"command": "GET_USERS"})
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                return resp.get("users", [])
            return []
        except Exception as e:
            print_error(f"Error fetching online users list: {e}")
            return []

    def offer_peer_transfer(self, receiver: str, file_path_str: str) -> Dict[str, Any]:
        """
        Calculates file SHA-256 and size, generates unique transfer ID,
        and submits PEER_TRANSFER_OFFER to the TCP server.
        """
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "TCP Client is not connected"}

        file_path = Path(file_path_str).resolve()
        if not file_path.exists() or not file_path.is_file():
            return {"success": False, "error": f"Local file not found: {file_path_str}"}

        filename = sanitize_filename(file_path.name)
        filesize = file_path.stat().st_size
        if filesize <= 0:
            return {"success": False, "error": "File is empty (0 bytes)"}

        print_info(f"Computing SHA-256 checksum for '{filename}' ({filesize} bytes)...", tag="TCP")
        checksum = calculate_sha256(file_path)
        transfer_id = uuid.uuid4().hex[:12]

        req = {
            "command": "PEER_TRANSFER_OFFER",
            "transfer_id": transfer_id,
            "sender": self.username,
            "receiver": receiver.strip(),
            "filename": filename,
            "filesize": filesize,
            "checksum": checksum
        }

        try:
            send_message(self.sock, req)
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                return {
                    "success": True,
                    "transfer_id": transfer_id,
                    "receiver": receiver,
                    "filename": filename,
                    "filesize": filesize,
                    "checksum": checksum,
                    "message": resp.get("message")
                }
            else:
                err_msg = resp.get("message") if resp else "Server did not respond"
                return {"success": False, "error": err_msg, "code": resp.get("code") if resp else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_transfer_status(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Queries current status of transfer_id on the server."""
        if not self.is_connected or not self.sock:
            return None
        try:
            send_message(self.sock, {"command": "CHECK_TRANSFER_STATUS", "transfer_id": transfer_id})
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                return resp.get("transfer")
            return None
        except Exception:
            return None

    def check_incoming_transfers(self) -> List[Dict[str, Any]]:
        """Fetches pending transfer notifications from server inbox."""
        if not self.is_connected or not self.sock:
            return []
        try:
            send_message(self.sock, {"command": "CHECK_INCOMING_TRANSFERS"})
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                return resp.get("requests", [])
            return []
        except Exception:
            return []

    def respond_to_transfer(self, transfer_id: str, decision: str, reason: str = "") -> Dict[str, Any]:
        """Sends ACCEPT or REJECT decision for an incoming transfer request."""
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "TCP Client is not connected"}
        req = {
            "command": "PEER_TRANSFER_RESPONSE",
            "transfer_id": transfer_id,
            "decision": decision.upper(),
            "reason": reason
        }
        try:
            send_message(self.sock, req)
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                return {"success": True, "decision": decision.upper(), "message": resp.get("message")}
            return {"success": False, "error": resp.get("message") if resp else "No response"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stream_peer_upload(self, transfer_id: str, file_path_str: str, resume: bool = False, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Dict[str, Any]:
        """
        Streams binary file in 4096-byte chunks to server staging relay for transfer_id.
        Supports resuming from server's verified offset if previously interrupted.
        Tracks progress, bytes sent, speed, and status.
        """
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "TCP Client is not connected"}

        file_path = Path(file_path_str).resolve()
        if not file_path.exists():
            return {"success": False, "error": f"File not found: {file_path_str}"}

        filesize = file_path.stat().st_size
        filename = sanitize_filename(file_path.name)
        checksum = calculate_sha256(file_path)

        cmd = "RESUME_PEER_UPLOAD" if resume else "PEER_UPLOAD_START"
        req = {
            "command": cmd,
            "transfer_id": transfer_id,
            "filename": filename,
            "filesize": filesize,
            "checksum": checksum,
            "resume": resume
        }
        send_message(self.sock, req)
        ready_ack = receive_message(self.sock)
        if not ready_ack or ready_ack.get("status") != "READY":
            return {"success": False, "error": ready_ack.get("message", "Server not ready for upload") if ready_ack else "No response"}

        offset = int(ready_ack.get("offset", 0)) if (resume or ready_ack.get("offset")) else 0
        if offset > 0:
            print_info(f"Resuming upload of '{filename}' from verified byte offset {offset}/{filesize}...", tag="TCP")
        else:
            print_info(f"Streaming '{filename}' ({filesize} bytes) in {CHUNK_SIZE}-byte chunks...", tag="TCP")

        sent_bytes = offset
        start_time = datetime.now()
        speed = 0.0

        try:
            with open(file_path, "rb") as f:
                if offset > 0:
                    f.seek(offset)
                while chunk := f.read(CHUNK_SIZE):
                    self.sock.sendall(chunk)
                    sent_bytes += len(chunk)
                    elapsed = (datetime.now() - start_time).total_seconds()
                    speed = ((sent_bytes - offset) / (1024 * 1024)) / (elapsed if elapsed > 0 else 0.001)
                    if progress_callback:
                        progress_callback(sent_bytes, filesize, speed)

            # Receive completion confirmation from server relay
            result = receive_message(self.sock)
            if result and result.get("status") == "SUCCESS":
                print_success(f"File streamed & staged successfully! [{transfer_id}] (Resumed from {offset} bytes)")
                return {
                    "success": True,
                    "transfer_id": transfer_id,
                    "filename": filename,
                    "bytes_sent": sent_bytes,
                    "filesize": filesize,
                    "offset_resumed": offset,
                    "speed_mbs": round(speed, 2),
                    "status": "STAGED_ON_SERVER"
                }
            else:
                err = result.get("message") if result else "Upload confirmation failed"
                print_error(f"Stream upload error: {err}")
                return {"success": False, "error": err}

        except Exception as e:
            print_error(f"Exception during peer stream upload: {e}")
            return {"success": False, "error": str(e), "bytes_sent": sent_bytes, "interrupted": True}

    def resume_peer_upload(self, transfer_id: str, file_path_str: str, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Dict[str, Any]:
        """Resumes an interrupted peer file upload from server's verified byte offset."""
        return self.stream_peer_upload(transfer_id, file_path_str, resume=True, progress_callback=progress_callback)

    def stream_peer_download(self, transfer_id: str, filename: str, filesize: int, expected_checksum: str, custom_downloads_dir: Optional[Path | str] = None, resume: bool = False, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Dict[str, Any]:
        """
        Streams binary file in 4096-byte chunks from server staging relay for transfer_id.
        Stores incomplete files with a .part extension and preserves them on interruption.
        Supports resuming from client's verified byte offset.
        Verifies full file using SHA-256 and renames .part to final filename only after verification.
        """
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "TCP Client is not connected"}

        clean_name = sanitize_filename(filename)
        dest_path = get_safe_download_path(clean_name, custom_downloads_dir)
        part_path = dest_path.parent / (dest_path.name + ".part")

        # Determine verified resume offset from local .part file if it exists
        offset = 0
        if (resume or part_path.exists()) and part_path.exists():
            offset = part_path.stat().st_size
            if offset >= filesize:
                offset = 0

        cmd = "RESUME_PEER_DOWNLOAD" if offset > 0 else "PEER_DOWNLOAD_START"
        send_message(self.sock, {
            "command": cmd,
            "transfer_id": transfer_id,
            "offset": offset
        })
        ready_ack = receive_message(self.sock)
        if not ready_ack or ready_ack.get("status") != "READY":
            return {"success": False, "error": ready_ack.get("message", "Server not ready for download") if ready_ack else "No response"}

        verified_offset = int(ready_ack.get("offset", 0))
        if verified_offset > 0:
            print_info(f"Resuming download of '{clean_name}' from verified byte offset {verified_offset}/{filesize}...", tag="TCP")
        else:
            print_info(f"Downloading '{clean_name}' ({filesize} bytes) from server relay...", tag="TCP")

        mode = "ab" if (verified_offset > 0 and part_path.exists()) else "wb"
        received_bytes = verified_offset
        start_time = datetime.now()

        try:
            with open(part_path, mode) as f:
                while received_bytes < filesize:
                    remaining = filesize - received_bytes
                    to_read = min(CHUNK_SIZE, remaining)
                    chunk = self.sock.recv(to_read)
                    if not chunk:
                        raise ConnectionError(f"Connection lost during peer download stream at {received_bytes}/{filesize} bytes")
                    f.write(chunk)
                    received_bytes += len(chunk)
                    elapsed = (datetime.now() - start_time).total_seconds()
                    speed = ((received_bytes - verified_offset) / (1024 * 1024)) / (elapsed if elapsed > 0 else 0.001)
                    if progress_callback:
                        progress_callback(received_bytes, filesize, speed)

            # Calculate SHA-256 over entire assembled file
            actual_checksum = calculate_sha256(part_path)
            checksum_valid = verify_checksum(expected_checksum, actual_checksum)

            if checksum_valid:
                # Rename the partial file to its final filename only after successful verification!
                if dest_path.exists():
                    dest_path.unlink()
                part_path.rename(dest_path)

                # Acknowledge completion to server
                send_message(self.sock, {"command": "PEER_DOWNLOAD_COMPLETE", "transfer_id": transfer_id})
                comp_ack = receive_message(self.sock)

                print_success(f"Received and verified '{clean_name}'! SHA-256 match confirmed.")
                return {
                    "success": True,
                    "transfer_id": transfer_id,
                    "filename": clean_name,
                    "filesize": filesize,
                    "saved_path": str(dest_path),
                    "checksum": actual_checksum,
                    "checksum_verified": True,
                    "offset_resumed": verified_offset
                }
            else:
                # If checksum fails, DO NOT rename partial file and DO NOT report success!
                print_error(f"Received file '{clean_name}' failed SHA-256 checksum verification! Preserving .part file for inspection.")
                return {
                    "success": False,
                    "error": "Checksum verification failed - file corrupted or altered in transit",
                    "checksum_verified": False,
                    "expected_checksum": expected_checksum,
                    "actual_checksum": actual_checksum
                }

        except Exception as e:
            # Preserve partial .part file for resume on connection drop
            print_error(f"Download stream interrupted at {received_bytes}/{filesize} bytes: {e}. Preserved partial file '{part_path.name}'.")
            return {
                "success": False,
                "error": str(e),
                "bytes_received": received_bytes,
                "interrupted": True
            }

    def resume_peer_download(self, transfer_id: str, filename: str, filesize: int, expected_checksum: str, custom_downloads_dir: Optional[Path | str] = None, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Dict[str, Any]:
        """Resumes an interrupted peer file download from client's verified byte offset."""
        return self.stream_peer_download(transfer_id, filename, filesize, expected_checksum, custom_downloads_dir=custom_downloads_dir, resume=True, progress_callback=progress_callback)

    def list_all_transfers(self) -> Optional[List[Dict[str, Any]]]:
        """Requests list of all transfers (active, staged, completed, interrupted) from server."""
        if not self.is_connected or not self.sock:
            return None
        try:
            send_message(self.sock, {"command": "LIST_TRANSFERS"})
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                return resp.get("transfers", [])
            return []
        except Exception as e:
            print_error(f"Error fetching transfer list: {e}")
            return None

    def cancel_transfer(self, transfer_id: str) -> Dict[str, Any]:
        """Cancels an active or pending transfer if caller is the sender or receiver."""
        if not self.is_connected or not self.sock:
            return {"success": False, "error": "TCP Client is not connected"}
        try:
            send_message(self.sock, {"command": "CANCEL_TRANSFER", "transfer_id": transfer_id})
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                return {"success": True, "message": resp.get("message")}
            return {"success": False, "error": resp.get("message", "Cancellation failed") if resp else "No response"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_file_to_peer(self, receiver: str, file_path_str: str, timeout: float = 30.0, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Dict[str, Any]:
        """
        End-to-end automated workflow for sender:
        1. Offers transfer to receiver.
        2. Polls status until ACCEPTED or REJECTED.
        3. Once accepted, streams file in 4096-byte chunks.
        """
        offer = self.offer_peer_transfer(receiver, file_path_str)
        if not offer.get("success"):
            return offer

        transfer_id = offer["transfer_id"]
        print_info(f"Offer sent [{transfer_id}]. Waiting for '{receiver}' to accept...", tag="TCP")
        start_wait = time.time()

        while (time.time() - start_wait) < timeout:
            status_info = self.check_transfer_status(transfer_id)
            if not status_info:
                time.sleep(0.3)
                continue

            current_status = status_info.get("status")
            if current_status == "REJECTED":
                return {
                    "success": False,
                    "transfer_id": transfer_id,
                    "status": "REJECTED",
                    "error": f"Receiver '{receiver}' rejected the file transfer."
                }
            elif current_status in ["ACCEPTED", "UPLOADING", "STAGED", "COMPLETED"]:
                return self.stream_peer_upload(transfer_id, file_path_str, progress_callback=progress_callback)

            time.sleep(0.3)

        return {
            "success": False,
            "transfer_id": transfer_id,
            "status": "TIMEOUT",
            "error": f"Transfer timed out waiting for receiver '{receiver}' acceptance."
        }

    def accept_and_receive_transfer(self, transfer_id: str, filename: str, filesize: int, checksum: str, custom_downloads_dir: Optional[Path | str] = None, timeout: float = 30.0, progress_callback: Optional[Callable[[int, int, float], None]] = None) -> Dict[str, Any]:
        """
        End-to-end automated workflow for receiver:
        1. Sends ACCEPT decision.
        2. Waits until server staging is ready (status == 'STAGED').
        3. Downloads stream in 4096-byte chunks, verifies SHA-256, and saves to downloads directory.
        """
        resp = self.respond_to_transfer(transfer_id, "ACCEPT")
        if not resp.get("success"):
            return resp

        print_info(f"Accepted transfer [{transfer_id}]. Waiting for sender stream...", tag="TCP")
        start_wait = time.time()

        while (time.time() - start_wait) < timeout:
            status_info = self.check_transfer_status(transfer_id)
            if not status_info:
                time.sleep(0.3)
                continue

            current_status = status_info.get("status")
            if current_status == "STAGED":
                return self.stream_peer_download(
                    transfer_id=transfer_id,
                    filename=filename,
                    filesize=filesize,
                    expected_checksum=checksum,
                    custom_downloads_dir=custom_downloads_dir,
                    progress_callback=progress_callback
                )
            elif current_status in ["UPLOAD_FAILED", "CHECKSUM_FAILED"]:
                return {
                    "success": False,
                    "transfer_id": transfer_id,
                    "status": current_status,
                    "error": "Sender upload to server failed or checksum mismatched"
                }

            time.sleep(0.3)

        return {
            "success": False,
            "transfer_id": transfer_id,
            "status": "TIMEOUT",
            "error": "Timed out waiting for sender file stream"
        }

    def disconnect(self) -> None:
        """Closes TCP socket cleanly."""
        if self.sock and self.is_connected:
            try:
                send_message(self.sock, {"command": "QUIT"})
                self.sock.close()
            except Exception:
                pass
            self.is_connected = False
            self.sock = None
            print_info("Disconnected from TCP Server", tag="TCP")
