# HYBRID TRANSFER: Fast File Transfer & Real-Time Communication System
> **An Academic & Production-Grade Computer Networks System using Real Python TCP & UDP Socket Programming**

---

## 📌 Executive Summary

**HYBRID TRANSFER** ("Fast File Transfer. Real-Time Communication. One Network.") is a dual-protocol networking application engineered in Python 3.12+ to demonstrate why **TCP (Transmission Control Protocol)** and **UDP (User Datagram Protocol)** are chosen for distinct network communication tasks:

- **TCP (Port 5000):** Reliable, connection-oriented byte stream sockets (`SOCK_STREAM`) for chunked file uploads, downloads, interrupted transfer RESUME capability, and SHA-256 checksum verification.
- **UDP (Port 6000):** Low-latency, connectionless datagram sockets (`SOCK_DGRAM`) with custom application-layer reliability (Sequence Numbers, 1s ACK Timeout Retransmissions, Duplicate Detection) for live multi-user chat, heartbeat presence tracking, and simulated packet loss analysis.

---

## 🚀 Module 1: TCP Socket Programming & Multi-Client Session Engine

### 1. Module 1 Objectives & Deliverables
* **Real TCP Sockets:** Pure standard-library Python sockets utilizing `socket.AF_INET` and `socket.SOCK_STREAM`.
* **Port 5000 Listener:** Multithreaded TCP server accepting simultaneous incoming client connections.
* **Unique Client Session IDs:** Unique 8-hex session tokens (`uuid.uuid4().hex[:8]`) assigned upon connection.
* **Username Registration & Validation:** Interactive client prompt requiring unique alphanumeric usernames (2–30 chars).
* **Duplicate Username Detection:** Real-time rejection (`DUPLICATE_USERNAME`) if another connected client is holding the username.
* **Server-Side Registry:** Thread-safe state tracking (`session_id`, `username`, `ip`, `port`, `status="CONNECTED"`, `connected_at`).
* **Connection Lifecycle Telemetry:** Real-time server logging for connection, registration, and disconnection/reset events.
* **Framed Stream Protocol:** 4-byte Big-Endian length-prefixed JSON protocol preventing TCP stream fragmentation / sticking.

---

### 2. Modular Project Structure

```text
CN-project/
├── server/                      # Server-side networking implementation
│   ├── tcp_server.py           # Core Module 1 TCP Server & Multithreaded Handler
│   ├── server.py               # Combined Server Entry Point (TCP 5000 + UDP 6000)
│   ├── client_registry.py      # Client state & session tracking
│   ├── file_manager.py         # Storage & upload streaming handlers
│   └── logger.py               # Structured event logging
│
├── client/                      # Client-side networking implementation
│   ├── tcp_client.py           # Core Module 1 TCP Client socket wrapper & framing
│   ├── client.py               # Interactive CLI Client (Terminal connection & menu)
│   ├── client_controller.py    # Bridge between Client UI and networking sockets
│   └── file_manager.py         # Client downloads directory & SHA-256 validation
│
├── shared/                      # Shared protocols, config, and utilities
│   ├── protocol.py             # 4-Byte Length-Prefixed Framing (send_message / receive_message)
│   ├── config.py               # Network constants (DEFAULT_HOST="127.0.0.1", TCP_PORT=5000)
│   ├── checksum.py             # SHA-256 calculation & constant-time verification
│   ├── stats.py                # Real-time network throughput & packet metrics
│   └── utils.py                # ANSI terminal colors & formatted logging
│
├── tests/                       # Automated unit test suite
│   ├── test_tcp.py             # Module 1 TCP Tests (Concurrency, Sessions, Registry, Errors)
│   └── ...                     # Additional protocol tests
│
└── README.md                    # System documentation & setup guide
```

---

### 3. Explanation of Important Files for Module 1

| File | Path | Key Role & Implementation Details |
| :--- | :--- | :--- |
| **`server/tcp_server.py`** | [tcp_server.py](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/server/tcp_server.py) | **Multithreaded TCP Server Engine.** Binds to `127.0.0.1:5000`, spawns `_accept_loop`, generates unique `session_id`, and starts a daemon thread (`_handle_client`) per client. Enforces username formatting, prevents duplicate usernames, maintains `clients_registry`, and guarantees cleanup in `finally`. |
| **`client/tcp_client.py`** | [tcp_client.py](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/client/tcp_client.py) | **Real TCP Socket Client.** Creates `socket.socket(AF_INET, SOCK_STREAM)`, connects to `(host, port)`, sends framed `HELLO` payload with username, receives assigned `session_id`, and manages socket teardown. |
| **`client/client.py`** | [client.py](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/client/client.py) | **Interactive Terminal Client.** Prompts user for Server IP (`127.0.0.1`), Port (`5000`), and Username. Loops on duplicate username rejection until valid, prints connection card, and offers interactive session options. |
| **`shared/protocol.py`** | [protocol.py](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/shared/protocol.py) | **TCP Stream Framing.** Implements `send_message()` and `receive_message()`. Uses `struct.pack(">I", length)` to prepend a 4-byte Big-Endian length header before JSON payload bytes. Uses `recv_exact()` to guarantee entire message receipt without boundary errors. |
| **`shared/config.py`** | [config.py](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/shared/config.py) | Centralized network parameters (`DEFAULT_HOST = "127.0.0.1"`, `TCP_PORT = 5000`, `CHUNK_SIZE = 4096`). |

