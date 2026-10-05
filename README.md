# HYBRID FILE TRANSFER AND LIVE CHAT SYSTEM
## Using TCP and UDP Socket Programming in Python

An academic Computer Networks project designed to demonstrate practically and visually the fundamental differences between **TCP** (Transmission Control Protocol) and **UDP** (User Datagram Protocol).

---

## 🏗️ System Architecture

```
                ┌─────────────────────────────┐
                │           SERVER            │
                │                             │
                │  TCP File Transfer Server   │
                │       Port 5000/TCP         │
                │                             │
                │  UDP Chat Server            │
                │       Port 6000/UDP         │
                │                             │
                │  Client Registry             │
                │  File Storage                │
                │  Transfer Logs               │
                └──────────────┬──────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
      TCP File Transfer                  UDP Chat/Presence
      Reliable / Ordered                Fast / Connectionless
              │                                 │
      ┌───────┴────────┐                ┌───────┴────────┐
      │                │                │                │
   Client A         Client B         Client A         Client B
   TCP socket       TCP socket       UDP socket       UDP socket
```

---

## 📁 Project Folder Structure

```
hybrid-network-system/
│
├── server/
│   ├── server.py             # Server launcher & thread controller
│   ├── tcp_server.py         # Multithreaded TCP server implementation
│   ├── udp_server.py         # UDP Server (Phase 6)
│   ├── client_registry.py   # Client status state (Phase 6)
│   ├── file_manager.py       # File I/O operations (Phase 2)
│   ├── protocol.py           # Protocol handling
│   ├── logger.py             # System activity logger
│   └── config.py             # Server configurations
│
├── client/
│   ├── client.py             # Terminal user interface
│   ├── tcp_client.py         # TCP socket client handler
│   ├── udp_client.py         # UDP socket client handler (Phase 6)
│   ├── protocol.py           # Client protocol encoder/decoder
│   ├── file_manager.py       # Client-side file transfer
│   └── config.py             # Client configuration
│
├── shared/
│   ├── protocol.py           # Application protocol framing
│   ├── checksum.py           # SHA-256 integrity verifier
│   └── utils.py              # Formatting & logging helpers
│
├── storage/
│   ├── uploads/              # Server upload storage
│   └── downloads/            # Client download storage
│
├── logs/                     # System execution logs
│
├── tests/
│   ├── test_tcp.py           # TCP socket connection tests
│   ├── test_udp.py           # UDP socket tests
│   └── test_checksum.py      # Checksum verification tests
│
├── requirements.txt          # Dependencies list
├── README.md                 # System documentation & Viva preparation
└── run_project.py            # Easy project launcher
```

---

## 🚀 Running Phase 1 (TCP Connection Test)

### 1. Requirements & Setup
No external third-party packages are required for Phase 1 as it uses Python standard library `socket` and `threading`.

### 2. Run Server
In Terminal 1:
```bash
python server/server.py
```
Expected Output:
```text
========================================
HYBRID NETWORK SERVER
=====================

TCP File Server : 5000
UDP Chat Server  : 6000 (Phase 6 Ready)
Server Host      : 127.0.0.1
Server Status    : RUNNING
==========================

✓ [SUCCESS HH:MM:SS] TCP File Server listening on 127.0.0.1:5000
[SERVER] Press Ctrl+C to stop the server.
```

### 3. Run Client
In Terminal 2:
```bash
python client/client.py
```
Select option `1` to test TCP connection to server.

Expected Output:
```text
✓ [SUCCESS HH:MM:SS] Connected to TCP Server at 127.0.0.1:5000
[TCP HH:MM:SS] Sent TCP PING header to server...
✓ [SUCCESS HH:MM:SS] Received from Server: PONG Server Ready Clients Connected: 1
```

---

## 🧪 Running Unit Tests
To verify Phase 1 TCP Socket connection programmatically:
```bash
python -m unittest discover tests
```

---

## 🎓 Computer Networks Concepts Demonstrated (Phase 1)

| Concept | Explanation |
| :--- | :--- |
| **Client-Server Architecture** | Centralized server listening on specific IP/Port; clients initiate connections. |
| **TCP Socket (`SOCK_STREAM`)** | Connection-oriented, reliable IPv4 socket created via `socket.socket(socket.AF_INET, socket.SOCK_STREAM)`. |
| **Port Numbers** | Port `5000` allocated for TCP file server; Port `6000` for UDP chat. |
| **Multithreading** | Server uses `threading.Thread` to handle each incoming client concurrently without blocking. |
| **Message Framing** | Delimited protocol structure (`COMMAND|ARGS\n`) prevents TCP stream fragmentation issues. |
