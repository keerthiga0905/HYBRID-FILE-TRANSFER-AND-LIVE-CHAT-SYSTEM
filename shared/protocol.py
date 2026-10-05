"""
Shared Protocol Module - Message framing and JSON protocol definitions for TCP/UDP socket communication.
Uses 4-byte network byte-order integer length prefix + JSON bytes payload.
Format: [4-byte Big-Endian Length Header][JSON Payload Bytes]
"""

import json
import socket
import struct
from typing import Any, Dict, Optional

# Security limit for maximum control message size (16 MB) to prevent OOM DOS attacks
MAX_CONTROL_MSG_SIZE = 16 * 1024 * 1024  # 16 MB


def recv_exact(sock: socket.socket, num_bytes: int) -> Optional[bytes]:
    """
    Helper function to reliably read exactly `num_bytes` from a TCP stream socket.
    Handles partial recv() calls across TCP buffer segments.
    Returns bytes or None if the socket was closed before completing read.
    """
    buf = bytearray()
    while len(buf) < num_bytes:
        try:
            chunk = sock.recv(num_bytes - len(buf))
            if not chunk:
                # Connection closed by remote endpoint
                return None
            buf.extend(chunk)
        except (socket.error, ConnectionError):
            return None
    return bytes(buf)


def send_message(sock: socket.socket, data: Dict[str, Any]) -> None:
    """
    Encodes a Python dictionary to JSON, prepends a 4-byte network-order length header,
    and sends the complete framed packet over the TCP socket.
    """
    json_bytes = json.dumps(data).encode("utf-8")
    payload_len = len(json_bytes)
    header = struct.pack(">I", payload_len)
    sock.sendall(header + json_bytes)


def receive_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """
    Reads a 4-byte length prefix from TCP socket, then reads exactly payload_len bytes.
    Decodes the JSON data payload into a Python dictionary.
    Returns None if socket is disconnected or message is invalid.
    """
    header = recv_exact(sock, 4)
    if not header:
        return None

    # Unpack 4-byte big-endian unsigned int
    (payload_len,) = struct.unpack(">I", header)

    if payload_len > MAX_CONTROL_MSG_SIZE:
        raise ValueError(f"Control message length ({payload_len} bytes) exceeds limit ({MAX_CONTROL_MSG_SIZE} bytes)")

    payload_bytes = recv_exact(sock, payload_len)
    if payload_bytes is None:
        return None

    try:
        decoded_str = payload_bytes.decode("utf-8")
        return json.loads(decoded_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON payload: {e}")
