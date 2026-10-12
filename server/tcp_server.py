import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import socket
import threading
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List
from shared.config import DEFAULT_HOST, TCP_PORT, CHUNK_SIZE
from shared.protocol import receive_message, send_message
from shared.checksum import calculate_sha256
from shared.utils import print_info, print_success, print_error, print_warning
from server.logger import log_event
from server.file_manager import (
    list_upload_files,
    save_upload_stream,
    get_safe_upload_path,
    get_partial_file_offset,
    get_safe_transfer_path,
    save_transfer_stream,
    get_safe_transfer_meta_path,
    save_transfer_metadata,
    load_transfer_metadata,
    get_partial_transfer_offset,
    list_all_transfers_metadata,
    cleanup_transfer_file,
    cancel_transfer_files,
    sanitize_filename
)


class TCPServer:
    """
    Multithreaded TCP Server for reliable connection-oriented communication.
    Assigns unique session IDs, manages username registry, detects duplicate users,
    and supports streaming file operations and peer-to-peer file transfer routing.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = TCP_PORT):
        self.host = host
        self.port = port
        self.server_socket: socket.socket | None = None
        self.is_running = False
        self.active_clients: Dict[str, socket.socket] = {}
        self.clients_registry: Dict[str, Dict[str, Any]] = {}
        self.active_usernames: set[str] = set()
        self.username_to_session: Dict[str, str] = {}
        self.session_to_socket: Dict[str, socket.socket] = {}
        self.pending_transfers: Dict[str, Dict[str, Any]] = {}
        self.user_inbox: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def _get_transfer_record(self, transfer_id: str) -> Any:
        """Retrieves transfer record from in-memory dictionary or persistent disk metadata."""
        with self._lock:
            record = self.pending_transfers.get(transfer_id)
            if record:
                return record

        clean_tid = "".join(c for c in transfer_id if c.isalnum() or c in "-_")
        from shared.config import TRANSFERS_DIR
        if TRANSFERS_DIR.exists():
            for meta_file in TRANSFERS_DIR.glob(f"{clean_tid}_*.meta.json"):
                try:
                    import json
                    with open(meta_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        with self._lock:
                            self.pending_transfers[transfer_id] = data
                        return data
                except Exception:
                    pass
        return None

    def get_connected_users(self) -> List[Dict[str, Any]]:
        """Returns list of all currently registered and active TCP clients."""
        with self._lock:
            return list(self.clients_registry.values())

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
                session_id = uuid.uuid4().hex[:8]
                addr_str = f"{client_addr[0]}:{client_addr[1]}"
                with self._lock:
                    self.active_clients[addr_str] = client_sock
                    self.session_to_socket[session_id] = client_sock

                print_info(f"Client connected: {addr_str} (Initial Session: {session_id})", tag="TCP")
                log_event(f"TCP Client connected: {addr_str} [session={session_id}]")

                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr, session_id),
                    daemon=True,
                    name=f"TCPClientHandler-{client_addr[1]}"
                )
                client_thread.start()

            except socket.error:
                if not self.is_running:
                    break

    def _handle_client(self, client_sock: socket.socket, client_addr: tuple[str, int], session_id: str) -> None:
        """
        Handles communication lifecycle for a single TCP client.
        Executed inside a separate thread per client socket.
        """
        addr_str = f"{client_addr[0]}:{client_addr[1]}"
        registered_username: str | None = None

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

                if cmd in ["HELLO", "REGISTER"]:
                    raw_name = msg.get("client_name", msg.get("username", "")).strip()

                    # Validate username format (2 to 30 characters, alphanumeric + underscore/hyphen)
                    clean_check = raw_name.replace("_", "").replace("-", "")
                    if not raw_name or len(raw_name) < 2 or len(raw_name) > 30 or not clean_check.isalnum():
                        err_resp = {
                            "status": "ERROR",
                            "code": "INVALID_USERNAME",
                            "message": f"Invalid username '{raw_name}'. Must be 2-30 characters (letters, numbers, '-' or '_')."
                        }
                        send_message(client_sock, err_resp)
                        print_warning(f"Rejected invalid username '{raw_name}' from {addr_str}")
                        continue

                    # Check for duplicate active username
                    with self._lock:
                        if raw_name in self.active_usernames and raw_name != registered_username:
                            err_resp = {
                                "status": "ERROR",
                                "code": "DUPLICATE_USERNAME",
                                "message": f"Username '{raw_name}' is already taken by another connected user."
                            }
                            send_message(client_sock, err_resp)
                            print_warning(f"Rejected duplicate username '{raw_name}' from {addr_str}")
                            continue

                        # Update registry
                        if registered_username:
                            self.active_usernames.discard(registered_username)
                            self.username_to_session.pop(registered_username, None)

                        registered_username = raw_name
                        self.active_usernames.add(registered_username)
                        self.username_to_session[registered_username] = session_id
                        self.user_inbox.setdefault(registered_username, [])
                        self.clients_registry[session_id] = {
                            "session_id": session_id,
                            "username": registered_username,
                            "ip": client_addr[0],
                            "port": client_addr[1],
                            "addr": addr_str,
                            "status": "CONNECTED",
                            "connected_at": time.time()
                        }

                    print_success(f"User '{registered_username}' registered with Session ID [{session_id}] from {addr_str}")
                    log_event(f"User '{registered_username}' registered [session={session_id}] from {addr_str}")

                    response = {
                        "status": "SUCCESS",
                        "command": "HELLO_ACK",
                        "message": f"Welcome '{registered_username}'! Registration successful.",
                        "session_id": session_id,
                        "username": registered_username,
                        "client_id": addr_str,
                        "server_status": "RUNNING"
                    }
                    send_message(client_sock, response)
                    print_info(f"HELLO response sent to '{registered_username}' [{session_id}]", tag="TCP")

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

                elif cmd in ["GET_USERS", "LIST_USERS"]:
                    with self._lock:
                        users = [
                            {
                                "username": u["username"],
                                "session_id": u["session_id"],
                                "ip": u["ip"],
                                "port": u["port"],
                                "status": u["status"]
                            }
                            for u in self.clients_registry.values()
                            if u.get("username") != registered_username
                        ]
                    send_message(client_sock, {
                        "status": "SUCCESS",
                        "command": "USERS_LIST",
                        "users": users
                    })

                elif cmd == "PEER_TRANSFER_OFFER":
                    receiver = msg.get("receiver", "").strip()
                    filename = msg.get("filename", "").strip()
                    filesize = int(msg.get("filesize", 0))
                    checksum = msg.get("checksum", "").strip()
                    transfer_id = msg.get("transfer_id", "")

                    if not receiver or receiver not in self.active_usernames:
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "RECEIVER_OFFLINE",
                            "message": f"Receiver '{receiver}' is not connected or offline."
                        })
                        continue

                    if not filename or filesize <= 0 or not checksum or not transfer_id:
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "INVALID_METADATA",
                            "message": "Invalid transfer metadata: filename, filesize, checksum, or transfer_id missing."
                        })
                        continue

                    try:
                        clean_filename = sanitize_filename(filename)
                    except ValueError as ve:
                        send_message(client_sock, {"status": "ERROR", "code": "INVALID_FILENAME", "message": str(ve)})
                        continue

                    transfer_record = {
                        "transfer_id": transfer_id,
                        "sender": registered_username or "Unknown",
                        "receiver": receiver,
                        "filename": clean_filename,
                        "filesize": filesize,
                        "checksum": checksum,
                        "bytes_stored": 0,
                        "status": "PENDING",
                        "created_at": time.time(),
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    offer_notification = {
                        "type": "TRANSFER_OFFER",
                        "transfer_id": transfer_id,
                        "sender": registered_username or "Unknown",
                        "filename": clean_filename,
                        "filesize": filesize,
                        "checksum": checksum
                    }

                    with self._lock:
                        self.pending_transfers[transfer_id] = transfer_record
                        self.user_inbox.setdefault(receiver, []).append(offer_notification)

                    save_transfer_metadata(transfer_id, clean_filename, transfer_record)

                    print_info(f"Peer transfer offer [{transfer_id}] from '{registered_username}' to '{receiver}': '{clean_filename}' ({filesize} bytes)", tag="TCP")
                    log_event(f"Peer transfer offer [{transfer_id}] from '{registered_username}' to '{receiver}': '{clean_filename}'")
                    send_message(client_sock, {
                        "status": "SUCCESS",
                        "command": "OFFER_SENT",
                        "transfer_id": transfer_id,
                        "message": f"Transfer request for '{clean_filename}' delivered to '{receiver}'. Awaiting acceptance."
                    })

                elif cmd in ["CHECK_INCOMING_TRANSFERS", "GET_PENDING_TRANSFERS"]:
                    target_user = registered_username or msg.get("username", "")
                    with self._lock:
                        items = list(self.user_inbox.get(target_user, []))
                        self.user_inbox[target_user] = []
                    send_message(client_sock, {
                        "status": "SUCCESS",
                        "command": "INBOX_LIST",
                        "requests": items
                    })

                elif cmd == "PEER_TRANSFER_RESPONSE":
                    transfer_id = msg.get("transfer_id", "")
                    decision = msg.get("decision", "").upper()
                    reason = msg.get("reason", "Declined by receiver")

                    t_record = self._get_transfer_record(transfer_id)

                    if not t_record:
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "TRANSFER_NOT_FOUND",
                            "message": f"Transfer ID '{transfer_id}' not found or already finalized."
                        })
                        continue

                    sender = t_record.get("sender")
                    filename = t_record.get("filename", "")

                    if decision == "REJECT":
                        with self._lock:
                            t_record["status"] = "REJECTED"
                            t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            self.user_inbox.setdefault(sender, []).append({
                                "type": "TRANSFER_REJECTED",
                                "transfer_id": transfer_id,
                                "receiver": registered_username,
                                "reason": reason
                            })
                        save_transfer_metadata(transfer_id, filename, t_record)

                        print_info(f"Peer transfer [{transfer_id}] REJECTED by '{registered_username}' (Sender: '{sender}')", tag="TCP")
                        log_event(f"Peer transfer [{transfer_id}] rejected by '{registered_username}'")
                        send_message(client_sock, {
                            "status": "SUCCESS",
                            "transfer_id": transfer_id,
                            "decision": "REJECTED",
                            "message": "Rejection dispatched to sender."
                        })

                    elif decision == "ACCEPT":
                        with self._lock:
                            t_record["status"] = "ACCEPTED"
                            t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            self.user_inbox.setdefault(sender, []).append({
                                "type": "TRANSFER_ACCEPTED",
                                "transfer_id": transfer_id,
                                "receiver": registered_username
                            })
                        save_transfer_metadata(transfer_id, filename, t_record)

                        print_info(f"Peer transfer [{transfer_id}] ACCEPTED by '{registered_username}' (Sender: '{sender}')", tag="TCP")
                        log_event(f"Peer transfer [{transfer_id}] accepted by '{registered_username}'")
                        send_message(client_sock, {
                            "status": "SUCCESS",
                            "transfer_id": transfer_id,
                            "decision": "ACCEPTED",
                            "message": "Acceptance recorded. Sender notified to begin streaming."
                        })

                elif cmd == "CHECK_TRANSFER_STATUS":
                    transfer_id = msg.get("transfer_id", "")
                    t_record = self._get_transfer_record(transfer_id)
                    if t_record:
                        fname = t_record.get("filename", "")
                        fsize = int(t_record.get("filesize", 0))
                        part_bytes = get_partial_transfer_offset(transfer_id, fname)
                        staged_path = get_safe_transfer_path(transfer_id, fname)
                        if staged_path.exists() and staged_path.is_file():
                            t_record["bytes_stored"] = fsize
                        elif part_bytes > 0:
                            t_record["bytes_stored"] = part_bytes
                        send_message(client_sock, {
                            "status": "SUCCESS",
                            "command": "TRANSFER_STATUS",
                            "transfer": t_record
                        })
                    else:
                        send_message(client_sock, {
                            "status": "ERROR",
                            "message": f"Transfer '{transfer_id}' not found."
                        })

                elif cmd in ["PEER_UPLOAD_START", "RESUME_PEER_UPLOAD"]:
                    transfer_id = msg.get("transfer_id", "")
                    t_record = self._get_transfer_record(transfer_id)

                    if not t_record:
                        send_message(client_sock, {"status": "ERROR", "message": f"Transfer record '{transfer_id}' not found."})
                        continue

                    # Validate sender permission
                    if registered_username and t_record.get("sender") != registered_username:
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "PERMISSION_DENIED",
                            "message": f"Unauthorized: User '{registered_username}' is not the sender of transfer '{transfer_id}'."
                        })
                        continue

                    # Validate file identity & size if provided by client
                    req_filename = msg.get("filename")
                    if req_filename and req_filename != t_record.get("filename"):
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "FILE_MISMATCH",
                            "message": f"Filename mismatch: expected '{t_record.get('filename')}', got '{req_filename}'."
                        })
                        continue

                    req_size = msg.get("filesize")
                    if req_size and int(req_size) != int(t_record.get("filesize", 0)):
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "SIZE_MISMATCH",
                            "message": f"Filesize mismatch: expected {t_record.get('filesize')}, got {req_size}."
                        })
                        continue

                    req_checksum = msg.get("checksum")
                    if req_checksum and req_checksum != t_record.get("checksum"):
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "CHECKSUM_MISMATCH",
                            "message": "SHA-256 checksum mismatch with original transfer offer."
                        })
                        continue

                    curr_status = t_record.get("status")
                    if curr_status in ["COMPLETED", "CANCELLED", "REJECTED"]:
                        send_message(client_sock, {
                            "status": "ERROR",
                            "message": f"Cannot upload/resume: transfer status is '{curr_status}'."
                        })
                        continue

                    filename = t_record["filename"]
                    filesize = t_record["filesize"]
                    expected_checksum = t_record["checksum"]
                    receiver = t_record["receiver"]

                    # Determine verified resume offset
                    verified_offset = get_partial_transfer_offset(transfer_id, filename) if (cmd == "RESUME_PEER_UPLOAD" or msg.get("resume")) else 0
                    if verified_offset >= filesize:
                        verified_offset = 0

                    send_message(client_sock, {
                        "status": "READY",
                        "transfer_id": transfer_id,
                        "offset": verified_offset,
                        "bytes_stored": verified_offset,
                        "message": f"Server relay ready for peer stream upload (resuming from byte {verified_offset})."
                    })

                    try:
                        with self._lock:
                            t_record["status"] = "UPLOADING"
                            t_record["bytes_stored"] = verified_offset
                            t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_transfer_metadata(transfer_id, filename, t_record)

                        result = save_transfer_stream(client_sock, transfer_id, filename, filesize, expected_checksum, offset=verified_offset)
                        if result.get("checksum_verified"):
                            with self._lock:
                                t_record["status"] = "STAGED"
                                t_record["bytes_stored"] = filesize
                                t_record["checksum_verified"] = True
                                t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            save_transfer_metadata(transfer_id, filename, t_record)

                            print_success(f"Peer transfer [{transfer_id}] staged on server & SHA-256 verified ({filesize} bytes, offset={verified_offset})")
                            log_event(f"Peer transfer [{transfer_id}] staged on server relay from offset {verified_offset}")

                            ready_notification = {
                                "type": "FILE_READY_FOR_RECEIVE",
                                "transfer_id": transfer_id,
                                "sender": t_record["sender"],
                                "filename": filename,
                                "filesize": filesize,
                                "checksum": expected_checksum
                            }

                            with self._lock:
                                self.user_inbox.setdefault(receiver, []).append(ready_notification)

                            send_message(client_sock, {
                                "status": "SUCCESS",
                                "command": "UPLOAD_COMPLETE",
                                "transfer_id": transfer_id,
                                "offset_resumed": verified_offset,
                                "message": "File streamed and SHA-256 verified on server relay."
                            })
                        else:
                            with self._lock:
                                t_record["status"] = "CHECKSUM_FAILED"
                                t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            save_transfer_metadata(transfer_id, filename, t_record)
                            send_message(client_sock, {
                                "status": "ERROR",
                                "code": "CHECKSUM_FAILED",
                                "message": "Checksum verification failed during server relay upload."
                            })

                    except Exception as e:
                        with self._lock:
                            t_record["status"] = "INTERRUPTED"
                            t_record["bytes_stored"] = get_partial_transfer_offset(transfer_id, filename)
                            t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_transfer_metadata(transfer_id, filename, t_record)
                        print_error(f"Error during peer upload stream [{transfer_id}]: {e}")
                        send_message(client_sock, {"status": "ERROR", "message": str(e)})

                elif cmd in ["PEER_DOWNLOAD_START", "RESUME_PEER_DOWNLOAD"]:
                    transfer_id = msg.get("transfer_id", "")
                    t_record = self._get_transfer_record(transfer_id)

                    if not t_record:
                        send_message(client_sock, {"status": "ERROR", "message": f"Transfer record '{transfer_id}' not found."})
                        continue

                    # Validate receiver permission
                    if registered_username and t_record.get("receiver") != registered_username:
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "PERMISSION_DENIED",
                            "message": f"Unauthorized: User '{registered_username}' is not the receiver of transfer '{transfer_id}'."
                        })
                        continue

                    filename = t_record["filename"]
                    filesize = t_record["filesize"]
                    checksum = t_record["checksum"]

                    staged_path = get_safe_transfer_path(transfer_id, filename)
                    if not staged_path.exists() or not staged_path.is_file():
                        send_message(client_sock, {"status": "ERROR", "message": f"Staged file '{filename}' not found on server."})
                        continue

                    requested_offset = int(msg.get("offset", 0))
                    if requested_offset < 0 or requested_offset >= filesize:
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "INVALID_OFFSET",
                            "message": f"Requested offset {requested_offset} is invalid for filesize {filesize}."
                        })
                        continue

                    try:
                        send_message(client_sock, {
                            "status": "READY",
                            "transfer_id": transfer_id,
                            "filename": filename,
                            "filesize": filesize,
                            "offset": requested_offset,
                            "checksum": checksum,
                            "message": f"Server streaming from offset {requested_offset}."
                        })

                        with self._lock:
                            t_record["status"] = "DOWNLOADING"
                            t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        with open(staged_path, "rb") as f:
                            if requested_offset > 0:
                                f.seek(requested_offset)
                            while chunk := f.read(CHUNK_SIZE):
                                client_sock.sendall(chunk)

                        print_success(f"Streamed staged file [{transfer_id}] ({filesize - requested_offset} bytes from offset {requested_offset}) to receiver '{registered_username}'")
                        log_event(f"Streamed staged file [{transfer_id}] to receiver '{registered_username}'")

                    except Exception as e:
                        with self._lock:
                            t_record["status"] = "INTERRUPTED"
                            t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_transfer_metadata(transfer_id, filename, t_record)
                        print_error(f"Error streaming peer transfer [{transfer_id}] to receiver: {e}")
                        send_message(client_sock, {"status": "ERROR", "message": str(e)})

                elif cmd == "PEER_DOWNLOAD_COMPLETE":
                    transfer_id = msg.get("transfer_id", "")
                    t_record = self._get_transfer_record(transfer_id)

                    if t_record:
                        filename = t_record.get("filename", "")
                        sender = t_record.get("sender")
                        with self._lock:
                            t_record["status"] = "COMPLETED"
                            t_record["bytes_stored"] = t_record.get("filesize", 0)
                            t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        cleanup_transfer_file(transfer_id, filename)
                        save_transfer_metadata(transfer_id, filename, t_record)

                        with self._lock:
                            self.user_inbox.setdefault(sender, []).append({
                                "type": "TRANSFER_DELIVERED",
                                "transfer_id": transfer_id,
                                "receiver": registered_username,
                                "filename": filename
                            })

                        print_success(f"Peer transfer [{transfer_id}] successfully completed and delivered to '{registered_username}'!")
                        log_event(f"Peer transfer [{transfer_id}] successfully delivered to '{registered_username}'")

                    send_message(client_sock, {
                        "status": "SUCCESS",
                        "message": "Transfer finalized and acknowledged by server."
                    })

                elif cmd in ["LIST_TRANSFERS", "TRANSFERS_LIST"]:
                    transfers_map = {}
                    with self._lock:
                        for tid, rec in self.pending_transfers.items():
                            transfers_map[tid] = dict(rec)

                    for m in list_all_transfers_metadata():
                        tid = m.get("transfer_id")
                        if tid:
                            if tid not in transfers_map:
                                transfers_map[tid] = dict(m)
                            else:
                                if "bytes_stored" in m:
                                    transfers_map[tid]["bytes_stored"] = m["bytes_stored"]
                                if "status" in m and transfers_map[tid].get("status") == "PENDING":
                                    transfers_map[tid]["status"] = m["status"]

                    formatted_list = []
                    for tid, t in transfers_map.items():
                        fname = t.get("filename", "")
                        fsize = int(t.get("filesize", 0))
                        part_bytes = get_partial_transfer_offset(tid, fname)
                        try:
                            staged_path = get_safe_transfer_path(tid, fname)
                            if staged_path.exists() and staged_path.is_file():
                                stored = fsize
                            elif part_bytes > 0:
                                stored = part_bytes
                            else:
                                stored = int(t.get("bytes_stored", 0))
                        except Exception:
                            stored = int(t.get("bytes_stored", 0))

                        formatted_list.append({
                            "transfer_id": tid,
                            "filename": fname,
                            "filesize": fsize,
                            "sender": t.get("sender", "Unknown"),
                            "receiver": t.get("receiver", "Unknown"),
                            "bytes_stored": stored,
                            "status": t.get("status", "UNKNOWN"),
                            "checksum": t.get("checksum", "")
                        })

                    send_message(client_sock, {
                        "status": "SUCCESS",
                        "command": "TRANSFERS_LIST",
                        "transfers": formatted_list
                    })

                elif cmd == "CANCEL_TRANSFER":
                    transfer_id = msg.get("transfer_id", "")
                    t_record = self._get_transfer_record(transfer_id)

                    if not t_record:
                        send_message(client_sock, {"status": "ERROR", "message": f"Transfer '{transfer_id}' not found."})
                        continue

                    sender = t_record.get("sender")
                    receiver = t_record.get("receiver")

                    if registered_username and registered_username not in [sender, receiver]:
                        send_message(client_sock, {
                            "status": "ERROR",
                            "code": "PERMISSION_DENIED",
                            "message": f"Permission denied: User '{registered_username}' cannot cancel transfer owned by '{sender}' and '{receiver}'."
                        })
                        continue

                    if t_record.get("status") == "COMPLETED":
                        send_message(client_sock, {
                            "status": "ERROR",
                            "message": "Cannot cancel a transfer that is already completed."
                        })
                        continue

                    filename = t_record.get("filename", "")
                    with self._lock:
                        t_record["status"] = "CANCELLED"
                        t_record["cancelled_by"] = registered_username
                        t_record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    cancel_transfer_files(transfer_id, filename)
                    save_transfer_metadata(transfer_id, filename, t_record)

                    # Notify the other peer in their inbox
                    other = receiver if registered_username == sender else sender
                    if other:
                        with self._lock:
                            self.user_inbox.setdefault(other, []).append({
                                "type": "TRANSFER_CANCELLED",
                                "transfer_id": transfer_id,
                                "filename": filename,
                                "cancelled_by": registered_username
                            })

                    print_warning(f"Transfer [{transfer_id}] cancelled by user '{registered_username}'")
                    log_event(f"Transfer [{transfer_id}] cancelled by '{registered_username}'")

                    send_message(client_sock, {
                        "status": "SUCCESS",
                        "transfer_id": transfer_id,
                        "message": f"Transfer '{transfer_id}' cancelled successfully."
                    })

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
                if registered_username:
                    self.active_usernames.discard(registered_username)
                    self.username_to_session.pop(registered_username, None)
                    self.user_inbox.pop(registered_username, None)
                self.clients_registry.pop(session_id, None)
                self.session_to_socket.pop(session_id, None)

            if registered_username:
                print_info(f"Client disconnected: {addr_str} (User: '{registered_username}', Session: {session_id})", tag="TCP")
                log_event(f"TCP Client disconnected: {addr_str} (User: '{registered_username}', Session: {session_id})")
            else:
                print_info(f"Client disconnected: {addr_str} (Session: {session_id})", tag="TCP")
                log_event(f"TCP Client disconnected: {addr_str} (Session: {session_id})")

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


if __name__ == "__main__":
    print_info("Starting Standalone TCP Server (Module 1)...", tag="TCP")
    srv = TCPServer(host=DEFAULT_HOST, port=TCP_PORT)
    try:
        srv.start()
        print_info(f"TCP Server running on {DEFAULT_HOST}:{TCP_PORT}. Press Ctrl+C to terminate.", tag="TCP")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping TCP Server...")
        srv.stop()

