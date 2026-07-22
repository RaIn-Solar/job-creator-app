"""Solbiz Desktop launcher.

Starts Solbiz as a little local web server and opens it in the default
browser, so a teammate can run the whole app by double-clicking one file.
Their data (the database + uploaded files) is kept in a personal "Solbiz"
folder under their home directory, separate from the program itself, so it
survives replacing the app with a newer build.

This file is the entry point PyInstaller bundles into Solbiz.exe; it also
runs directly with `python desktop/run_solbiz.py` for testing.
"""

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

# Each person gets their own copy of the data here. Chosen BEFORE importing
# app, because app reads SOLBIZ_DATA_DIR at import time.
DATA_DIR = Path.home() / "Solbiz"
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("SOLBIZ_DATA_DIR", str(DATA_DIR))

# When frozen, the bundled app package is on sys.path already; when running
# from source, add the repo root (this file's parent's parent) so `app`
# imports.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app, init_db  # noqa: E402


def _free_port():
    """Grab an available localhost port so two copies (or another program
    on 5000) never collide."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    init_db()
    port = _free_port()
    url = f"http://127.0.0.1:{port}/"
    print("=" * 60)
    print("  Solbiz is starting up...")
    print(f"  It will open in your web browser at:  {url}")
    print("  Your data is saved in:  " + str(DATA_DIR))
    print()
    print("  KEEP THIS WINDOW OPEN while you use Solbiz.")
    print("  Close this window to shut Solbiz down.")
    print("=" * 60)
    # Open the browser a moment after the server starts listening.
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    # debug=False: no reloader (which would fail inside a frozen exe) and no
    # debugger. threaded=True so the browser and app can talk concurrently.
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
