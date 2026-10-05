"""
Main Entry Point for Hybrid Network Client (Phase 1).
Interactive terminal application for connecting to the TCP Server.
"""

import sys
from pathlib import Path

# Add project root directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from shared.config import DEFAULT_HOST, TCP_PORT
from shared.utils import TermColor, print_info, print_success, print_error, print_warning
from client.tcp_client import TCPClient



def print_banner() -> None:
    banner = f"""========================================
HYBRID NETWORK CLIENT
========================================
Connecting to {DEFAULT_HOST}:{TCP_PORT}...
"""
    print(banner)


def main() -> None:
    print_banner()

    client = TCPClient(host=DEFAULT_HOST, port=TCP_PORT)
    connected = client.connect()

    if not connected:
        print_error("Failed to connect to server. Please check if server is running.")
        sys.exit(1)

    # Perform HELLO handshake
    client.send_hello(client_name="Client")

    print("\nPress Ctrl+C or type 9 to disconnect and exit.")

    while True:
        try:
            print("\nOptions: [1] Re-send HELLO | [9] Exit Client")
            choice = input("Select option: ").strip()

            if choice == "1":
                client.send_hello(client_name="Client")
            elif choice == "9":
                print_info("Disconnecting client...", tag="TCP")
                client.disconnect()
                print_success("Goodbye!")
                break
            else:
                print_warning("Invalid selection. Enter 1 or 9.")

        except (KeyboardInterrupt, EOFError):
            print("\nDisconnecting...")
            client.disconnect()
            sys.exit(0)


if __name__ == "__main__":
    main()
