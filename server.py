"""
server.py (Root WSGI Launcher)
------------------------------
Entry point for Render, Railway, Gunicorn, and local launch.
Exposes `app` at module level so `gunicorn server:app` works seamlessly.
"""
import os
import sys
import importlib.util

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_SERVER_PATH = os.path.join(CURRENT_DIR, "backend", "server.py")

# Ensure backend directory is in sys.path
backend_dir = os.path.join(CURRENT_DIR, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Load backend/server.py under distinct module name to avoid circular import
spec = importlib.util.spec_from_file_location("backend_server", BACKEND_SERVER_PATH)
backend_server = importlib.util.module_from_spec(spec)
sys.modules["backend_server"] = backend_server
spec.loader.exec_module(backend_server)

# Expose app for WSGI servers like Gunicorn
app = backend_server.app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
