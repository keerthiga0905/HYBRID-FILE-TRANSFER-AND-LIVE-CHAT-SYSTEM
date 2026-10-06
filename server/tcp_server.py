"""
TCP Server Module - Handles reliable connection-oriented communication.
Multithreaded client handler supporting TCP File Upload, Download, List, RESUME, and framed JSON protocol.
"""

import socket
import threading
from pathlib import Path
from shared.config import DEFAULT_HOST, TCP_PORT, CHUNK_SIZE
from shared.protocol import receive_message, send_message
from shared.checksum import calculate_sha256
from shared.utils import print_info, print_success, print_error, print_warning
from server.logger import log_event
from server.file_manager import (
    list_upload_files,
    save_upload_stream,
    get_safe_upload_path,
    get_partial_file_offset
)


class TCPServer:
    """
    Multithreaded TCP Server for reliable connection-oriented file transfers & resumes.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = TCP_PORT):
        self.host = host
        self.port = port
        self.server_socket: socket.socket | None = None
        self.is_running = False
        self.active_clients = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        """Initializes TCP socket, binds, listens, and runs accept loop."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.is_running = True
            log_event(f"TCP File Server listening on {self.host}:{self.port}")
            print_success(f"TCP File Server listening on {self.host}:{self.port}")

            accept_thread = threading.Thread(target=self._accept_loop, daemon=True, name="TCPAcceptLoop")
            accept_thread.start()

        except Exception as e:
            print_error(f"Failed to start TCP Server: {e}")
            log_event(f"TCP Server startup error: {e}", "error")
            raise e

    def _accept_loop(self) -> None:
        """Loop that continuously accepts new client TCP connections."""
        while self.is_running:
            try:
                client_sock, client_addr = self.server_socket.accept()
                addr_str = f"{client_addr[0]}:{client_addr[1]}"
                with self._lock:
                    self.active_clients[addr_str] = client_sock

                print_info(f"Client connected: {addr_str}", tag="TCP")
                log_event(f"TCP Client connected: {addr_str}")

                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    daemon=True,
                    name=f"TCPClientHandler-{client_addr[1]}"
                )
                client_thread.start()

            except socket.error:
                if not self.is_running:
                    break

    def _handle_client(self, client_sock: socket.socket, client_addr: tuple[str, int]) -> None:
        """
        Handles communication lifecycle for a single TCP client.
        Executed inside a separate thread per client socket.
        """
        addr_str = f"{client_addr[0]}:{client_addr[1]}"
        try:
            while self.is_running:
                try:
                    msg = receive_message(client_sock)
                except ValueError as ve:
                    print_error(f"Received malformed payload from {addr_str}: {ve}")
                    log_event(f"Malformed payload from {addr_str}: {ve}", "warning")
                    err_response = {"status": "ERROR", "message": f"Malformed payload: {ve}"}
                    try:
                        send_message(client_sock, err_response)
                    except Exception:
                        pass
                    continue

                if msg is None:
                    break

                cmd = msg.get("command", "").upper()

                if cmd == "HELLO":
                    client_name = msg.get("client_name", "UnknownClient")
                    print_info("HELLO received", tag="TCP")
                    log_event(f"HELLO received from {client_name} ({addr_str})")

                    response = {
                        "status": "SUCCESS",
                        "command": "HELLO_ACK",
                        "message": "Connection is working",
                        "client_id": addr_str,
                        "server_status": "RUNNING"
                    }
                    send_message(client_sock, response)
                    print_info("HELLO response sent", tag="TCP")

                elif cmd == "LIST":
                    files_list = list_upload_files()
                    print_info(f"File LIST requested by {addr_str} ({len(files_list)} files found)", tag="TCP")
                    log_event(f"File list sent to {addr_str}: {len(files_list)} files")
                    send_message(client_sock, {"status": "SUCCESS", "command": "LIST_ACK", "files": files_list})

                elif cmd in ["UPLOAD", "RESUME_UPLOAD"]:
                    filename = msg.get("filename", "")
                    filesize = int(msg.get("filesize", 0))
                    client_checksum = msg.get("checksum", "")

                    # Check for existing partial file offset
                    existing_offset = get_partial_file_offset(filename) if cmd == "RESUME_UPLOAD" else 0

                    print_info(f"{cmd} request: {filename} ({filesize} bytes, offset={existing_offset})", tag="TCP")
                    log_event(f"{cmd} initiated from {addr_str}: {filename}, offset={existing_offset}")

                    try:
                        get_safe_upload_path(filename)
                        send_message(client_sock, {
                            "status": "READY",
                            "message": "Server ready for upload stream",
                            "offset": existing_offset
                        })

                        result = save_upload_stream(client_sock, filename, filesize, client_checksum, offset=existing_offset)
                        send_message(client_sock, result)

                        if result.get("checksum_verified"):
                            print_success(f"Upload/Resume completed & SHA-256 verified: {filename}")
                            log_event(f"Upload/Resume completed successfully: {filename}")
                        else:
                            print_error(f"Upload/Resume checksum failed for {filename}")
                            log_event(f"Upload/Resume checksum failure: {filename}", "error")

                    except ValueError as ve:
                        print_error(f"Upload rejected (Path Traversal): {ve}")
                        send_message(client_sock, {"status": "ERROR", "message": str(ve)})

                elif cmd in ["DOWNLOAD", "RESUME_DOWNLOAD"]:
                    filename = msg.get("filename", "")
                    requested_offset = int(msg.get("offset", 0))

                    print_info(f"{cmd} request: {filename} (offset={requested_offset})", tag="TCP")
                    log_event(f"{cmd} requested from {addr_str}: {filename}, offset={requested_offset}")

                    try:
                        file_path = get_safe_upload_path(filename)
                        if not file_path.exists() or not file_path.is_file():
                            send_message(client_sock, {"status": "FILE_NOT_FOUND", "message": f"File '{filename}' not found on server"})
                            print_warning(f"Download request failed: File '{filename}' not found")
                        else:
                            filesize = file_path.stat().st_size

                            if requested_offset < 0 or requested_offset >= filesize:
                                send_message(client_sock, {"status": "INVALID_OFFSET", "message": f"Requested offset {requested_offset} invalid for filesize {filesize}"})
                                continue

                            checksum = calculate_sha256(file_path)

                            # Send ready metadata header with offset acknowledgment
                            send_message(client_sock, {
                                "status": "READY",
                                "filename": file_path.name,
                                "filesize": filesize,
                                "offset": requested_offset,
                                "checksum": checksum
                            })

                            # Stream remaining binary chunks starting from requested_offset over TCP
                            with open(file_path, "rb") as f:
                                if requested_offset > 0:
                                    f.seek(requested_offset)
                                while chunk := f.read(CHUNK_SIZE):
                                    client_sock.sendall(chunk)

                            print_success(f"Streamed {filename} ({filesize - requested_offset} bytes from offset {requested_offset}) to client {addr_str}")
                            log_event(f"Download completed for {addr_str}: {filename}")

                    except ValueError as ve:
                        send_message(client_sock, {"status": "ERROR", "message": str(ve)})

                elif cmd == "QUIT":
                    send_message(client_sock, {"status": "SUCCESS", "message": "Goodbye"})
                    break

                else:
                    send_message(client_sock, {"status": "ACK", "message": f"Received command '{cmd}'"})

        except (socket.error, ConnectionResetError) as e:
            log_event(f"TCP Client {addr_str} connection reset: {e}", "info")
        except Exception as e:
            log_event(f"Error handling TCP client {addr_str}: {e}", "error")
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            with self._lock:
                self.active_clients.pop(addr_str, None)
            print_info(f"Client disconnected: {addr_str}", tag="TCP")
            log_event(f"TCP Client disconnected: {addr_str}")

    def stop(self) -> None:
        """Stops the TCP server and closes server socket."""
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        print_info("TCP File Server stopped", tag="TCP")
        log_event("TCP Server stopped")