---

### 4. Step-by-Step Windows PowerShell Commands to Run Module 1

Open separate **Windows PowerShell** windows from the project root directory (`c:\Users\KEERTHIGA M\Desktop\CN-project`):

#### Terminal 1: Run TCP Server
```powershell
python server/tcp_server.py
```
*Expected Server Output:*
```text
[OK 10:30:00] TCP File Server listening on 127.0.0.1:5000
[TCP 10:30:00] TCP Server running on 127.0.0.1:5000. Press Ctrl+C to terminate.
```

#### Terminal 2: Run Client 1 (Alice)
```powershell
python client/client.py
```
*Enter inputs:*
- **Server IP:** Press `Enter` (defaults to `127.0.0.1`)
- **TCP Port:** Press `Enter` (defaults to `5000`)
- **Username:** `Alice`

*Expected Terminal 2 Output:*
```text
[OK 10:30:15] TCP CONNECTION ESTABLISHED
[INFO 10:30:15] Registering username 'Alice' with server...
[OK 10:30:15] Registered as 'Alice' | Session ID: [4a0bbfc0]
=============================================================
  [SUCCESS] REGISTERED WITH TCP SERVER
  Session ID: 4a0bbfc0
  Username:   Alice
  Server:     127.0.0.1:5000
=============================================================
```

#### Terminal 3: Run Client 2 (Bob - Concurrent Connection)
```powershell
python client/client.py
```
*Enter inputs:*
- **Server IP:** Press `Enter` (defaults to `127.0.0.1`)
- **TCP Port:** Press `Enter` (defaults to `5000`)
- **Username:** `Bob`

*Expected Terminal 3 Output:*
```text
[OK 10:30:30] TCP CONNECTION ESTABLISHED
[INFO 10:30:30] Registering username 'Bob' with server...
[OK 10:30:30] Registered as 'Bob' | Session ID: [7e50cf3e]
=============================================================
  [SUCCESS] REGISTERED WITH TCP SERVER
  Session ID: 7e50cf3e
  Username:   Bob
  Server:     127.0.0.1:5000
=============================================================
```

#### Terminal 4: Test Duplicate Username Rejection (Alice duplicate check)
```powershell
python client/client.py
```
*Enter inputs:*
- **Username:** `Alice`
- *Observation:* Server rejects with `[ERROR] Registration Failed: Username 'Alice' is already taken by another connected user.`
- Prompt asks for a different unique username. Enter `Charlie` to successfully connect!

---

### 5. Running Automated Unit Tests for Module 1

Run the dedicated Module 1 TCP unit tests:
```powershell
python -m unittest tests/test_tcp.py
```
*All 8 tests pass in < 1 second, validating listening sockets, concurrent multi-client threads, unique session IDs, username validation, duplicate rejection, and graceful disconnect registry updates.*

---

## 📁 Module 2: Complete TCP-Based Peer File Transfer System

### 1. Module 2 Objectives & Architecture
Module 2 enables real-time peer-to-peer file transfer between any two connected users mediated by the reliable TCP server relay without breaking Module 1.

```text
SENDER (Alice)                   TCP SERVER (Relay)                 RECEIVER (Bob)
     │                                    │                                 │
     │ 1. GET_USERS                       │                                 │
     ├───────────────────────────────────>│                                 │
     │<── [Bob (Online)] ─────────────────┤                                 │
     │                                    │                                 │
     │ 2. PEER_TRANSFER_OFFER             │                                 │
     │    (filename, size, SHA-256, TID)  │                                 │
     ├───────────────────────────────────>│ [Recorded in Inbox]             │
     │<── OFFER_SENT ─────────────────────┤                                 │
     │                                    │ 3. CHECK_INCOMING_TRANSFERS     │
     │                                    │<────────────────────────────────┤
     │                                    ├──── INBOX_LIST (Offer) ────────>│
     │                                    │                                 │
     │                                    │ 4. PEER_TRANSFER_RESPONSE       │
     │                                    │    (TID, decision: "ACCEPT")    │
     │                                    │<────────────────────────────────┤
     │                                    ├──── SUCCESS ───────────────────>│
     │ 5. CHECK_STATUS (ACCEPTED)         │                                 │
     ├───────────────────────────────────>│                                 │
     │                                    │                                 │
     │ 6. PEER_UPLOAD_START (TID)         │                                 │
     ├───────────────────────────────────>│                                 │
     │<── READY ──────────────────────────┤                                 │
     │=== 4096-byte chunk stream =========>│ (Staged & SHA-256 Verified)     │
     │<── UPLOAD_COMPLETE ────────────────┤                                 │
     │                                    │                                 │
     │                                    │ 7. PEER_DOWNLOAD_START (TID)    │
     │                                    │<────────────────────────────────┤
     │                                    ├──── READY ─────────────────────>│
     │                                    │=== 4096-byte chunk stream ======>│
     │                                    │                                 │
     │                                    │ 8. Calculate SHA-256 Checksum   │
     │                                    │    verify_checksum() MATCH!     │
     │                                    │    Rename .part to final file   │
     │                                    │                                 │
     │                                    │ 9. PEER_DOWNLOAD_COMPLETE       │
     │                                    │<────────────────────────────────┤
     │                                    │ [Staged file cleaned up]        │
     │                                    ├──── Finalized ACK ─────────────>│
```

