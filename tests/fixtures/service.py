from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--broken", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state: dict[str, Any] = {
        "effect_count": 0,
        "processed_event_ids": [],
        "sequence": 0,
        "status": "new",
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_error(404)
                return
            self.send_response(200)
            self.end_headers()

        def do_POST(self) -> None:
            if self.path != "/webhook":
                self.send_error(404)
                return
            length = int(self.headers["Content-Length"])
            event = json.loads(self.rfile.read(length))
            if event["kind"] == "reject":
                self.send_error(422)
                return

            event_id = event["id"]
            duplicate = event_id in state["processed_event_ids"]
            if args.broken or not duplicate:
                if event["kind"] == "completed":
                    state["effect_count"] += 1
                if args.broken or event["sequence"] >= state["sequence"]:
                    state["sequence"] = event["sequence"]
                    state["status"] = event["kind"]
            if not duplicate:
                state["processed_event_ids"].append(event_id)
            args.state.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
            self.send_response(202)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
