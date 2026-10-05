# HYBRID FILE TRANSFER AND LIVE CHAT SYSTEM
## Using TCP and UDP Socket Programming in Python

An academic Computer Networks project designed to demonstrate practically and visually the fundamental differences between **TCP** (Transmission Control Protocol) and **UDP** (User Datagram Protocol).

---

## 🏗️ System Architecture

```
                    HYBRID NETWORK SYSTEM
                            │
              ┌─────────────┴─────────────┐
              │                           │
             TCP                         UDP
              │                           │
        Port 5000                    Port 6000
              │                           │
       File Transfer              Chat + Presence
              │                           │
       ┌──────┴──────┐             ┌──────┴──────┐
       │             │             │             │
     Upload       Download       Chat         Presence
       │             │             │             │
       └──────┬──────┘             └──────┬──────┘
              │                           │
          SHA-256                 ACK / Retry / Sequence
```

---

## 📁 Project Folder Structure

```
hybrid-network-system/
│
├── server/
│   ├── __init__.py
│   ├── server.py             # Main server launcher & thread controller
│   ├── tcp_server.py         # Multithreaded TCP server implementation
│   ├── udp_server.py         # UDP Server (Phase 6)
│   ├── client_registry.py   # Client status state (Phase 6)
│   ├── file_manager.py       # File I/O operations (Phase 2)
│   ├── protocol.py           # Server protocol wrapper
│   ├── logger.py             # System activity logger
│   └── config.py             # Server configurations
│
├── client/
│   ├── __init__.py
│   ├── client.py             # Terminal user interface
│   ├── tcp_client.py         # TCP socket client handler
│   ├── udp_client.py         # UDP socket client handler (Phase 6)
│   ├── protocol.py           # Client protocol wrapper
│   ├── file_manager.py       # Client file operations
│   └── config.py             # Client configuration
│
├── shared/
│   ├── __init__.py
│   ├── protocol.py           # 4-byte network-order length + JSON message framing
│   ├── checksum.py           # Streaming SHA-256 calculator & verifier
│   └── utils.py              # Formatting & console logging helpers
│
├── storage/
│   ├── uploads/              # Server upload storage directory
│   └── downloads/            # Client download storage directory
│
├── logs/                     # System execution logs (server.log)
│
├── tests/
│   ├── __init__.py
│   ├── test_tcp.py           # TCP socket connection and concurrency tests
│   ├── test_udp.py           # UDP socket tests (Phase 6)
│   ├── test_checksum.py      # Checksum verification tests
│   └── test_protocol.py      # Length prefix framing unit tests
│
├── requirements.txt          # System requirements
├── README.md                 # Documentation and viva preparation
├── run_project.py            # Quick launcher script
└── .gitignore                # Git exclusion rules
```

---

## 🚀 Running Phase 1 (Basic TCP Connection)

### 1. Requirements & Setup
Uses standard Python 3.12+ `socket`, `struct`, `json`, and `threading` libraries. No third-party packages required.

### 2. Run Server
In Terminal 1:
```bash
python server/server.py
```

Expected Output:
```text
========================================
HYBRID NETWORK SERVER
========================================

TCP File Server : 5000
UDP Chat Server : NOT STARTED
Server Status   : RUNNING

Waiting for TCP clients...
[OK 22:33:03] TCP File Server listening on 127.0.0.1:5000
```

### 3. Run Client
In Terminal 2:
```bash
python client/client.py
```

Expected Output:
```text
========================================
HYBRID NETWORK CLIENT
========================================
Connecting to 127.0.0.1:5000...

[OK 22:33:03] TCP CONNECTION ESTABLISHED
[Server 22:33:03] Server response:
[OK 22:33:03] HELLO received
[OK 22:33:03] Connection is working
```

---

## 🧪 Running Unit Tests
To run all automated socket & protocol tests:
```bash
python -m unittest discover tests
```

---

## 🎓 Computer Networks Concepts Demonstrated (Phase 1)

| Concept | Explanation |
| :--- | :--- |
| **Client-Server Architecture** | Centralized server listening on `127.0.0.1:5000`; clients initiate connection via socket. |
| **TCP Stream Socket (`SOCK_STREAM`)** | Connection-oriented IPv4 socket created using `socket.socket(socket.AF_INET, socket.SOCK_STREAM)`. |
| **TCP 3-Way Handshake** | `connect()` triggers initial `SYN`, `SYN-ACK`, `ACK` exchange with server. |
| **Multithreading (`threading.Thread`)** | Server allocates a dedicated daemon thread per connected client socket. |
| **Message Framing (`struct.pack(">I", length)`)** | 4-byte network-byte-order integer length prefix prepended to JSON payload to solve stream fragmentation. |
| **Resilience & Error Handling** | Malformed payloads are intercepted at protocol parser level without crashing the server. |