---

### 2. Core Features Implemented

#### Sender Features:
1. **Show Connected Users:** Queries `GET_USERS` and displays numbered list of online peers.
2. **Choose Receiver:** Prompt to choose receiver by username or number.
3. **File Selection:** Choose path directly or type `browse` for GUI file dialog.
4. **Any File Type Supported:** Pure binary transfer supporting `PDF`, `DOCX`, `TXT`, `JPG`, `PNG`, `ZIP`, `MP4`, and more.
5. **Metadata Transmission:** Sends `filename`, `filesize`, unique `transfer_id`, and `SHA-256` checksum.
6. **Live Progress:** Visual progress bar with bytes transferred, percent, and MB/s speed.
7. **Receiver Notification:** Receiver's inbox is immediately notified of incoming request.

#### Receiver Features:
1. **Request Inspection:** Displays sender's username, filename, size, transfer ID, and SHA-256 checksum.
2. **Accept or Reject:** Receiver can accept (`[A]`) or reject (`[R]`).
3. **Transfer Only Upon Acceptance:** Zero file bytes are streamed if receiver declines.
4. **Configurable Downloads Directory:** Default is `storage/downloads/`, or user can specify custom path.
5. **Live Download Progress:** Visual progress bar with percentage, bytes received, and speed.
6. **SHA-256 Verification:** Receiver computes SHA-256 on `.part` file and compares with sender's checksum using `hmac.compare_digest`.
7. **Integrity Guaranteed:** Success reported only after 100% byte receipt and checksum match.

---

### 3. Step-by-Step Windows PowerShell Commands to Test Module 2

Open three separate **Windows PowerShell** windows:

#### Terminal 1: TCP Server
```powershell
python server/tcp_server.py
```

#### Terminal 2: Client 1 (Alice - Sender)
```powershell
python client/client.py
```
- Username: `Alice`

#### Terminal 3: Client 2 (Bob - Receiver)
```powershell
python client/client.py
```
- Username: `Bob`

---

#### Step 4: Perform Peer File Transfer
1. In **Terminal 2 (Alice)**:
   - Select option `[5] Send File to User (Peer-to-Peer Transfer)`.
   - Select receiver: `Bob`.
   - Enter file path: `storage/sample_test_1mb.dat` (or any image, pdf, text, or zip file).
   - Alice computes SHA-256 and submits offer.

2. In **Terminal 3 (Bob)**:
   - Select option `[6] Check Incoming Transfer Requests (Receive/Verify)`.
   - Bob sees incoming transfer offer from Alice.
   - Type `A` to **ACCEPT**.
   - Press **Enter** for default `storage/downloads/` directory.

3. **Observe Live Streaming & Integrity Verification:**
   - Alice streams 4096-byte chunks with live progress.
   - Bob receives 4096-byte chunks with live progress.
   - Bob calculates SHA-256 of received file and verifies exact match with Alice's original file!

---

### 4. Running Automated Tests for Module 2
```powershell
python -m unittest tests/test_file_transfer.py
```
*All 11 tests pass in < 1 second, validating small text files, binary PNG images, PDF documents, 2 MB large binary archives, receiver rejection, offline receivers, and custom downloads directory.*

---

## 🔄 Module 3: Reliable File Transfer Management and Resume Support

### 1. Module 3 Objectives & Deliverables
Module 3 adds robust reliability, fault tolerance, and resumption capabilities to both file uploads and downloads. Network disconnections, client crashes, or intentional interrupts no longer force files to restart from byte 0.

