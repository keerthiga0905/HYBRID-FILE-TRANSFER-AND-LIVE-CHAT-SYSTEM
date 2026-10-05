"""
Server Protocol Interface - Imports shared protocol definitions to ensure protocol consistency across Client and Server.
"""

from shared.protocol import send_message, receive_message, recv_exact, MAX_CONTROL_MSG_SIZE

__all__ = ["send_message", "receive_message", "recv_exact", "MAX_CONTROL_MSG_SIZE"]
