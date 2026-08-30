"""Tiny webhook handler used to demonstrate WebhookWitness."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--broken", action="store_true")
    args = parser.parse_args()

    state = {
        "effect_count": 0,
        "processed_event_ids": [],
        "sequence": 0,
        "status": "new",
    }
    args.state.parent.mkdir(parents=True, exist_ok=True)

    def persist() -> None:
        args.state.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    persist()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_error(404)
                return
            self.send_response(204)
            self.end_headers()

        def do_POST(self) -> None:
            if self.path != "/webhook":
                self.send_error(404)
                return
            try:
                length = int(self.headers["Content-Length"])
                payload = json.loads(self.rfile.read(length))
                event_id = self.headers["X-Event-ID"]
                sequence = int(payload["sequence"])
                status = payload["status"]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                self.send_error(400)
                return

            already_processed = event_id in state["processed_event_ids"]
            if args.broken or not already_processed:
                state["processed_event_ids"].append(event_id)
                if status == "completed":
                    state["effect_count"] += 1

            if args.broken or sequence >= state["sequence"]:
                state["sequence"] = sequence
                state["status"] = status

            persist()
            self.send_response(202)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