* **Unique Transfer Identifiers:** Every transfer is assigned an immutable 12-hex Transfer ID (`uuid.uuid4().hex[:12]`).
* **Partial File Staging (`.part` extension):** All incomplete uploads staged on the server and incomplete downloads on the client are saved with a `.part` extension (e.g. `resume_test_2mb.dat.part`).
* **Metadata Persistence (`.meta.json`):** Tracks `transfer_id`, `filename`, `filesize`, `checksum`, `sender`, `receiver`, `bytes_stored`, `status`, and timestamps across restarts.
* **Verified Resume Offset Calculation:** On reconnect or retry, the receiver/server inspects the actual byte count stored on disk (`get_partial_transfer_offset()`), returns the verified offset, seeks the file pointer (`f.seek(offset)`), and streams only remaining bytes in append mode (`"ab"`).
* **Strict Permission & Identity Validation:**
  - Validates transfer ID exists.
  - Verifies file identity (`filename`) and exact expected `filesize`.
  - Enforces sender/receiver access control: unauthorized third-party clients attempting to resume another user's transfer receive `PERMISSION_DENIED`.
* **Zero Missing or Duplicated Bytes:** Chunk offsets ensure seamless continuation from exact byte boundaries.
* **Post-Transfer SHA-256 Verification:** Constant-time checksum calculation (`hmac.compare_digest`) on the assembled file after transfer completion.
* **Conditional Atomic File Renaming:** Incomplete `.part` files are renamed to their final filenames **strictly after** checksum verification succeeds. If a checksum fails, success is **never reported** and `.part` is preserved.
* **File Transfers Registry (`LIST_TRANSFERS`):** Clients can query available transfers, viewing `transfer_id`, `filename`, `filesize`, `sender`, `receiver`, `bytes_stored`, and current `status`.
* **Transfer Cancellation (`CANCEL_TRANSFER`):** Senders and receivers can cancel transfers at any time, cleaning up staging files and preventing unauthorized stream operations.

---

### 2. Resume Architecture Sequence Diagram

```text
SENDER (Alice)                   TCP SERVER (Relay)                 RECEIVER (Bob)
     │                                    │                                 │
     │ 1. INTERRUPTED UPLOAD              │                                 │
     │=== Streamed 1,048,576 bytes ======>│ (Connection Dropped / Reset)   │
     │                                    │ [Preserves .part & .meta.json]  │
     │                                    │                                 │
     │ 2. RESUME_PEER_UPLOAD              │                                 │
     │    (TID, filename, size, checksum) │                                 │
     ├───────────────────────────────────>│ Validate Permissions & Identity│
     │                                    │ Check disk: 1,048,576 bytes     │
     │<── RESUME_READY (offset=1048576) ──┤                                 │
     │                                    │                                 │
     │ 3. Alice seeks f.seek(1048576)     │ Server opens in "ab" append mode│
     │=== Streams remaining 1MB =========>│ SHA-256 Verified on server      │
     │<── UPLOAD_COMPLETE ────────────────┤                                 │
     │                                    │                                 │
     │                                    │ 4. RESUME_PEER_DOWNLOAD         │
     │                                    │    (TID, offset=1048576)        │
     │                                    │<────────────────────────────────┤
     │                                    ├──── RESUME_READY ──────────────>│
     │                                    │ Bob seeks .part in "ab" mode    │
     │                                    │=== Streams remaining 1MB ======>│
     │                                    │                                 │
     │                                    │ 5. Calculate Full File SHA-256  │
     │                                    │    Match confirmed!             │
     │                                    │    Rename .part -> final file   │
     │                                    │ 6. PEER_DOWNLOAD_COMPLETE       │
     │                                    │<────────────────────────────────┤
     │                                    │ [Clean up staging files]        │
     │                                    ├──── Finalized ACK ─────────────>│
```

---

### 3. Step-by-Step PowerShell Guide: Testing Resumable Transfers

#### Step 1: Start TCP Server
```powershell
python server/tcp_server.py
```

#### Step 2: Open Client A (Alice - Sender)
```powershell
python client/client.py
```
- Username: `Alice`

#### Step 3: Open Client B (Bob - Receiver)
```powershell
python client/client.py
```
- Username: `Bob`

#### Step 4: Initiate Transfer & Simulate Network Interruption
1. In **Alice's terminal**, choose option `[5]` to send a large file (e.g., `storage/sample_test_1mb.dat`) to `Bob`.
2. In **Bob's terminal**, choose option `[6]` and accept (`A`).
3. Press `Ctrl+C` or terminate the connection during transfer to simulate a real-world network failure.
4. Observe that `storage/transfers/*.part` and `storage/downloads/*.part` remain on disk with partial byte counts.

#### Step 5: Reconnect & Resume
1. In **Alice's terminal**, re-launch `python client/client.py` and register as `Alice`.
2. Choose option `[7] View Active & Interrupted Transfers Registry`.
   - Inspect the transfer ID, filename, total bytes, stored bytes, and `INTERRUPTED` status.
3. Choose option `[8] Resume Interrupted File Transfer`.
   - Enter the Transfer ID and select `[U] Resume Upload`.
   - Alice queries the server's partial offset, seeks to that exact byte offset, and sends only the remaining chunks!
4. In **Bob's terminal**, select option `[8]` and select `[D] Resume Download`.
   - Bob streams remaining bytes from the server staging relay.
   - Bob verifies the SHA-256 checksum across the entire reconstructed file.
   - Upon checksum match, Bob's client atomically renames the `.part` file to the original filename!

