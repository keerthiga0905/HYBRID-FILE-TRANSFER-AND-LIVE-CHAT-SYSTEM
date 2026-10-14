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

from typing import Optional
from shared.config import DEFAULT_HOST, TCP_PORT, UDP_PORT
from shared.utils import TermColor, print_info, print_success, print_error, print_warning
from client.tcp_client import TCPClient
from client.udp_client import UDPClient


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


def print_progress(bytes_transferred: int, total_bytes: int, speed: float, prefix: str = "Transfer") -> None:
    """Renders real-time transfer progress bar with bytes and speed."""
    percent = (bytes_transferred / total_bytes * 100.0) if total_bytes > 0 else 100.0
    bar_len = 24
    filled = int(bar_len * bytes_transferred // (total_bytes if total_bytes > 0 else 1))
    bar = "=" * filled + "-" * (bar_len - filled)
    sys.stdout.write(f"\r  [{prefix}] [{bar}] {percent:5.1f}% ({bytes_transferred:,}/{total_bytes:,} bytes) | {speed:5.2f} MB/s")
    sys.stdout.flush()
    if bytes_transferred >= total_bytes:
        print()


def pick_file_path() -> str:
    """Allows user to type a file path or use 'browse' for a GUI file dialog."""
    print(f"\n{TermColor.YELLOW}Enter file path (e.g. storage/sample.pdf, text.txt) or type 'browse' for file dialog:{TermColor.RESET}")
    path_input = input("File Path: ").strip().strip('"').strip("'")
    if path_input.lower() == "browse":
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askopenfilename(
                title="Select File to Send",
                filetypes=[
                    ("All Files (*.*)", "*.*"),
                    ("Documents (*.pdf;*.docx;*.txt)", "*.pdf;*.docx;*.txt"),
                    ("Images (*.jpg;*.png;*.jpeg)", "*.jpg;*.png;*.jpeg"),
                    ("Media & Archives (*.zip;*.mp4)", "*.zip;*.mp4")
                ]
            )
            root.destroy()
            if selected:
                return selected
        except Exception:
            print_warning("GUI File Dialog not available in this environment. Please specify path.")
            path_input = input("File Path: ").strip().strip('"').strip("'")
    return path_input


def handle_send_peer_file(client: TCPClient) -> None:
    """Module 2: Sender feature - select user, choose file, compute SHA-256, and stream transfer."""
    print_info("Fetching list of connected users...", tag="TCP")
    users = client.list_online_users()
    if not users:
        print_warning("No other users are currently connected. Open another terminal and run client/client.py with a different username.")
        return

    print(f"\n{TermColor.BOLD}--- Available Online Receivers ---{TermColor.RESET}")
    for idx, u in enumerate(users, 1):
        print(f"  [{idx}] {u.get('username')} (Session: {u.get('session_id')}, Status: {u.get('status')})")

    sel = input(f"\nSelect receiver by number [1-{len(users)}] or enter username: ").strip()
    target_user = None
    if sel.isdigit() and 1 <= int(sel) <= len(users):
        target_user = users[int(sel) - 1].get("username")
    elif sel:
        target_user = sel

    if not target_user:
        print_error("Invalid receiver selected.")
        return

    filepath = pick_file_path()
    if not filepath or not Path(filepath).exists():
        print_error(f"File not found: '{filepath}'")
        return

    path_obj = Path(filepath).resolve()
    print(f"""
{TermColor.CYAN}--- Peer File Transfer Details ---{TermColor.RESET}
  Sender:       {client.username}
  Receiver:     {target_user}
  Filename:     {path_obj.name}
  Size:         {path_obj.stat().st_size:,} bytes ({path_obj.stat().st_size / (1024*1024):.2f} MB)
""")

    print_info(f"Submitting transfer offer to '{target_user}'...", tag="TCP")
    res = client.send_file_to_peer(
        receiver=target_user,
        file_path_str=str(path_obj),
        timeout=45.0,
        progress_callback=lambda b, t, s: print_progress(b, t, s, prefix="Uploading Stream")
    )

    if res.get("success"):
        print_success(f"Transfer of '{path_obj.name}' successfully sent and staged on relay!")
        print_info(f"Receiver '{target_user}' can now accept and download it.")
    else:
        print_error(f"Transfer Failed: {res.get('error')}")


def handle_check_incoming_transfers(client: TCPClient) -> None:
    """Module 2: Receiver feature - display requests, accept/reject, download and verify SHA-256."""
    print_info("Checking for incoming transfer requests...", tag="TCP")
    incoming = client.check_incoming_transfers()
    if not incoming:
        print_info("No pending file transfer offers for you at this time.", tag="TCP")
        return

    for req in incoming:
        tid = req.get("transfer_id")
        sender = req.get("sender")
        filename = req.get("filename")
        filesize = int(req.get("filesize", 0))
        checksum = req.get("checksum")

        print(f"""
{TermColor.YELLOW}=============================================================
  [INCOMING TRANSFER OFFER]
  From Sender:  {sender}
  File Name:    {filename}
  File Size:    {filesize:,} bytes ({filesize / 1024:.1f} KB)
  Transfer ID:  {tid}
  SHA-256 Hash: {checksum[:16]}...{checksum[-8:]}
============================================================={TermColor.RESET}""")

        choice = input("Do you want to ACCEPT or REJECT this file? [A/R]: ").strip().upper()
        if choice == "A" or choice == "ACCEPT":
            custom_dir = input("Enter destination directory (Press Enter for default storage/downloads/): ").strip()
            dest_dir = custom_dir if custom_dir else None

            print_info(f"Accepting transfer [{tid}] and waiting for file stream...", tag="TCP")
            result = client.accept_and_receive_transfer(
                transfer_id=tid,
                filename=filename,
                filesize=filesize,
                checksum=checksum,
                custom_downloads_dir=dest_dir,
                timeout=45.0,
                progress_callback=lambda b, t, s: print_progress(b, t, s, prefix="Downloading Stream")
            )

            if result.get("success"):
                print(f"""
{TermColor.GREEN}=============================================================
  [SUCCESS] FILE RECEIVED & VERIFIED!
  Saved File:   {result.get('saved_path')}
  File Size:    {result.get('filesize'):,} bytes
  SHA-256 Hash: {result.get('checksum')}
  Integrity:    100% VERIFIED MATCH
============================================================={TermColor.RESET}""")
            else:
                print_error(f"File transfer failed: {result.get('error')}")
        else:
            reason = input("Optional rejection reason: ").strip() or "Declined by receiver"
            rej_res = client.respond_to_transfer(tid, "REJECT", reason=reason)
            if rej_res.get("success"):
                print_warning(f"Rejected file transfer [{tid}] from '{sender}'.")
            else:
                print_error(f"Failed to submit rejection: {rej_res.get('error')}")


def handle_list_transfers(client: TCPClient) -> None:
    """Module 3: Displays transfer list showing available files, size, sender, receiver, stored bytes, and status."""
    print_info("Fetching transfers registry from server...", tag="TCP")
    transfers = client.list_all_transfers()
    if not transfers:
        print_info("No transfers recorded yet.", tag="TCP")
        return

    print(f"\n{TermColor.BOLD}{TermColor.CYAN}--- File Transfers Registry ---{TermColor.RESET}")
    print(f"{'Transfer ID':<14} | {'Filename':<20} | {'Size':<10} | {'Stored':<10} | {'Sender':<14} | {'Receiver':<14} | {'Status':<12}")
    print("-" * 105)
    for t in transfers:
        tid = t.get("transfer_id", "")[:12]
        fname = t.get("filename", "")[:18]
        fsize = f"{t.get('filesize', 0):,} B"
        stored = f"{t.get('bytes_stored', 0):,} B"
        sender = t.get("sender", "")[:12]
        receiver = t.get("receiver", "")[:12]
        status = t.get("status", "")
        status_color = TermColor.GREEN if status in ["COMPLETED", "STAGED"] else (TermColor.RED if "FAIL" in status or status == "CANCELLED" else TermColor.YELLOW)
        print(f"{tid:<14} | {fname:<20} | {fsize:<10} | {stored:<10} | {sender:<14} | {receiver:<14} | {status_color}{status:<12}{TermColor.RESET}")


def handle_resume_transfer(client: TCPClient) -> None:
    """Module 3: Resumes interrupted upload or download using verified byte offset and SHA-256 verification."""
    print_info("Fetching resumable transfers...", tag="TCP")
    transfers = client.list_all_transfers()
    if not transfers:
        print_warning("No transfers found on server.")
        return

    resumable = [
        t for t in transfers
        if t.get("status") not in ["COMPLETED", "CANCELLED", "REJECTED"] and (t.get("sender") == client.username or t.get("receiver") == client.username)
    ]

    if not resumable:
        print_info("No interrupted or resumable transfers found for your user.", tag="TCP")
        return

    print(f"\n{TermColor.BOLD}--- Resumable Transfers for {client.username} ---{TermColor.RESET}")
    for idx, t in enumerate(resumable, 1):
        role = "Sender (Upload)" if t.get("sender") == client.username else "Receiver (Download)"
        print(f"  [{idx}] {t.get('transfer_id')} | {t.get('filename')} ({t.get('filesize'):,} bytes) | Stored: {t.get('bytes_stored'):,} | Role: {role} | Status: {t.get('status')}")

    sel = input(f"\nSelect transfer to resume [1-{len(resumable)}]: ").strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(resumable)):
        print_error("Invalid selection.")
        return

    target_t = resumable[int(sel) - 1]
    tid = target_t.get("transfer_id")
    fname = target_t.get("filename")
    fsize = int(target_t.get("filesize", 0))
    checksum = target_t.get("checksum", "")

    if target_t.get("sender") == client.username:
        filepath = pick_file_path()
        if not filepath or not Path(filepath).exists():
            print_error(f"Local file not found: '{filepath}'")
            return
        print_info(f"Resuming upload of [{tid}]...", tag="TCP")
        res = client.resume_peer_upload(
            transfer_id=tid,
            file_path_str=filepath,
            progress_callback=lambda b, t, s: print_progress(b, t, s, prefix="Resuming Upload")
        )
        if res.get("success"):
            print_success(f"Upload successfully resumed & staged! Offset: {res.get('offset_resumed'):,} bytes. SHA-256 verified.")
        else:
            print_error(f"Resume upload failed: {res.get('error')}")

    else:
        print_info(f"Resuming download of [{tid}]...", tag="TCP")
        res = client.resume_peer_download(
            transfer_id=tid,
            filename=fname,
            filesize=fsize,
            expected_checksum=checksum,
            progress_callback=lambda b, t, s: print_progress(b, t, s, prefix="Resuming Download")
        )
        if res.get("success"):
            print_success(f"Download successfully resumed & verified! Saved to: {res.get('saved_path')}")
        else:
            print_error(f"Resume download failed: {res.get('error')}")


