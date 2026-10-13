"""
Vercel Serverless Function Entry Point for HYBRID TRANSFER.
Bridges incoming Vercel HTTP/WSGI requests to the Flask web application.
"""

import sys
import os
from pathlib import Path

# Add root directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import the main Flask application
from app import app

# Vercel WSGI callable
# When deployed to Vercel, the runtime looks for `app` in api/index.py
if __name__ == "__main__":
    app.run(debug=True)