---

### 4. Running Automated Tests for Module 3
```powershell
python -m unittest tests/test_resume.py -v
```
*All 7 tests pass, verifying:*
1. Direct server upload resume from `.part` offset.
2. Direct client download resume from `.part` offset.
3. Peer upload resume from 1MB offset on server relay staging.
4. Peer download resume from 1MB offset on receiver downloads.
5. Permission validation rejecting unauthorized third-party attempts (`PERMISSION_DENIED`).
6. Checksum failure rejection preventing file renaming when corruption occurs.
7. Transfer listing (`LIST_TRANSFERS`) and authorized cancellation (`CANCEL_TRANSFER`).

---

## 📡 Module 4: UDP Communication & Online User Presence Engine

### 1. Module 4 Objectives & Deliverables
Module 4 adds a high-speed, connectionless UDP datagram subsystem for tracking online users, maintaining presence, and receiving real-time state changes without modifying or replacing the TCP server.

* **Dual-Protocol Coexistence:** 
  - **TCP Server** continues listening on port **5000** for reliable stream file transfers.
  - **UDP Server** listens on port **6000** (`socket.AF_INET`, `socket.SOCK_DGRAM`) for datagram presence and messaging.
* **Session & Identity Reuse:** Clients reuse their authenticated usernames and unique 8-hex session IDs obtained during TCP registration.
* **UDP Datagram Registration (`JOIN`):** When a client joins, the server records `username`, `session_id`, `ip`, `port`, `endpoint` (`IP:Port`), `last_seen` timestamp, and marks status `ONLINE`.
* **5-Second Heartbeat Engine (`HEARTBEAT`):** Active clients run a background daemon thread sending lightweight UDP datagrams every 5 seconds.
* **15-Second Inactivity Timeout:** If no valid heartbeat arrives for 15 seconds, the server marks the client `OFFLINE` and cleans up stale endpoint bindings.
* **Stale Endpoint Cleanup & Presence Change Notifications (`PRESENCE_CHANGE`):** When clients join, leave, or time out, the server clears stale IP/port allocations and broadcasts `PRESENCE_CHANGE` datagrams (`USER_JOINED`, `USER_LEFT`, `TIMEOUT`) to remaining online clients.
* **Online Presence Panel (CLI Option `[10]` & Web UI):** Displays a live table of online users, active session tokens, UDP socket endpoints, and last heartbeat timestamps.
* **Robust Resilience & Fault Tolerance:**
  - **Repeated `JOIN` Messages:** Handled idempotently by refreshing timestamps and endpoint addresses without creating duplicate registry records.
  - **Malformed Datagrams:** Binary garbage, non-JSON bytes, and missing fields are rejected without crashing the server.
  - **Session Isolation:** Rejects unauthorized attempts to overwrite or spoof an active client's session (`SESSION_CONFLICT`).

---

### 2. UDP Presence Protocol Flow

```text
CLIENT (Alice)                    UDP SERVER (Port 6000)             CLIENT (Bob)
     │                                    │                                 │
     │ 1. JOIN (username, session_id)     │                                 │
     ├───────────────────────────────────>│ [Records Alice: 127.0.0.1:52001]│
     │<── JOIN_ACK (status: SUCCESS) ─────┤                                 │
     │                                    │ 2. PRESENCE_CHANGE (Alice joined│
     │                                    ├────────────────────────────────>│
     │                                    │                                 │
     │ 3. HEARTBEAT (Every 5 seconds)     │                                 │
     ├───────────────────────────────────>│ [Updates last_seen timestamp]   │
     │<── HEARTBEAT_ACK ──────────────────┤                                 │
     │                                    │                                 │
     │ 4. GET_USERS                       │                                 │
     ├───────────────────────────────────>│                                 │
     │<── USERS_LIST (Online peers) ──────┤                                 │
     │                                    │                                 │
     │ 5. Client Abrupt Exit (No packets) │                                 │
     │    ... 15.0 seconds elapse ...     │                                 │
     │                                    │ [Timeout detected!]             │
     │                                    │ [Alice marked OFFLINE]          │
     │                                    │ [Stale endpoint cleared]        │
     │                                    │ 6. PRESENCE_CHANGE (TIMEOUT)    │
     │                                    ├────────────────────────────────>│
```

---

### 3. Step-by-Step PowerShell Guide: Testing 3 Clients & Heartbeat Timeout

Open **four** separate Windows PowerShell windows from `c:\Users\KEERTHIGA M\Desktop\CN-project`:

#### Terminal 1: Start Dual TCP & UDP Server
```powershell
python server/server.py
```
*Output confirms:*
```text
TCP File Server listening on 127.0.0.1:5000
UDP Chat & Presence Server listening on 127.0.0.1:6000
```