def handle_cancel_transfer(client: TCPClient) -> None:
    """Module 3: Allows users to cancel their own pending or active transfers."""
    print_info("Fetching active transfers...", tag="TCP")
    transfers = client.list_all_transfers()
    if not transfers:
        print_info("No transfers found on server.", tag="TCP")
        return

    cancellable = [
        t for t in transfers
        if t.get("status") not in ["COMPLETED", "CANCELLED"] and (t.get("sender") == client.username or t.get("receiver") == client.username)
    ]

    if not cancellable:
        print_info("No active or pending transfers eligible for cancellation.", tag="TCP")
        return

    print(f"\n{TermColor.BOLD}--- Your Active Transfers ---{TermColor.RESET}")
    for idx, t in enumerate(cancellable, 1):
        role = "Sender" if t.get("sender") == client.username else "Receiver"
        print(f"  [{idx}] {t.get('transfer_id')} | {t.get('filename')} ({t.get('filesize'):,} bytes) | Role: {role} | Status: {t.get('status')}")

    sel = input(f"\nSelect transfer to cancel [1-{len(cancellable)}] or enter Transfer ID: ").strip()
    target_tid = None
    if sel.isdigit() and 1 <= int(sel) <= len(cancellable):
        target_tid = cancellable[int(sel) - 1].get("transfer_id")
    elif sel:
        target_tid = sel

    if not target_tid:
        print_error("Invalid selection.")
        return

    res = client.cancel_transfer(target_tid)
    if res.get("success"):
        print_success(f"Transfer [{target_tid}] cancelled successfully.")
    else:
        print_error(f"Cancellation failed: {res.get('error')}")


