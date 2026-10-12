"""
HYBRID TRANSFER - Web Application Product Server
Bridges the HTML5/CSS3 Web UI to real Python TCP and UDP Socket Engine.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from flask import Flask, render_template, jsonify, request
from client.client_controller import controller
from shared.config import DEFAULT_HOST, TCP_PORT, UDP_PORT, DOWNLOADS_DIR

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "web" / "templates"),
    static_folder=str(BASE_DIR / "web" / "static")
)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True


@app.route("/")
def index():
    """Serves the Product UI Dashboard SPA."""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    """Returns real connection state."""
    return jsonify(controller.get_status())


@app.route("/api/connect", methods=["POST"])
def connect_server():
    """Triggers real Python TCP & UDP connections via ClientController."""
    data = request.json or {}
    host = data.get("host", DEFAULT_HOST)
    tcp_port = data.get("tcp_port", TCP_PORT)
    udp_port = data.get("udp_port", UDP_PORT)
    username = data.get("username", "Keerthi")

    result = controller.connect(host, tcp_port, udp_port, username)
    return jsonify(result)


@app.route("/api/disconnect", methods=["POST"])
def disconnect_server():
    """Triggers disconnect on real Python sockets."""
    result = controller.disconnect()
    return jsonify(result)


@app.route("/api/files", methods=["GET"])
def get_files():
    """Lists files available on the TCP server."""
    files = controller.list_files()
    return jsonify({"files": files})


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Receives browser file upload and triggers real TCP streaming upload to server."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded in request"})

    file_obj = request.files["file"]
    if not file_obj.filename:
        return jsonify({"success": False, "error": "Empty filename"})

    resume = request.form.get("resume", "false").lower() == "true"

    temp_dir = DOWNLOADS_DIR / "staging"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file_obj.filename
    file_obj.save(str(temp_path))

    res = controller.upload_file(str(temp_path), resume=resume)

    if temp_path.exists():
        try:
            temp_path.unlink()
        except Exception:
            pass

    return jsonify(res)


@app.route("/api/download", methods=["POST"])
def download_file():
    """Triggers real TCP streaming download from server to client storage."""
    data = request.json or {}
    filename = data.get("filename", "")
    resume = data.get("resume", False)
    if not filename:
        return jsonify({"success": False, "error": "Filename parameter required"})

    res = controller.download_file(filename, resume=resume)
    return jsonify(res)


@app.route("/api/chat/send", methods=["POST"])
def send_chat():
    """Triggers UDP chat message datagram sending to server."""
    data = request.json or {}
    msg_text = data.get("message", "")
    recipient = data.get("recipient")
    if not msg_text:
        return jsonify({"success": False, "error": "Message parameter required"})

    res = controller.send_chat_message(msg_text, recipient=recipient)
    return jsonify(res)


@app.route("/api/chat/messages", methods=["GET"])
def get_chat_messages():
    """Returns chat history received over UDP datagrams."""
    messages = controller.get_chat_history()
    return jsonify({"messages": messages})


@app.route("/api/users", methods=["GET"])
def get_users():
    """Returns list of online users from UDP server presence registry."""
    users = controller.get_online_users()
    return jsonify({"users": users})


@app.route("/api/partials", methods=["GET"])
def get_partials():
    """Returns partial files available for transfer resume."""
    partials = controller.list_partial_files()
    return jsonify({"partials": partials})


@app.route("/api/transfers", methods=["GET"])
def get_transfers():
    """Returns real transfer history."""
    return jsonify({"transfers": controller.get_transfers()})


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Returns activity log entries."""
    return jsonify({"logs": controller.get_activity_logs()})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Returns real-time network monitor metrics (throughput, latency RTT, packets, reliability)."""
    return jsonify(controller.get_network_stats())


@app.route("/api/simulation", methods=["POST"])
def set_simulation():
    """Sets simulated UDP packet loss rate (e.g., 0.20 = 20% dropped packets)."""
    data = request.json or {}
    rate = data.get("rate", 0.0)
    res = controller.set_simulated_loss(rate)
    return jsonify(res)


# --- Module 2: Peer-to-Peer TCP File Transfer Routes ---

@app.route("/api/peer/users", methods=["GET"])
def get_peer_users():
    """Returns connected TCP peers for peer-to-peer file transfer."""
    users = controller.list_tcp_online_users()
    return jsonify({"users": users})


@app.route("/api/peer/incoming", methods=["GET"])
def get_peer_incoming():
    """Checks pending incoming transfer requests for the receiver."""
    requests_list = controller.check_incoming_transfers()
    return jsonify({"requests": requests_list})


@app.route("/api/peer/send", methods=["POST"])
def send_peer_file_route():
    """Initiates peer-to-peer transfer from sender to receiver."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded in request"})
    receiver = request.form.get("receiver", "").strip()
    if not receiver:
        return jsonify({"success": False, "error": "Receiver username required"})

    file_obj = request.files["file"]
    temp_dir = DOWNLOADS_DIR / "staging"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file_obj.filename
    file_obj.save(str(temp_path))

    res = controller.send_peer_file(receiver, str(temp_path))
    if temp_path.exists():
        try:
            temp_path.unlink()
        except Exception:
            pass
    return jsonify(res)


@app.route("/api/peer/accept", methods=["POST"])
def accept_peer_transfer_route():
    """Receiver accepts pending transfer offer and downloads file."""
    data = request.json or {}
    transfer_id = data.get("transfer_id", "")
    filename = data.get("filename", "")
    filesize = data.get("filesize", 0)
    checksum = data.get("checksum", "")
    custom_dir = data.get("custom_dir")

    res = controller.accept_peer_transfer(transfer_id, filename, filesize, checksum, custom_downloads_dir=custom_dir)
    return jsonify(res)


@app.route("/api/peer/reject", methods=["POST"])
def reject_peer_transfer_route():
    """Receiver rejects pending transfer offer."""
    data = request.json or {}
    transfer_id = data.get("transfer_id", "")
    reason = data.get("reason", "Declined by user")
    res = controller.reject_peer_transfer(transfer_id, reason=reason)
    return jsonify(res)



if __name__ == "__main__":
    print(f"========================================")
    print(f"  HYBRID TRANSFER - PRODUCT WEB ENGINE")
    print(f"========================================")
    print(f"Product UI running at: http://127.0.0.1:8000")
    print(f"Press Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=8000, debug=False)
