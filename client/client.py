"""
Main Entry Point for Hybrid Network Client.
Interactive console UI for TCP File Transfer and UDP Chat.
"""

import sys
import time
from shared.config import DEFAULT_HOST, TCP_PORT
from shared.utils import TermColor, print_info, print_success, print_error, print_warning
from client.tcp_client import TCPClient


def print_menu() -> None:
    menu = f"""
{TermColor.BOLD}========================================
HYBRID NETWORK CLIENT (Phase 1)
========================================{TermColor.RESET}
1. Connect to TCP Server
2. Upload File (Phase 2)
3. Download File (Phase 3)
4. List Files (Phase 2)
5. Join Chat (Phase 6)
6. Send Message (Phase 7)
7. View Online Users (Phase 6)
8. Network Statistics (Phase 10)
9. Exit
========================================
"""
    print(menu)


def main() -> None:
    tcp_client = TCPClient(host=DEFAULT_HOST, port=TCP_PORT)

    while True:
        print_menu()
        try:
            choice = input("Select an option (1-9): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting client.")
            tcp_client.disconnect()
            sys.exit(0)

        if choice == "1":
            print_info("Attempting connection to TCP Server...", tag="TCP")
            if tcp_client.connect():
                # Send PING to verify communication
                tcp_client.ping()
        elif choice == "9":
            print_info("Closing client application...", tag="SYSTEM")
            tcp_client.disconnect()
            print_success("Goodbye!")
            break
        elif choice in ["2", "3", "4", "5", "6", "7", "8"]:
            print_warning(f"Option {choice} is scheduled for implementation in upcoming phases.")
        else:
            print_error("Invalid selection. Please choose a valid menu number (1-9).")

        time.sleep(1)


if __name__ == "__main__":
    main()
