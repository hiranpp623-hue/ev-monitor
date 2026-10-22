"""
backend.py (Root Launcher Alias)
--------------------------------
Alias for server.py so running `python backend.py` starts the server.
"""
from server import app

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
