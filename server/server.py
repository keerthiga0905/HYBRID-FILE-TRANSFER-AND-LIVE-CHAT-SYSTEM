"""
Main Entry Point for Hybrid Network Server.
Launches TCP File Transfer Server and UDP Chat Server (Phase 6+).
"""

import sys
import time
from shared.config import TCP_PORT, UDP_PORT, DEFAULT_HOST
from server.tcp_server import TCPServer
from server.logger import log_event


def print_banner() -> None:
    banner = f"""
========================================
HYBRID NETWORK SERVER
=====================

TCP File Server : {TCP_PORT}
UDP Chat Server  : {UDP_PORT} (Phase 6 Ready)
Server Host      : {DEFAULT_HOST}
Server Status    : RUNNING
==========================
"""
    print(banner)


def main() -> None:
    print_banner()
    log_event("Starting Hybrid Server...")

    # Start TCP Server
    tcp_server = TCPServer(host=DEFAULT_HOST, port=TCP_PORT)
    try:
        tcp_server.start()
        print("[SERVER] Press Ctrl+C to stop the server.\n")

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down server gracefully...")
        tcp_server.stop()
        log_event("Server shut down by user KeyboardInterrupt.")
        sys.exit(0)


if __name__ == "__main__":
    main()
