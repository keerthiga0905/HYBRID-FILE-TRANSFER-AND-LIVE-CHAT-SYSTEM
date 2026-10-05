"""
TCP Server Module - Handles reliable connection-oriented communication.
Used for TCP File Transfer. Multithreaded client handler.
"""

import socket
import threading
from shared.config import DEFAULT_HOST, TCP_PORT
from shared.protocol import receive_framed_msg, send_framed_msg, ProtocolMessage
from shared.utils import print_info, print_success, print_error
from server.logger import log_event


class TCPServer:
    """
    Multithreaded TCP Server demonstrating socket creation, binding, listening,
    and thread allocation per client connection.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = TCP_PORT):
        self.host = host
        self.port = port
        self.server_socket: socket.socket | None = None
        self.is_running = False
        self.active_clients = set()
        self._lock = threading.Lock()

    def start(self) -> None:
        """
        Initializes TCP socket, binds to address, listens, and runs accept loop.
        """
        # Create TCP IPv4 stream socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow reuse of local socket address (solves 'Address already in use' error on restart)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.is_running = True
            log_event(f"TCP File Server started on {self.host}:{self.port}")
            print_success(f"TCP File Server listening on {self.host}:{self.port}")

            # Accept connection loop running in dedicated thread or main thread
            accept_thread = threading.Thread(target=self._accept_loop, daemon=True, name="TCPAcceptLoop")
            accept_thread.start()

        except Exception as e:
            print_error(f"Failed to start TCP Server: {e}")
            log_event(f"TCP Server startup error: {e}", "error")
            raise e

    def _accept_loop(self) -> None:
        """Loop that continuously accepts new client TCP connections."""
        while self.is_running:
            try:
                client_sock, client_addr = self.server_socket.accept()
                with self._lock:
                    self.active_clients.add(client_addr)

                print_info(f"New TCP client connected from {client_addr[0]}:{client_addr[1]}", tag="TCP")
                log_event(f"TCP Client connected: {client_addr}")

                # Spawn a new thread for each client connection
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    daemon=True,
                    name=f"TCPClientHandler-{client_addr[1]}"
                )
                client_thread.start()

            except socket.error:
                if not self.is_running:
                    break  # Server stopped intentionally

    def _handle_client(self, client_sock: socket.socket, client_addr: tuple[str, int]) -> None:
        """
        Handles communication lifecycle for a single TCP client.
        Executed inside a separate thread per client.
        """
        buffer = ""
        try:
            while self.is_running:
                msg, buffer = receive_framed_msg(client_sock, buffer)
                if msg is None:
                    # Connection closed by client
                    break

                # Phase 1 Command Handling: PING / QUIT
                if msg.command == "PING":
                    response = ProtocolMessage("PONG", "Server Ready", f"Clients Connected: {len(self.active_clients)}")
                    send_framed_msg(client_sock, response)
                    log_event(f"Handled PING from {client_addr}")
                elif msg.command == "QUIT":
                    response = ProtocolMessage("GOODBYE", "Connection closing")
                    send_framed_msg(client_sock, response)
                    break
                else:
                    response = ProtocolMessage("ACK", f"Received command: {msg.command}")
                    send_framed_msg(client_sock, response)

        except Exception as e:
            log_event(f"Error handling TCP client {client_addr}: {e}", "error")
        finally:
            client_sock.close()
            with self._lock:
                self.active_clients.discard(client_addr)
            print_info(f"TCP client disconnected from {client_addr[0]}:{client_addr[1]}", tag="TCP")
            log_event(f"TCP Client disconnected: {client_addr}")

    def stop(self) -> None:
        """Stops the TCP server and closes server socket."""
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        print_info("TCP File Server stopped", tag="TCP")
        log_event("TCP Server stopped")
