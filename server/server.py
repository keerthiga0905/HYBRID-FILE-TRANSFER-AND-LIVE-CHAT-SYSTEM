"""
Main Entry Point for Hybrid Network Server.
Launches both TCP File Transfer Server (Port 5000) and UDP Chat Server (Port 6000) concurrently.
"""

import sys
from pathlib import Path

# Add project root directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from shared.config import TCP_PORT, UDP_PORT, DEFAULT_HOST
from server.tcp_server import TCPServer
from server.udp_server import UDPServer
from server.logger import log_event


def print_banner() -> None:
    banner = f"""========================================
HYBRID NETWORK SERVER
========================================

TCP File Server : {TCP_PORT}
UDP Chat Server : {UDP_PORT}
Server Host      : {DEFAULT_HOST}
Server Status   : RUNNING

Waiting for TCP & UDP clients...
"""
    print(banner, flush=True)


def main() -> None:
    print_banner()
    log_event("Starting Hybrid Network Server (TCP Port 5000 + UDP Port 6000)...")

    tcp_server = TCPServer(host=DEFAULT_HOST, port=TCP_PORT)
    udp_server = UDPServer(host=DEFAULT_HOST, port=UDP_PORT)

    try:
        tcp_server.start()
        udp_server.start()

        print("[SERVER] TCP and UDP Servers are RUNNING. Press Ctrl+C to stop.\n", flush=True)

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down servers gracefully...", flush=True)
        tcp_server.stop()
        udp_server.stop()
        log_event("Server shut down by KeyboardInterrupt.")
        sys.exit(0)


if __name__ == "__main__":
    main()