#### Terminal 2: Start Client 1 (Alice)
```powershell
python client/client.py
```
- Username: `Alice`
- Observe registration on TCP port 5000 and UDP port 6000.

#### Terminal 3: Start Client 2 (Bob)
```powershell
python client/client.py
```
- Username: `Bob`
- Terminal 2 (Alice) immediately receives: `[UDP Presence Notification: User 'Bob' is ONLINE [USER_JOINED]]`.

#### Terminal 4: Start Client 3 (Charlie)
```powershell
python client/client.py
```
- Username: `Charlie`
- Terminals 2 and 3 receive notification: `[UDP Presence Notification: User 'Charlie' is ONLINE [USER_JOINED]]`.

#### Verify 3 Clients in Presence Panel:
In **Terminal 2 (Alice)**, choose option `[10] View Real-Time UDP Online Presence & Heartbeat Monitor`.
- Observe all 3 users (`Alice`, `Bob`, `Charlie`) listed with status `ONLINE`, their respective UDP endpoints, and active heartbeat timestamps!

#### Test Inactivity Timeout:
1. In **Terminal 4 (Charlie)**, press `Ctrl+C` or close the window abruptly (simulating network disconnection / crash without sending `LEAVE`).
2. Wait 15 seconds.
3. Observe in **Terminal 1 (Server)**:
   ```text
   [WARN] UDP User 'Charlie' marked OFFLINE (Heartbeat timeout)
   ```
4. Observe in **Terminals 2 and 3 (Alice & Bob)**:
   ```text
   [UDP Presence Notification: User 'Charlie' is OFFLINE [TIMEOUT]]
   ```
5. In **Terminal 2 (Alice)**, choose option `[10]` again.
   - `Charlie` is now marked `OFFLINE` and stale endpoints are cleared (`N/A`)!

---

### 4. Running Automated Tests for Module 4
```powershell
python -m unittest tests/test_udp.py -v
```
*All 8 tests pass, verifying 3-client joins, heartbeat updates, 15-second offline timeouts, presence notifications, repeated joins, malformed datagrams resilience, session isolation, and TCP/UDP dual operation.*

---

## 🏗️ System Architecture

```text
                               HYBRID TRANSFER APPLICATION
                                            │
                       ┌────────────────────┴────────────────────┐
                       │                                         │
              TCP SOCKET ENGINE                         UDP SOCKET ENGINE
               (Port 5000 / TCP)                         (Port 6000 / UDP)
                       │                                         │
        ┌──────────────┴──────────────┐           ┌──────────────┴──────────────┐
        │                             │           │                             │
   Upload Engine             Download Engine   UDP Live Chat             Presence Tracker
(4KB Chunk Stream)         (Resume .part File)  (ACK / Retransmit)        (5s Heartbeat Daemon)
        │                             │           │                             │
   SHA-256 Hash               HMAC Digest      Sequence Tracking            Loss Simulator
 Verification            Verification      Duplicate Rejection           (0% - 50% Drop)
```

### Protocol Comparison Summary

| Metric / Feature | TCP File Transfer | UDP Live Chat & Presence |
| :--- | :--- | :--- |
| **Socket Type** | `socket.AF_INET`, `socket.SOCK_STREAM` | `socket.AF_INET`, `socket.SOCK_DGRAM` |
| **Port** | `5000` | `6000` |
| **Connection Protocol** | Connection-Oriented (3-Way Handshake) | Connectionless Datagram |
| **Framing Format** | 4-Byte Network Length Header + JSON | Direct JSON Bytes Datagram |
| **Payload Handling** | 4 KB Streaming Chunks | Up to 1024-Byte Datagram |
| **Reliability** | Transport Layer OS Retransmission | Application-Layer ACK & 1s Retransmissions |
| **Integrity Check** | Constant-Time SHA-256 (`hmac.compare_digest`) | Custom Sequence Numbering |
| **Primary Use Case** | Bulk Data, Files, Resumes | Real-Time Messaging, Heartbeats |

---

## 💻 Tech Stack & Architecture

- **Backend Network Sockets:** Python 3.12 `socket`, `struct`, `threading`, `hashlib`, `hmac`, `json`.
- **Local Web Product Engine:** Flask Local Web Server (`http://127.0.0.1:8000`) bridging Web UI to Python Sockets.
- **Frontend Dashboard:** Dark Navy / Electric Blue HTML5, CSS3 Custom Tokens, Vanilla JavaScript ES6 (No React, No WebSocket, No Socket.IO).

---

## 📡 Wireshark Packet Inspection Guide

To analyze real socket traffic using **Wireshark**:

1. Open Wireshark and select your capture interface (`Adapter for loopback traffic` for `127.0.0.1` or `Wi-Fi / Ethernet` for LAN).
2. Enter the following **Wireshark Display Filter**:
   ```text
   tcp.port == 5000 || udp.port == 6000
   ```
