# HYBRID TRANSFER: Fast File Transfer & Real-Time Communication System
> **An Academic & Production-Grade Computer Networks System using Real Python TCP & UDP Socket Programming**

---

## 📌 Executive Summary

**HYBRID TRANSFER** ("Fast File Transfer. Real-Time Communication. One Network.") is a dual-protocol networking application engineered in Python 3.12+ to demonstrate why **TCP (Transmission Control Protocol)** and **UDP (User Datagram Protocol)** are chosen for distinct network communication tasks:

- **TCP (Port 5000):** Reliable, connection-oriented byte stream sockets (`SOCK_STREAM`) for chunked file uploads, downloads, interrupted transfer RESUME capability, and SHA-256 checksum verification.
- **UDP (Port 6000):** Low-latency, connectionless datagram sockets (`SOCK_DGRAM`) with custom application-layer reliability (Sequence Numbers, 1s ACK Timeout Retransmissions, Duplicate Detection) for live multi-user chat, heartbeat presence tracking, and simulated packet loss analysis.

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

## 🧪 Automated Unit Test Suite (24 Passed)

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
