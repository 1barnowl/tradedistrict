#!/usr/bin/env python3
"""Trade District — native desktop window launcher."""
import sys
import os
import threading
import time

# ── Path bootstrap ────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR   = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

os.chdir(BASE_DIR)
if BUNDLE_DIR not in sys.path:
    sys.path.insert(0, BUNDLE_DIR)

# DB lives next to the executable, persists between runs
os.environ['TD_DB_PATH'] = os.path.join(BASE_DIR, 'tradedistrict.db')

# ── Init database BEFORE importing app ───────────────────────────────────────
import database as db
db.init_db()

# ── Import app (tables now exist) ─────────────────────────────────────────────
from app import app

# ── Start Flask in background thread ─────────────────────────────────────────
def _run_flask():
    app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)

flask_thread = threading.Thread(target=_run_flask, daemon=True)
flask_thread.start()

# Wait for Flask to be ready
time.sleep(1.5)

# ── Open native desktop window (no browser chrome) ───────────────────────────
try:
    import webview
    window = webview.create_window(
        'Trade District 1.0',
        'http://127.0.0.1:5000',
        width=1400,
        height=900,
        resizable=True,
        min_size=(900, 600),
    )
    webview.start(gui='qt')
except Exception as e:
    # Fallback: open in browser if webview unavailable
    print(f"[Trade District] Native window unavailable ({e}), opening browser...")
    import webbrowser
    webbrowser.open('http://127.0.0.1:5000')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
