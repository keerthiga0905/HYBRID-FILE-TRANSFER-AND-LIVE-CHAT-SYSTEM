"""
Checksum utility for computing and verifying SHA-256 hashes of files and data.
Demonstrates error detection in Computer Networks.
"""

import hashlib
from pathlib import Path


def calculate_sha256(filepath_or_data: str | Path | bytes) -> str:
    """
    Computes the SHA-256 hash of a file path or raw bytes without loading full file into memory.
    Uses chunked reading (4KB chunks).
    """
    sha256 = hashlib.sha256()

    if isinstance(filepath_or_data, (str, Path)):
        path = Path(filepath_or_data)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, "rb") as f:
            while chunk := f.read(4096):
                sha256.update(chunk)
    elif isinstance(filepath_or_data, bytes):
        sha256.update(filepath_or_data)
    else:
        raise ValueError("Input must be a filepath or bytes.")

    return sha256.hexdigest()


def verify_checksum(hash1: str, hash2: str) -> bool:
    """
    Compares two SHA-256 hashes in constant time to prevent timing attacks.
    """
    if not hash1 or not hash2:
        return False
    return hashlib.compare_digest(hash1.lower().strip(), hash2.lower().strip())
