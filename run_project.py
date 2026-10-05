"""
Runner script to launch Server and Client for quick testing.
Usage:
  python run_project.py server
  python run_project.py client
"""

import sys
import subprocess


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run_project.py server")
        print("  python run_project.py client")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "server":
        subprocess.run([sys.executable, "server/server.py"])
    elif cmd == "client":
        subprocess.run([sys.executable, "client/client.py"])
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
