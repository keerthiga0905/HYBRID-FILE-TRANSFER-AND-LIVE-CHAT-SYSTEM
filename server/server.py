"""
Main Entry Point for Hybrid Network Server (Phase 1).
Launches TCP File Transfer Server.
"""

import sys
from pathlib import Path

# Add project root directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from shared.config import TCP_PORT, DEFAULT_HOST
from server.tcp_server import TCPServer
from server.logger import log_event



def print_banner() -> None:
    banner = f"""========================================
HYBRID NETWORK SERVER
========================================

TCP File Server : {TCP_PORT}
UDP Chat Server : NOT STARTED
Server Status   : RUNNING

Waiting for TCP clients...
"""
    print(banner, flush=True)



def main() -> None:
    print_banner()
    log_event("Starting Hybrid Server...")

    tcp_server = TCPServer(host=DEFAULT_HOST, port=TCP_PORT)
    try:
        tcp_server.start()

        # Keep main thread running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down server gracefully...")
        tcp_server.stop()
        log_event("Server shut down by KeyboardInterrupt.")
        sys.exit(0)


if __name__ == "__main__":
    main()
