"""
Main Entry Point for Hybrid Network Client (Module 1 - TCP Socket Engine).
Interactive terminal client for connecting to the multithreaded TCP Server,
registering a unique username, receiving a unique session ID, and managing connection state.
"""

import sys
import time
from pathlib import Path

# Add project root directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import DEFAULT_HOST, TCP_PORT
from shared.utils import TermColor, print_info, print_success, print_error, print_warning
from client.tcp_client import TCPClient


def print_banner() -> None:
    print(f"""
{TermColor.BOLD}{TermColor.CYAN}=============================================================
  HYBRID FILE TRANSFER & LIVE CHAT SYSTEM
  Module 1: TCP Socket Connection & Client Session Manager
============================================================={TermColor.RESET}""")


def prompt_connection_params() -> tuple[str, int, str]:
    """Prompts user for Server Host, Port, and Username with smart defaults."""
    print(f"\n{TermColor.YELLOW}[STEP 1] Enter Connection Parameters:{TermColor.RESET}")
    
    host_input = input(f"Server IP [{DEFAULT_HOST}]: ").strip()
    host = host_input if host_input else DEFAULT_HOST

    port_input = input(f"TCP Port [{TCP_PORT}]: ").strip()
    try:
        port = int(port_input) if port_input else TCP_PORT
    except ValueError:
        print_warning(f"Invalid port entered. Falling back to default: {TCP_PORT}")
        port = TCP_PORT

    while True:
        username = input("Enter a unique Username (alphanumeric, 2-30 chars): ").strip()
        clean = username.replace("_", "").replace("-", "")
        if username and len(username) >= 2 and len(username) <= 30 and clean.isalnum():
            break
        print_warning("Username must be between 2 and 30 characters (letters, numbers, '-' or '_'). Please re-enter.")

    return host, port, username


def main() -> None:
    print_banner()

    host, port, username = prompt_connection_params()
    client = TCPClient(host=host, port=port)

    print_info(f"Connecting to TCP server at {host}:{port}...", tag="TCP")
    if not client.connect():
        print_error(f"Could not establish connection to {host}:{port}. Ensure server is running.")
        sys.exit(1)

    # Register username and obtain unique session ID
    current_username = username
    while True:
        print_info(f"Registering username '{current_username}' with server...", tag="TCP")
        resp = client.send_hello(client_name=current_username)

        if resp and resp.get("status") == "SUCCESS":
            session_id = resp.get("session_id", "N/A")
            print(f"""
{TermColor.GREEN}=============================================================
  [SUCCESS] REGISTERED WITH TCP SERVER
  Session ID: {session_id}
  Username:   {current_username}
  Server:     {host}:{port}
============================================================={TermColor.RESET}""")
            break
        elif resp and resp.get("code") == "DUPLICATE_USERNAME":
            print_error(f"Registration Failed: {resp.get('message')}")
            current_username = input("\nPlease enter a different unique username: ").strip()
        else:
            err_msg = resp.get("message") if resp else "Server did not respond."
            print_error(f"Registration Failed: {err_msg}")
            current_username = input("\nPlease re-enter a valid username: ").strip()

    # Interactive Client Command Loop
    while True:
        try:
            print(f"""
{TermColor.BOLD}--- Client Session Options ---{TermColor.RESET}
[1] View Current Session Info
[2] Ping Server (Re-send HELLO)
[3] List Server Files
[9] Disconnect & Exit
""")
            choice = input("Select an option [1-9]: ").strip()

            if choice == "1":
                print(f"""
  Connected Server: {client.host}:{client.port}
  Username:         {client.username}
  Session ID:       {client.session_id}
  Socket State:     {'CONNECTED' if client.is_connected else 'DISCONNECTED'}
""")
            elif choice == "2":
                print_info("Sending HELLO ping to server...", tag="TCP")
                ping_resp = client.send_hello(client_name=client.username)
                if ping_resp and ping_resp.get("status") == "SUCCESS":
                    print_success(f"Server ACK received: {ping_resp.get('message')}")
            elif choice == "3":
                files = client.list_files()
                if files is not None:
                    print_info(f"Server Files Available: {len(files)} files", tag="TCP")
                    for f in files:
                        size_kb = f.get('size', 0) / 1024
                        print(f"  • {f.get('filename')} ({size_kb:.1f} KB)")
            elif choice == "9":
                print_info("Disconnecting from TCP server...", tag="TCP")
                client.disconnect()
                print_success("Disconnected cleanly. Goodbye!")
                break
            else:
                print_warning("Invalid choice. Please select 1, 2, 3, or 9.")

        except (KeyboardInterrupt, EOFError):
            print("\nDisconnecting...")
            client.disconnect()
            break


if __name__ == "__main__":
    main()