3. **What to Observe:**
   - **TCP 3-Way Handshake:** Look for `[SYN]`, `[SYN-ACK]`, `[ACK]` flags on Port 5000 during connection initiation.
   - **TCP Framing:** Inspect TCP payload segments containing 4-byte big-endian length prefix headers.
   - **UDP Datagrams:** Inspect unsegmented UDP packets on Port 6000 containing `{"type": "JOIN"}`, `{"type": "MSG"}`, and `{"type": "ACK"}` payloads.
   - **UDP Retransmission:** Set Simulated Packet Loss to 20% in the Network Monitor tab, send a chat message, and watch Wireshark capture identical sequence numbers transmitted 1.0s apart!

---

## 🎓 30+ Computer Networks Viva Questions & Answers

### Q1: What is the primary difference between TCP and UDP sockets?
**Answer:** TCP (`SOCK_STREAM`) is a reliable, connection-oriented stream protocol offering ordered, error-checked delivery via OS-level ACKs and 3-way handshakes. UDP (`SOCK_DGRAM`) is a connectionless, low-overhead datagram protocol without native reliability or ordering guarantees.

### Q2: Why did you use TCP for file transfer and UDP for chat in this project?
**Answer:** File transfers require 100% data integrity without missing bytes, making TCP's reliable streaming and SHA-256 checksum ideal. Chat and presence prioritize low latency and real-time delivery; using UDP allows fast transmission while implementing custom lightweight application-layer ACKs for reliability.

### Q3: What is Socket Programming?
**Answer:** Socket programming is a way of connecting two nodes on a network to communicate with each other. One socket (node) listens on a specific port at an IP address, while another socket reaches out to form a connection or send datagrams.

### Q4: Explain the TCP 3-Way Handshake.
**Answer:** Before TCP sends data:
1. Client sends `SYN` (Synchronize sequence number).
2. Server responds with `SYN-ACK`.
3. Client sends `ACK` (Acknowledge).
Connection is now established.

### Q5: What is the purpose of `struct.pack('>I', payload_len)` in your TCP framing?
**Answer:** `struct.pack('>I', payload_len)` packs a 32-bit unsigned integer into 4 bytes using Big-Endian (Network Byte Order `>`). This guarantees both client and server agree on message boundary lengths regardless of CPU architecture (Little-Endian vs Big-Endian).

### Q6: How do you prevent framing errors or partial reads on TCP streams?
**Answer:** Since TCP is a continuous byte stream without built-in message boundaries, we created `recv_exact(sock, num_bytes)` which loops `sock.recv()` until exactly `num_bytes` are collected.

### Q7: How does file resume work in your project?
**Answer:** The client checks the size of the existing partial `.part` file in `storage/downloads/`, sends a `RESUME_DOWNLOAD` request with the `offset` byte count, and the server seeks to `f.seek(offset)` before streaming remaining 4KB chunks.

### Q8: Why do you calculate SHA-256 checksums?
**Answer:** To guarantee end-to-end data integrity across network transfers. After streaming, the client computes the SHA-256 hash of the received file and compares it using `hmac.compare_digest` against the server's expected hash.

### Q9: Why use `hmac.compare_digest` instead of `==` for hash comparison?
**Answer:** `hmac.compare_digest` performs constant-time comparison, preventing timing side-channel attacks.

### Q10: How does your UDP Chat implement reliability over connectionless sockets?
**Answer:** We implemented application-layer ACKs and sequence numbers. Every message is assigned a sequence number (`seq`). When received, the server replies with an `ACK` packet (`{"type": "ACK", "sequence": seq}`). If the client does not receive an ACK within `1.0s`, it retransmits up to 3 times.

### Q11: How do you prevent duplicate UDP chat messages from being displayed?
**Answer:** The receiver maintains a thread-safe `processed_sequences` set. If an incoming datagram has a sequence number already in `processed_sequences`, it is logged as a duplicate and ignored.

### Q12: How does the UDP Online Presence system work?
**Answer:** Clients run a background `UDPHeartbeatThread` sending a `HEARTBEAT` datagram every 5 seconds. The server's `UDPPresenceMonitor` thread checks timestamps every 5 seconds and marks any client inactive if no heartbeat is received within 15 seconds.

### Q13: What is the purpose of `socket.SO_REUSEADDR`?
**Answer:** It allows a socket to forcibly bind to a port that is in `TIME_WAIT` state, enabling immediate server restarts without getting `Address already in use` errors.

### Q14: What is the default buffer chunk size used for TCP file streaming and why?
**Answer:** `4096` bytes (4 KB). This aligns with standard OS memory page sizes, ensuring high throughput without overloading system RAM.

### Q15: What is the maximum UDP payload size in your configuration?
**Answer:** `1024` bytes. Keeping UDP payloads under the Internet Maximum Transmission Unit (MTU ~1500 bytes) prevents IP fragmentation.

### Q16: What is IP Fragmentation?
**Answer:** When an IP datagram exceeds the Maximum Transmission Unit (MTU) of a network link, router hardware breaks it into smaller fragments, increasing drop risk.

