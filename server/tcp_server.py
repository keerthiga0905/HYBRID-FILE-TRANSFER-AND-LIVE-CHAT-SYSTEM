"""
TCP Server Module - Handles reliable connection-oriented communication.
Multithreaded client handler using framed JSON messages over TCP stream sockets.
"""

import socket
import threading
from shared.config import DEFAULT_HOST, TCP_PORT
from shared.protocol import receive_message, send_message
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
        self.active_clients = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        """
        Initializes TCP socket, binds to address, listens, and runs accept loop.
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.is_running = True
            log_event(f"TCP File Server listening on {self.host}:{self.port}")
            print_success(f"TCP File Server listening on {self.host}:{self.port}")

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
                addr_str = f"{client_addr[0]}:{client_addr[1]}"
                with self._lock:
                    self.active_clients[addr_str] = client_sock

                print_info(f"Client connected: {addr_str}", tag="TCP")
                log_event(f"TCP Client connected: {addr_str}")

                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    daemon=True,
                    name=f"TCPClientHandler-{client_addr[1]}"
                )
                client_thread.start()

            except socket.error:
                if not self.is_running:
                    break

    def _handle_client(self, client_sock: socket.socket, client_addr: tuple[str, int]) -> None:
        """
        Handles communication lifecycle for a single TCP client.
        Executed inside a separate thread per client.
        """
        addr_str = f"{client_addr[0]}:{client_addr[1]}"
        try:
            while self.is_running:
                try:
                    msg = receive_message(client_sock)
                except ValueError as ve:
                    # Malformed client message handling without server crash
                    print_error(f"Received malformed payload from {addr_str}: {ve}")
                    log_event(f"Malformed payload from {addr_str}: {ve}", "warning")
                    err_response = {
                        "status": "ERROR",
                        "message": f"Malformed payload: {ve}"
                    }
                    try:
                        send_message(client_sock, err_response)
                    except Exception:
                        pass
                    continue

                if msg is None:
                    # Client disconnected cleanly
                    break

                cmd = msg.get("command", "").upper()

                if cmd == "HELLO":
                    client_name = msg.get("client_name", "UnknownClient")
                    print_info("HELLO received", tag="TCP")
                    log_event(f"HELLO received from {client_name} ({addr_str})")

                    response = {
                        "status": "SUCCESS",
                        "command": "HELLO_ACK",
                        "message": "Connection is working",
                        "client_id": addr_str,
                        "server_status": "RUNNING"
                    }
                    send_message(client_sock, response)
                    print_info("HELLO response sent", tag="TCP")
                    log_event(f"HELLO response sent to {addr_str}")

                elif cmd == "QUIT":
                    response = {"status": "SUCCESS", "message": "Goodbye"}
                    send_message(client_sock, response)
                    break

                else:
                    response = {
                        "status": "ACK",
                        "message": f"Received command '{cmd}'"
                    }
                    send_message(client_sock, response)

        except (socket.error, ConnectionResetError) as e:
            log_event(f"TCP Client {addr_str} connection reset: {e}", "info")
        except Exception as e:
            log_event(f"Error handling TCP client {addr_str}: {e}", "error")
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            with self._lock:
                self.active_clients.pop(addr_str, None)
            print_info(f"Client disconnected: {addr_str}", tag="TCP")
            log_event(f"TCP Client disconnected: {addr_str}")

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
