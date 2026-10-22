"""
server.py (Root Launcher)
-------------------------
Starts the Flask Backend API Server located in backend/server.py.
Allows running `python server.py` directly from the project root directory.
"""
import sys
import os

backend_dir = os.path.join(os.path.dirname(__file__), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import server

if __name__ == "__main__":
    server.app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
