"""Lightweight Local Interactive Server for DepRadar.
Uses Python standard library http.server to provide zero-dependency live visualization,
real-time re-scanning, and safe directory pruning.
"""

import os
import json
import shutil
import platform
import webbrowser
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

from .graph import build_graph
from .generator import generate_html
from .models import get_default_output_dir
from .diff import save_snapshot, list_snapshots, load_snapshot, compute_diff
from .audit import audit_packages

class DepRadarHandler(BaseHTTPRequestHandler):
    graph_data_cache: Optional[Dict[str, Any]] = None

    def log_message(self, format, *args):
        # Quiet logging
        pass

    def send_json(self, status_code: int, data: Any):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        url = self.path.split("?")[0]

        if url == "/" or url == "/index.html":
            # Generate and serve live HTML viewer
            g = build_graph()
            out_file = get_default_output_dir() / "live_viewer.html"
            generate_html(g, out_file)
            content = out_file.read_bytes()

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        elif url == "/api/graph":
            g = build_graph()
            self.send_json(200, g.to_dict())
            return

        elif url == "/api/audit":
            g = build_graph()
            res = audit_packages(g)
            self.send_json(200, res)
            return

        elif url == "/api/snapshots":
            snaps = list_snapshots()
            self.send_json(200, snaps)
            return

        elif url == "/api/health":
            self.send_json(200, {"status": "ok", "platform": platform.system()})
            return

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        url = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        req_data = {}
        if body:
            try:
                req_data = json.loads(body.decode("utf-8"))
            except Exception:
                pass

        if url == "/api/snapshot":
            g = build_graph()
            label = req_data.get("label", "manual")
            snap_path = save_snapshot(g, label)
            self.send_json(200, {"success": True, "path": str(snap_path)})
            return

        elif url == "/api/prune":
            target_path_str = req_data.get("path")
            if not target_path_str:
                self.send_json(400, {"error": "Missing target path"})
                return

            target = Path(target_path_str).resolve()
            home = Path.home().resolve()

            # Safety Guardrails: Protect critical operating system and root directories
            if target == home or target == Path("/") or len(target.parts) < 3:
                self.send_json(403, {"error": "Refusing to delete critical system or home directory"})
                return

            if not target.exists():
                self.send_json(404, {"error": "Target path does not exist"})
                return

            # Prune directory
            try:
                # Try send2trash first if available for safe OS trash bin routing
                try:
                    import send2trash
                    send2trash.send2trash(str(target))
                    method = "trash"
                except ImportError:
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                    method = "delete"

                self.send_json(200, {
                    "success": True,
                    "target": str(target),
                    "method": method,
                    "message": f"Successfully removed {target.name}"
                })
            except Exception as e:
                self.send_json(500, {"error": str(e)})
            return

        else:
            self.send_response(404)
            self.end_headers()

def run_server(port: int = 8080, open_browser: bool = True):
    """Starts the local DepRadar HTTP server daemon."""
    server_address = ("127.0.0.1", port)
    try:
        httpd = HTTPServer(server_address, DepRadarHandler)
    except OSError:
        # Fall back to next port if occupied
        port += 1
        server_address = ("127.0.0.1", port)
        httpd = HTTPServer(server_address, DepRadarHandler)

    url = f"http://localhost:{port}"
    print(f"🚀 DepRadar interactive daemon running at: {url}")
    print(f"📡 Real-time API endpoints active: /api/graph, /api/audit, /api/snapshots, /api/prune")
    print(f"Press Ctrl+C to stop.")

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping DepRadar server...")
        httpd.server_close()
