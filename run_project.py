"""
HYBRID TRANSFER - Master Product Launcher
Usage:
  python run_project.py          (Launches Web Product UI on http://127.0.0.1:8000)
  python run_project.py server   (Launches TCP/UDP Server on 127.0.0.1:5000)
  python run_project.py cli      (Launches Terminal CLI Client)
"""

import sys
import subprocess
from pathlib import Path

# Add project root directory to python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def main():
    mode = "web"
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    if mode == "server":
        print("[LAUNCHER] Starting HYBRID TRANSFER Server...")
        subprocess.run([sys.executable, "-u", "server/server.py"])
    elif mode == "cli":
        print("[LAUNCHER] Starting HYBRID TRANSFER Terminal CLI Mode...")
        subprocess.run([sys.executable, "-u", "client/client.py"])
    elif mode in ["web", "ui", "app"]:
        print("==================================================")
        print("   HYBRID TRANSFER - PRODUCT APPLICATION")
        print("==================================================")
        print("Launching Web Product Engine on http://127.0.0.1:8000 ...")
        subprocess.run([sys.executable, "app.py"])
    else:
        print(f"Unknown mode '{mode}'. Available options: web, server, cli")


if __name__ == "__main__":
    main()
