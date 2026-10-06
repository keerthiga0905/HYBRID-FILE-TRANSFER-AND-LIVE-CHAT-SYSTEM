"""
TCP Client Module - Handles TCP connection lifecycle, framed message processing,
streaming file uploads/downloads, and interrupted transfer RESUME recovery with SHA-256 verification.
"""

import os
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from shared.config import DEFAULT_HOST, TCP_PORT, CHUNK_SIZE
from shared.protocol import send_message, receive_message
from shared.checksum import calculate_sha256, verify_checksum
from shared.utils import print_success, print_error, print_info
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
        """Sends HELLO command JSON message to server."""
        if not self.is_connected or not self.sock:
            return None

        hello_request = {"command": "HELLO", "client_name": client_name}
        try:
            send_message(self.sock, hello_request)
            resp = receive_message(self.sock)
            if resp and resp.get("status") == "SUCCESS":
                print_success(f"HELLO received: {resp.get('message')}")
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
