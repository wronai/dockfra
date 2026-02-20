"""Artifact server for desktop app builds — serves downloads and build status."""
import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

APP_NAME = os.environ.get("APP_NAME", "InfraDemo")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
DEPLOY_MODE = os.environ.get("DEPLOY_MODE", "local")
PORT = int(os.environ.get("DESKTOP_APP_PORT", 8083))
DIST_DIR = "/app/dist"


class ArtifactHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/health":
            self._json_response({
                "status": "ok",
                "service": "desktop-app",
                "version": APP_VERSION,
                "deploy_mode": DEPLOY_MODE,
                "timestamp": datetime.utcnow().isoformat()
            })
        elif self.path == "/artifacts":
            artifacts = []
            if os.path.isdir(DIST_DIR):
                for f in os.listdir(DIST_DIR):
                    fp = os.path.join(DIST_DIR, f)
                    if os.path.isfile(fp):
                        artifacts.append({
                            "name": f,
                            "size": os.path.getsize(fp),
                            "url": f"/{f}"
                        })
            self._json_response({"artifacts": artifacts, "version": APP_VERSION})
        else:
            super().do_GET()

    def _json_response(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"[*] Desktop artifact server starting on :{PORT}")
    print(f"[*] Serving from: {DIST_DIR}")
    server = HTTPServer(("0.0.0.0", PORT), ArtifactHandler)
    server.serve_forever()
