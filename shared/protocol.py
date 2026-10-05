"""
Application-level framing protocol for TCP and UDP messages.
Handles string message encoding/decoding and line-delimited message framing over stream sockets.
"""

import socket
from shared.config import HEADER_DELIMITER, MSG_END_MARKER


class ProtocolMessage:
    """
    Represents an application-layer control message.
    Format: COMMAND|ARG1|ARG2...
    """

    def __init__(self, command: str, *args: str):
        self.command = command.upper().strip()
        self.args = [str(a).strip() for a in args]

    def encode(self) -> bytes:
        """Encodes message to UTF-8 bytes with end marker."""
        parts = [self.command] + self.args
        raw_str = HEADER_DELIMITER.join(parts) + MSG_END_MARKER
        return raw_str.encode("utf-8")

    @classmethod
    def decode(cls, raw_data: str) -> "ProtocolMessage":
        """Decodes raw string message into a ProtocolMessage instance."""
        clean_str = raw_data.rstrip("\r\n")
        if not clean_str:
            return cls("INVALID")
        parts = clean_str.split(HEADER_DELIMITER)
        return cls(parts[0], *parts[1:])

    def __repr__(self) -> str:
        return f"<ProtocolMessage cmd={self.command} args={self.args}>"


def send_framed_msg(sock: socket.socket, msg: ProtocolMessage) -> None:
    """
    Sends a complete framed control message over a TCP stream socket.
    """
    sock.sendall(msg.encode())


def receive_framed_msg(sock: socket.socket, buffer: str = "") -> tuple[ProtocolMessage | None, str]:
    """
    Reads from TCP socket until a full line delimiter '\\n' is found.
    Returns (ProtocolMessage, remaining_buffer).
    Handles socket recv streaming fragmentation.
    """
    current_buf = buffer
    while MSG_END_MARKER not in current_buf:
        try:
            chunk = sock.recv(1024)
            if not chunk:
                # Socket connection closed by remote peer
                if current_buf.strip():
                    return ProtocolMessage.decode(current_buf), ""
                return None, ""
            current_buf += chunk.decode("utf-8", errors="replace")
        except socket.error as e:
            raise e

    line, remaining = current_buf.split(MSG_END_MARKER, 1)
    return ProtocolMessage.decode(line), remaining
