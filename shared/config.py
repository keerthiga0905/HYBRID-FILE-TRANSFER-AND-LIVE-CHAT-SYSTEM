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

# Detect Vercel / serverless read-only environment
IS_VERCEL = bool(os.environ.get("VERCEL"))

# File Storage Paths
if IS_VERCEL or not os.access(str(BASE_DIR), os.W_OK):
    STORAGE_DIR = Path("/tmp") / "storage"
    LOGS_DIR = Path("/tmp") / "logs"
else:
    STORAGE_DIR = BASE_DIR / "storage"
    LOGS_DIR = BASE_DIR / "logs"

UPLOADS_DIR = STORAGE_DIR / "uploads"
DOWNLOADS_DIR = STORAGE_DIR / "downloads"
TRANSFERS_DIR = STORAGE_DIR / "transfers"

# Ensure directories exist safely without crashing on read-only systems
for _dir in [STORAGE_DIR, UPLOADS_DIR, DOWNLOADS_DIR, TRANSFERS_DIR, LOGS_DIR]:
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

# Protocol Delimiters
HEADER_DELIMITER = "|"
MSG_END_MARKER = "\n"
