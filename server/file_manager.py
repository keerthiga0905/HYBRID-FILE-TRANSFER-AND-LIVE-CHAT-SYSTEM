"""
Server File Manager - Handles safe file storage, path traversal protection,
directory listing, streaming file I/O operations, and interrupted file transfer RESUME logic.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from shared.config import UPLOADS_DIR, TRANSFERS_DIR, CHUNK_SIZE
from shared.checksum import calculate_sha256, verify_checksum


def sanitize_filename(filename: str) -> str:
    """Sanitizes filename to prevent path traversal attacks."""
    clean_name = os.path.basename(filename.strip().replace("\\", "/"))
    if not clean_name or clean_name in [".", ".."]:
        raise ValueError("Invalid filename")
    return clean_name


def get_safe_upload_path(filename: str) -> Path:
    """Resolves filename inside UPLOADS_DIR and enforces strict path containment check."""
    clean_name = sanitize_filename(filename)
    target_path = (UPLOADS_DIR / clean_name).resolve()

    if not str(target_path).startswith(str(UPLOADS_DIR.resolve())):
        raise ValueError(f"Security Alert: Path traversal attempt detected for filename '{filename}'")

    return target_path


def list_upload_files() -> List[Dict[str, Any]]:
    """Lists all available files in storage/uploads/ with size and modified date."""
    files_info = []
    if not UPLOADS_DIR.exists():
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    for item in UPLOADS_DIR.iterdir():
        if item.is_file() and not item.name.endswith(".part") and not item.name.startswith("."):
            stat = item.stat()
            files_info.append({
                "filename": item.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    return files_info


def get_partial_file_offset(filename: str) -> int:
    """Returns size of existing .part file in bytes, or 0 if none exists."""
    safe_final_path = get_safe_upload_path(filename)
    part_path = safe_final_path.parent / (safe_final_path.name + ".part")
    if part_path.exists() and part_path.is_file():
        return part_path.stat().st_size
    return 0


def save_upload_stream(sock, filename: str, expected_size: int, expected_checksum: str, offset: int = 0) -> Dict[str, Any]:
    """
    Streams file chunks from TCP socket, writes/appends to filename.part, computes SHA-256 hash,
    compares with client checksum, and renames to final filename on match.
    Supports resumed transfers starting from `offset` bytes.
    """
    safe_final_path = get_safe_upload_path(filename)
    safe_final_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = safe_final_path.parent / (safe_final_path.name + ".part")

    mode = "ab" if offset > 0 and part_path.exists() else "wb"
    received_bytes = part_path.stat().st_size if (offset > 0 and part_path.exists()) else 0

    if offset > 0 and received_bytes != offset:
        # Client claimed different offset than server's actual file size - safety check
        offset = received_bytes

    start_time = datetime.now()

    try:
        with open(part_path, mode) as f:
            while received_bytes < expected_size:
                remaining = expected_size - received_bytes
                to_read = min(CHUNK_SIZE, remaining)

                chunk = sock.recv(to_read)
                if not chunk:
                    raise ConnectionError("Socket disconnected prematurely during file upload")

                f.write(chunk)
                received_bytes += len(chunk)

        # Compute SHA-256 of complete received file
        server_checksum = calculate_sha256(part_path)
        checksum_valid = verify_checksum(expected_checksum, server_checksum)

        if checksum_valid:
            if safe_final_path.exists():
                safe_final_path.unlink()
            part_path.rename(safe_final_path)

            elapsed = (datetime.now() - start_time).total_seconds()
            throughput = (expected_size / (1024 * 1024)) / (elapsed if elapsed > 0 else 0.001)

            return {
                "success": True,
                "status": "SUCCESS",
                "filename": safe_final_path.name,
                "bytes_received": received_bytes,
                "server_checksum": server_checksum,
                "checksum_verified": True,
                "throughput_mbs": round(throughput, 2)
            }
        else:
            # Keep partial file for future resume attempt, but return error
            return {
                "success": False,
                "status": "RETRY",
                "error": "SHA-256 checksum mismatch - File integrity verification failed",
                "client_checksum": expected_checksum,
                "server_checksum": server_checksum,
                "checksum_verified": False
            }

    except Exception as e:
        # Preserve partial file for resume on connection drop
        raise e


def get_safe_transfer_path(transfer_id: str, filename: str) -> Path:
    """Returns safe path for staged peer transfer file in TRANSFERS_DIR."""
    clean_name = sanitize_filename(filename)
    clean_tid = "".join(c for c in transfer_id if c.isalnum() or c in "-_")
    if not clean_tid:
        raise ValueError("Invalid transfer ID")
    target_path = (TRANSFERS_DIR / f"{clean_tid}_{clean_name}").resolve()
    if not str(target_path).startswith(str(TRANSFERS_DIR.resolve())):
        raise ValueError(f"Security Alert: Path traversal attempt for transfer file '{filename}'")
    return target_path


def save_transfer_stream(sock, transfer_id: str, filename: str, expected_size: int, expected_checksum: str) -> Dict[str, Any]:
    """
    Streams file chunks for a peer transfer into storage/transfers/,
    computes SHA-256 hash, and verifies integrity against sender's checksum.
    """
    safe_final_path = get_safe_transfer_path(transfer_id, filename)
    safe_final_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = safe_final_path.parent / (safe_final_path.name + ".part")

    received_bytes = 0
    start_time = datetime.now()

    try:
        with open(part_path, "wb") as f:
            while received_bytes < expected_size:
                remaining = expected_size - received_bytes
                to_read = min(CHUNK_SIZE, remaining)

                chunk = sock.recv(to_read)
                if not chunk:
                    raise ConnectionError("Socket disconnected during peer file transfer stream")

                f.write(chunk)
                received_bytes += len(chunk)

        # Compute and verify SHA-256
        server_checksum = calculate_sha256(part_path)
        checksum_valid = verify_checksum(expected_checksum, server_checksum)

        if checksum_valid:
            if safe_final_path.exists():
                safe_final_path.unlink()
            part_path.rename(safe_final_path)

            elapsed = (datetime.now() - start_time).total_seconds()
            throughput = (expected_size / (1024 * 1024)) / (elapsed if elapsed > 0 else 0.001)

            return {
                "success": True,
                "status": "SUCCESS",
                "transfer_id": transfer_id,
                "filename": safe_final_path.name,
                "bytes_received": received_bytes,
                "server_checksum": server_checksum,
                "checksum_verified": True,
                "throughput_mbs": round(throughput, 2)
            }
        else:
            if part_path.exists():
                part_path.unlink()
            return {
                "success": False,
                "status": "ERROR",
                "error": "SHA-256 checksum mismatch",
                "client_checksum": expected_checksum,
                "server_checksum": server_checksum,
                "checksum_verified": False
            }

    except Exception as e:
        if part_path.exists():
            try:
                part_path.unlink()
            except Exception:
                pass
        raise e


def cleanup_transfer_file(transfer_id: str, filename: str) -> None:
    """Removes staged transfer file from TRANSFERS_DIR after delivery."""
    try:
        safe_path = get_safe_transfer_path(transfer_id, filename)
        if safe_path.exists():
            safe_path.unlink()
        part_path = safe_path.parent / (safe_path.name + ".part")
        if part_path.exists():
            part_path.unlink()
    except Exception:
        pass

