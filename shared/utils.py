"""
Utility functions for terminal formatting, icons, and timestamping.
"""

import sys
from datetime import datetime

# Ensure stdout and stderr use UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class TermColor:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def get_timestamp() -> str:
    """Returns formatted HH:MM:SS timestamp."""
    return datetime.now().strftime("%H:%M:%S")


def print_success(msg: str) -> None:
    try:
        print(f"{TermColor.GREEN}[OK {get_timestamp()}]{TermColor.RESET} {msg}", flush=True)
    except Exception:
        print(f"[OK {get_timestamp()}] {msg}", flush=True)


def print_error(msg: str) -> None:
    try:
        print(f"{TermColor.RED}[ERROR {get_timestamp()}]{TermColor.RESET} {msg}", flush=True)
    except Exception:
        print(f"[ERROR {get_timestamp()}] {msg}", flush=True)


def print_info(msg: str, tag: str = "INFO") -> None:
    try:
        print(f"{TermColor.CYAN}[{tag} {get_timestamp()}]{TermColor.RESET} {msg}", flush=True)
    except Exception:
        print(f"[{tag} {get_timestamp()}] {msg}", flush=True)


def print_warning(msg: str) -> None:
    try:
        print(f"{TermColor.YELLOW}[WARN {get_timestamp()}]{TermColor.RESET} {msg}", flush=True)
    except Exception:
        print(f"[WARN {get_timestamp()}] {msg}", flush=True)


