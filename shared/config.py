"""
Configuration constants shared across Server and Client.
"""

import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Network Configuration
DEFAULT_HOST = "127.0.0.1"
TCP_PORT = 5000
UDP_PORT = 6000

# Buffer Sizes & Socket Config
CHUNK_SIZE = 4096  # 4 KB chunk size for TCP file transfer
MAX_UDP_PAYLOAD = 1024  # Standard safe size for UDP datagrams
ACK_TIMEOUT = 1.0  # 1.0 second retransmission timeout for UDP ACKs
MAX_RETRIES = 3  # Maximum retries before declaring UDP message dropped
DEFAULT_SIMULATED_LOSS_RATE = 0.0  # Default 0% simulated packet loss (range 0.0 to 0.5)

# File Storage Paths
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
DOWNLOADS_DIR = STORAGE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Protocol Delimiters
HEADER_DELIMITER = "|"
MSG_END_MARKER = "\n"