### Q17: What is RTT (Round Trip Time)?
**Answer:** The total time taken in milliseconds for a data packet to travel from sender to receiver and for the acknowledgment to travel back.

### Q18: What is Packet Loss?
**Answer:** When one or more transmitted data packets fail to arrive at their destination due to network congestion, hardware errors, or signal degradation.

### Q19: How does your Packet Loss Simulator work?
**Answer:** When a user sets a loss rate (e.g. 20%), the server randomly drops incoming UDP packets using `if random.random() < loss_rate: continue`, forcing the client to demonstrate application-layer retransmission.

### Q20: What is a Socket Address?
**Answer:** The combination of an IP address and a Port number (e.g., `127.0.0.1:5000`).

### Q21: What is localhost / `127.0.0.1`?
**Answer:** The IPv4 loopback network address, allowing client and server processes on the same machine to communicate without external network interfaces.

### Q22: How can this system run across two machines on a LAN?
**Answer:** By substituting `127.0.0.1` with the server machine's local LAN IP address (e.g. `192.168.1.15`).

### Q23: Why use multithreading in socket servers?
**Answer:** A single-threaded TCP server would block on `accept()` or streaming a large file, preventing other clients from connecting. Multithreading (`threading.Thread`) allows dedicated execution per client.

### Q24: What is thread synchronization and why is `threading.Lock` used?
**Answer:** Prevents race conditions when multiple client threads access shared data structures (such as `client_registry` or `transfer_history`).

### Q25: Difference between `send()` and `sendall()` in Python sockets?
**Answer:** `send()` may transmit only part of the bytes buffer and returns the count sent. `sendall()` continues sending bytes from the buffer until all data is sent or an error occurs.

### Q26: Difference between `recv()` and `recvfrom()`?
**Answer:** `recv()` is used for connected TCP sockets and returns data bytes. `recvfrom()` is used for UDP datagram sockets and returns a tuple `(data_bytes, sender_address)`.

### Q27: What is a blocking vs non-blocking socket?
**Answer:** A blocking socket waits indefinitely for an operation (like `recv`) to complete. A non-blocking socket returns immediately or raises `socket.timeout`.

### Q28: What is a daemon thread in Python?
**Answer:** A background thread that automatically terminates when the main program exits (e.g. `UDPReceiverThread`, `UDPHeartbeatThread`).

### Q29: What is Big-Endian vs Little-Endian?
**Answer:** Big-Endian stores the most significant byte at the lowest memory address (Standard Network Byte Order). Little-Endian stores the least significant byte first (x86/x64 CPUs).

### Q30: How does Flask integrate with Python sockets in this project?
**Answer:** Flask serves as a lightweight local Web Engine (`http://127.0.0.1:8000`) translating HTTP JSON UI actions into calls to `ClientController`, which executes real TCP and UDP socket communication.

---

## 🧪 Automated Unit Test Suite (45 Passed)

To run the complete automated test suite:
```bash
python -m unittest discover tests
```

| Test Module | Test Coverage Description | Result |
| :--- | :--- | :--- |
| [`test_tcp.py`](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/tests/test_tcp.py) | TCP Server connection, HELLO exchange & multithreaded concurrency | **PASSED** |
| [`test_protocol.py`](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/tests/test_protocol.py) | 4-byte Big-Endian framing, JSON encoding & length verification | **PASSED** |
| [`test_file_transfer.py`](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/tests/test_file_transfer.py) | 4KB chunk streaming upload, download & SHA-256 verification | **PASSED** |
| [`test_resume.py`](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/tests/test_resume.py) | Interrupted file upload/download RESUME from `.part` offsets | **PASSED** |
| [`test_udp.py`](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/tests/test_udp.py) | UDP JOIN, chat broadcast & 15-second heartbeat presence monitor | **PASSED** |
| [`test_chat.py`](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/tests/test_chat.py) | Multi-user chat history & presence registry tracking | **PASSED** |
| [`test_udp_reliability.py`](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/tests/test_udp_reliability.py) | Sequence tracking, 1s ACK timeout retransmissions & duplicate rejection | **PASSED** |
| [`test_stats.py`](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/tests/test_stats.py) | Network statistics collector, throughput speeds & packet metrics | **PASSED** |
| [`test_simulation.py`](file:///c:/Users/KEERTHIGA%20M/Desktop/CN-project/tests/test_simulation.py) | Simulated UDP packet loss rates (0% to 50%) & drop checking | **PASSED** |

---

## 🚀 Quick Start & How to Run

### Method 1: Web Product UI (Recommended)
1. Start the Server in Terminal 1:
   ```bash
   python run_project.py server
   ```
2. Start the Product Web Engine in Terminal 2:
   ```bash
   python run_project.py
   ```
3. Open your browser and navigate to:
   ```text
   http://127.0.0.1:8000
   ```

### Method 2: Terminal Interactive CLI
```bash
python client/client.py
```
