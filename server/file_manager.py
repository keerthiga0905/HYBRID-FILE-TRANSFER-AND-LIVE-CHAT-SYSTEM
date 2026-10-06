"""
Server File Manager - Handles safe file storage, path traversal protection,
directory listing, and streaming file I/O operations for TCP file transfers.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from shared.config import UPLOADS_DIR, CHUNK_SIZE
from shared.checksum import calculate_sha256, verify_checksum


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes filename to prevent path traversal attacks (e.g. ../../secret.txt).
    Extracts only the basename.
    """
    clean_name = os.path.basename(filename.strip().replace("\\", "/"))
    if not clean_name or clean_name in [".", ".."]:
        raise ValueError("Invalid filename")
    return clean_name


def get_safe_upload_path(filename: str) -> Path:
    """
    Resolves filename inside UPLOADS_DIR and enforces strict path containment check.
    """
    clean_name = sanitize_filename(filename)
    target_path = (UPLOADS_DIR / clean_name).resolve()

    # Enforce path containment security check
    if not str(target_path).startswith(str(UPLOADS_DIR.resolve())):
        raise ValueError(f"Security Alert: Path traversal attempt detected for filename '{filename}'")

    return target_path


def list_upload_files() -> List[Dict[str, Any]]:
    """
    Lists all available files in storage/uploads/ with size and modified date.
    """
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


def save_upload_stream(sock, filename: str, expected_size: int, expected_checksum: str) -> Dict[str, Any]:
    """
    Streams file chunks from TCP socket, writes to filename.part, computes SHA-256 hash,
    compares with client checksum, and renames to final filename on match.
    """
    safe_final_path = get_safe_upload_path(filename)
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
                    raise ConnectionError("Socket disconnected prematurely during file upload")

                f.write(chunk)
                received_bytes += len(chunk)

        # Compute SHA-256 of received partial file
        server_checksum = calculate_sha256(part_path)
        checksum_valid = verify_checksum(expected_checksum, server_checksum)

        if checksum_valid:
            # Rename .part file to final filename after verified checksum
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
            # Clean up corrupted partial file
            if part_path.exists():
                part_path.unlink()
            return {
                "success": False,
                "status": "RETRY",
                "error": "SHA-256 checksum mismatch - File corrupted during transfer",
                "client_checksum": expected_checksum,
                "server_checksum": server_checksum,
                "checksum_verified": False
            }

    except Exception as e:
        if part_path.exists():
            part_path.unlink()
        raise e


