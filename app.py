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
    """Triggers real Python TCP connection via ClientController."""
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

    # Save incoming browser file to local client downloads staging path
    temp_dir = DOWNLOADS_DIR / "staging"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file_obj.filename
    file_obj.save(str(temp_path))

    # Trigger real Python TCP socket upload to server
    res = controller.upload_file(str(temp_path))

    # Clean up temp staging file
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
    if not filename:
        return jsonify({"success": False, "error": "Filename parameter required"})

    res = controller.download_file(filename)
    return jsonify(res)


@app.route("/api/transfers", methods=["GET"])
def get_transfers():
    """Returns real transfer history."""
    return jsonify({"transfers": controller.get_transfers()})


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Returns activity log entries."""
    return jsonify({"logs": controller.get_activity_logs()})


if __name__ == "__main__":
    print(f"========================================")
    print(f"  HYBRID TRANSFER - PRODUCT WEB ENGINE")
    print(f"========================================")
    print(f"Product UI running at: http://127.0.0.1:8000")
    print(f"Press Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=8000, debug=False)
