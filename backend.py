"""
backend.py (Root Launcher Alias)
--------------------------------
Alias for server.py so running `python backend.py` starts the server.
"""
import sys
import os

backend_dir = os.path.join(os.path.dirname(__file__), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import server

if __name__ == "__main__":
    server.app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
