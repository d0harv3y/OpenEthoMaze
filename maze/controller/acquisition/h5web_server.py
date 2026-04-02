"""
Local server for the h5web viewer: serves static h5web build + h5grove API.

Used when the user clicks "Open H5 in h5web". No Node required at runtime.
"""

from __future__ import annotations

import socket
import threading
from pathlib import Path
from typing import Optional

from flask import Flask, send_from_directory

from h5grove.flask_utils import (
    attr_route as h5_attr_route,
    data_route as h5_data_route,
    meta_route as h5_meta_route,
    root_route as h5_root_route,
    stats_route as h5_stats_route,
)


def get_h5web_static_dir() -> Optional[Path]:
    """Return path to web/h5web_dist (built React app), or None if not found."""
    # Package dir: maze/controller/acquisition/; repo root is one level up from there.
    package_dir = Path(__file__).resolve().parent
    repo_root = package_dir.parent
    static_dir = repo_root / "web" / "h5web_dist"
    if static_dir.is_dir() and (static_dir / "index.html").exists():
        return static_dir
    return None


def create_app(h5_base_dir: Path, static_dir: Path) -> Flask:
    """Flask app: h5grove API under /api + static files for the h5web frontend at /.

    Keep h5grove (Python) on the same major line as the embedded @h5web/app build;
    rebuild ``web/h5web_dist``
    after bumping the npm package.
    """
    app = Flask(__name__)
    app.config["H5_BASE_DIR"] = str(h5_base_dir.resolve())

    # h5grove endpoints under /api/*
    @app.route("/api/", strict_slashes=False)
    def api_root():
        return h5_root_route()

    @app.route("/api/meta", strict_slashes=False)
    def api_meta():
        return h5_meta_route()

    @app.route("/api/data", strict_slashes=False)
    def api_data():
        return h5_data_route()

    @app.route("/api/attr", strict_slashes=False)
    def api_attr():
        return h5_attr_route()

    @app.route("/api/stats", strict_slashes=False)
    def api_stats():
        return h5_stats_route()

    @app.route("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    # Serve built assets under /assets/... so that /api/... remains handled by h5grove.
    @app.route("/assets/<path:path>")
    def static_files(path: str):
        return send_from_directory(static_dir / "assets", path)

    # Optional: favicon (avoid 404 noise)
    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(static_dir, "favicon.ico")

    return app


def run_server(
    h5_file: Path,
    static_dir: Path,
    host: str = "127.0.0.1",
) -> tuple[int, threading.Thread]:
    """
    Start the Flask server in a daemon thread. Returns (port, thread).
    The server will run until the process exits (daemon thread).
    """
    app = create_app(h5_file.parent, static_dir)
    # Bind to port 0 to get an ephemeral port, then pass it to Flask
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, 0))
    port = sock.getsockname()[1]
    sock.close()

    def run():
        app.run(host=host, port=port, threaded=True, use_reloader=False)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return port, thread
