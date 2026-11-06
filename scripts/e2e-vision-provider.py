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
        messages = body["messages"]
        content = messages[-1]["content"]
        has_image = isinstance(content, list) and any(item.get("type") == "image_url" for item in content if isinstance(item, dict))
        user_text = " ".join(message.get("content", "") for message in messages if message.get("role") == "user" and isinstance(message.get("content"), str)).casefold()
        if "log 250 ml of water" in user_text:
            message = {"tool_calls": [{"id": "call-local-water", "type": "function", "function": {"name": "propose_water", "arguments": '{"water_ml":250}'}}]}
        elif has_image:
            answer = json.dumps({"items": [{"name": "Browser test oatmeal", "grams": 150}]})
            message = {"content": answer}
        else:
            message = {"content": "This is a deterministic test response based on your saved nutrition log."}
        payload = {"choices": [{"message": message}]}
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