def handle_udp_presence(udp_client: Optional[UDPClient]) -> None:
    """Module 4: Displays real-time UDP online user presence and heartbeat monitor."""
    if not udp_client or not udp_client.is_connected:
        print_warning("UDP Client is not connected to presence server.")
        return

    print_info("Querying UDP Presence Server (Port 6000) via datagram...", tag="UDP")
    users = udp_client.get_online_users()
    if not users:
        print_warning("No online users reported by UDP Server.")
        return

    print(f"\n{TermColor.BOLD}==========================================================================================")
    print("  REAL-TIME UDP ONLINE USER PRESENCE REGISTRY (Port 6000)")
    print(f"=========================================================================================={TermColor.RESET}")
    print(f"{'Username':<18} | {'Session ID':<12} | {'UDP Endpoint':<24} | {'Status':<10} | {'Last Seen'}")
    print("-" * 90)
    for u in users:
        uname = u.get("username", "")[:16]
        sess = str(u.get("session_id", "N/A"))[:10]
        endpoint = str(u.get("endpoint", "N/A"))[:22]
        st = u.get("status", "OFFLINE")
        color = TermColor.GREEN if st == "ONLINE" else TermColor.RED
        last_seen = u.get("last_seen", "")
        print(f"{uname:<18} | {sess:<12} | {endpoint:<24} | {color}{st:<10}{TermColor.RESET} | {last_seen}")
    
    events = udp_client.get_presence_events()
    if events:
        print(f"\n{TermColor.CYAN}Recent Presence Change Notifications ({len(events)}):{TermColor.RESET}")
        for evt in events[-5:]:
            print(f"  • [{evt.get('timestamp')}] {evt.get('username')} -> {evt.get('status')} ({evt.get('event')})")

    print(f"\nActive Heartbeat: {'RUNNING (Every 5s)' if udp_client.is_heartbeat_running else 'STOPPED'}")


