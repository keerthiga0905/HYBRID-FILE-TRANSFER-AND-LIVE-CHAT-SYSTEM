"""
Client File Manager - Handles safe client-side file storage in storage/downloads/
and streaming file chunk reading for TCP file upload operations.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from shared.config import DOWNLOADS_DIR, CHUNK_SIZE
from shared.checksum import calculate_sha256, verify_checksum


def sanitize_filename(filename: str) -> str:
    """Sanitizes filename to prevent path traversal."""
    clean_name = os.path.basename(filename.strip().replace("\\", "/"))
    if not clean_name or clean_name in [".", ".."]:
        raise ValueError("Invalid filename")
    return clean_name


def get_safe_download_path(filename: str) -> Path:
    """Resolves filename inside DOWNLOADS_DIR with path containment security check."""
    clean_name = sanitize_filename(filename)
    target_path = (DOWNLOADS_DIR / clean_name).resolve()

    if not str(target_path).startswith(str(DOWNLOADS_DIR.resolve())):
        raise ValueError(f"Security Alert: Path traversal attempt detected for filename '{filename}'")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path



def list_download_files() -> List[Dict[str, Any]]:
    """Lists files saved in storage/downloads/."""
    files_info = []
    if not DOWNLOADS_DIR.exists():
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    for item in DOWNLOADS_DIR.iterdir():
        if item.is_file() and not item.name.endswith(".part") and not item.name.startswith("."):
            stat = item.stat()
            files_info.append({
                "filename": item.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    return files_info
