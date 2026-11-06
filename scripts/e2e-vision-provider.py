"""Deterministic OpenAI-compatible vision endpoint for local browser tests only."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sys
from urllib.parse import urlparse

FAILED_ASSISTANT_PROMPTS=set()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlparse(self.path).path
        if path == "/api/v3/product/3017624010701.json":
            if not self.headers.get("User-Agent","").startswith("LossFit/"):
                self.send_error(400);return
            payload={"code":"3017624010701","status":"success","product":{"product_name":"Browser test cocoa spread","brands":"Example Brand","quantity":"350 g","categories":"Spreads","nutrition_data_per":"100g","nutriments":{"energy-kcal_100g":539,"proteins_100g":6.3,"carbohydrates_100g":57.5,"fat_100g":30.9}}}
            encoded=json.dumps(payload).encode();self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(encoded)));self.end_headers();self.wfile.write(encoded);return
        if path != "/health":
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
        user_parts = []
        for message in messages:
            if message.get("role") != "user":
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                user_parts.append(content)
            elif isinstance(content, list):
                user_parts.extend(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text")
        user_text = " ".join(user_parts).casefold()
        outage_prompt="simulate the temporary provider outage and retry this question"
        if outage_prompt in user_text and outage_prompt not in FAILED_ASSISTANT_PROMPTS:
            FAILED_ASSISTANT_PROMPTS.add(outage_prompt)
            encoded=json.dumps({"error":{"message":"Deterministic provider outage for retry verification."}}).encode()
            self.send_response(503)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        if "log my weight as 68.4 kg" in user_text:
            message = {"tool_calls": [{"id": "call-local-weight", "type": "function", "function": {"name": "propose_weight", "arguments": '{"weight_kg":68.4}'}}]}
        elif "log 250 ml of water" in user_text:
            message = {"tool_calls": [{"id": "call-local-water", "type": "function", "function": {"name": "propose_water", "arguments": '{"water_ml":250}'}}]}
        elif has_image and "nutrition facts panel" in user_text:
            answer = json.dumps({"name": "Browser label granola", "brand": "Test", "serving_label": "1 bar", "serving_grams": 125, "basis": "per_serving", "kcal": 100, "protein": 8, "carbs": 12, "fat": None})
            message = {"content": answer}
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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("E2E_VISION_PORT", "0"))
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