def handle_live_chat(udp_client: Optional[UDPClient]) -> None:
    """Module 5: Interactive real-time UDP Live Chat Room supporting Group & Private messaging."""
    if not udp_client or not udp_client.is_connected:
        print_warning("UDP Client is not connected to chat server.")
        return

    print(f"""
{TermColor.BOLD}{TermColor.CYAN}========================================================================
  UDP LIVE CHAT ROOM (Port 6000)
========================================================================{TermColor.RESET}
  Logged in as: {TermColor.GREEN}{udp_client.username}{TermColor.RESET}
  Commands:
    {TermColor.YELLOW}/users{TermColor.RESET}                     - View online users
    {TermColor.YELLOW}/private <user> <msg>{TermColor.RESET}  - Send private message to a specific user
    {TermColor.YELLOW}/p <user> <msg>{TermColor.RESET}        - Shorthand for /private
    {TermColor.YELLOW}/group <msg>{TermColor.RESET}           - Send group message to all online users
    {TermColor.YELLOW}/history{TermColor.RESET}                  - View chat history
    {TermColor.YELLOW}<any text>{TermColor.RESET}                - Broadcasts directly to group chat
    {TermColor.YELLOW}/quit{TermColor.RESET}                    - Exit chat room and return to main menu
========================================================================
""")
    while True:
        try:
            cmd_line = input(f"[{udp_client.username}@Chat] > ").strip()
            if not cmd_line:
                continue

            if cmd_line.lower() in ["/quit", "/exit", "/q"]:
                print_info("Exiting Live Chat Room...", tag="UDP")
                break

            elif cmd_line.lower() == "/users":
                users = udp_client.get_online_users()
                print_info(f"Online Users ({len(users)} found):", tag="UDP")
                for u in users:
                    st = u.get("status", "OFFLINE")
                    color = TermColor.GREEN if st == "ONLINE" else TermColor.RED
                    print(f"  • {u.get('username'):16} | {color}{st}{TermColor.RESET} | Endpoint: {u.get('endpoint')}")

            elif cmd_line.lower() == "/history":
                history = udp_client.get_chat_history()
                print_info(f"Chat History ({len(history)} messages):", tag="UDP")
                for m in history:
                    mode = m.get("mode", "GROUP")
                    sender = m.get("sender")
                    recip = m.get("recipient", "ALL")
                    txt = m.get("message")
                    ts = m.get("timestamp")
                    st = m.get("status", "Delivered")
                    if mode == "PRIVATE":
                        print(f"  [{ts}] [PRIVATE {sender}->{recip}] {txt} ({st})")
                    else:
                        print(f"  [{ts}] [GROUP {sender}] {txt} ({st})")

            elif cmd_line.startswith("/private ") or cmd_line.startswith("/p "):
                parts = cmd_line.split(" ", 2)
                if len(parts) < 3 or not parts[2].strip():
                    print_warning("Usage: /private <username> <message>")
                    continue
                target_user = parts[1].strip()
                private_msg = parts[2].strip()
                res = udp_client.send_private_message(recipient=target_user, message_text=private_msg)
                if not res.get("success"):
                    print_error(f"Failed to send private message: {res.get('error')}")

            elif cmd_line.startswith("/group ") or cmd_line.startswith("/g "):
                parts = cmd_line.split(" ", 1)
                if len(parts) < 2 or not parts[1].strip():
                    print_warning("Usage: /group <message>")
                    continue
                group_msg = parts[1].strip()
                res = udp_client.send_group_message(group_msg)
                if not res.get("success"):
                    print_error(f"Failed to send group message: {res.get('error')}")

            else:
                # Default text sends as group message
                res = udp_client.send_group_message(cmd_line)
                if not res.get("success"):
                    print_error(f"Failed to send message: {res.get('error')}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting Live Chat Room...")
            break


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
    session_id = "N/A"
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

    # Step 2: Initialize UDP Client with same authenticated session for Live Presence & Chat
    udp_client = UDPClient(host=host, port=UDP_PORT, username=current_username, session_id=session_id)
    if udp_client.connect():
        resp_udp = udp_client.join_chat()
        if resp_udp and resp_udp.get("status") == "SUCCESS":
            print_success(f"Registered with UDP Presence & Chat Engine on port {UDP_PORT}!")
        else:
            print_warning("UDP Presence registration did not complete (Server may not be running UDP).")

    # Interactive Client Command Loop
    while True:
        try:
            print(f"""
{TermColor.BOLD}--- Client Session Options ---{TermColor.RESET}
[1] View Current Session Info
[2] Ping Server (Re-send HELLO)
[3] List Server Repository Files
[4] List Online Connected Users (TCP & UDP)
[5] Send File to User (Peer-to-Peer Transfer)
[6] Check Incoming Transfer Requests (Receive/Verify)
[7] View File Transfers Registry (Status, Size, Stored Bytes)
[8] Resume Interrupted File Transfer (Upload / Download)
[9] Cancel Active or Pending Transfer
[10] View Real-Time UDP Online Presence & Heartbeat Monitor
[11] Enter Real-Time UDP Live Chat Room (Group & Private)
[0] Disconnect & Exit
""")
            choice = input("Select an option [0-11]: ").strip()

            if choice == "1":
                print(f"""
  Connected Server: {client.host}:{client.port}
  Username:         {client.username}
  Session ID:       {client.session_id}
  TCP Socket State: {'CONNECTED' if client.is_connected else 'DISCONNECTED'}
  UDP Presence:     {'ONLINE (5s Heartbeat)' if udp_client and udp_client.is_heartbeat_running else 'OFFLINE'}
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

            elif choice == "4":
                users = client.list_online_users()
                print_info(f"Online TCP Users ({len(users)} found):", tag="TCP")
                for u in users:
                    print(f"  • Username: {u.get('username'):15} | Session: {u.get('session_id')} | Status: {u.get('status')}")

            elif choice == "5":
                handle_send_peer_file(client)

            elif choice == "6":
                handle_check_incoming_transfers(client)

            elif choice == "7":
                handle_list_transfers(client)

            elif choice == "8":
                handle_resume_transfer(client)

            elif choice == "9":
                handle_cancel_transfer(client)

            elif choice == "10":
                handle_udp_presence(udp_client)

            elif choice == "11":
                handle_live_chat(udp_client)

            elif choice in ["0", "exit", "quit"]:
                print_info("Disconnecting from TCP & UDP servers...", tag="TCP")
                if udp_client:
                    udp_client.leave_chat()
                client.disconnect()
                print_success("Disconnected cleanly. Goodbye!")
                break
            else:
                print_warning("Invalid choice. Please select 0-11.")

        except (KeyboardInterrupt, EOFError):
            print("\nDisconnecting...")
            if udp_client:
                udp_client.leave_chat()
            client.disconnect()
            break


if __name__ == "__main__":
    main()

