"""Deterministic OpenAI-compatible vision endpoint for local browser tests only."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        if self.headers.get("Authorization") != "Bearer local-e2e-vision-key":
            self.send_error(401)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        content = body["messages"][0]["content"]
        if not any(item.get("type") == "image_url" for item in content):
            self.send_error(422)
            return
        payload = {"choices": [{"message": {"content": json.dumps({"items": [{"name": "Browser test oatmeal", "grams": 150}]})}}]}
        encoded = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format, *_args):
        return


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(os.environ.get("E2E_VISION_PORT", "0"))), Handler).serve_forever()
