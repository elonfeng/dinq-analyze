#!/usr/bin/env python3
"""
DINQ Gateway playground dev server (static + reverse proxy).

Why:
- Browsers enforce CORS. If the Gateway doesn't enable CORS for localhost, a
  page served from http://localhost:* cannot call https://api.dinq.me directly.
- This server serves the playground UI and proxies /api/* to the real gateway,
  so the browser sees same-origin requests (no CORS).

Usage:
  cd dinq/test/frontend
  python dev_proxy.py --port 8000 --upstream https://api.dinq.me

Then open:
  http://localhost:8000

In the UI, set "API Base" to:
  http://localhost:8000
"""

from __future__ import annotations

import argparse
import errno
import http.server
import os
import socketserver
import sys
import urllib.error
import urllib.request
from typing import Dict


HOP_BY_HOP_REQ_HEADERS = {
    "connection",
    "proxy-connection",
    "keep-alive",
    "te",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "accept-encoding",  # force upstream to return uncompressed bytes
}

HOP_BY_HOP_RESP_HEADERS = {
    "connection",
    "proxy-connection",
    "keep-alive",
    "te",
    "transfer-encoding",
    "upgrade",
}


def _copy_request_headers(handler: http.server.BaseHTTPRequestHandler) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for key, value in handler.headers.items():
        if key.lower() in HOP_BY_HOP_REQ_HEADERS:
            continue
        headers[key] = value
    return headers


def _send_cors(handler: http.server.BaseHTTPRequestHandler) -> None:
    origin = handler.headers.get("Origin") or "*"
    handler.send_header("Access-Control-Allow-Origin", origin)
    handler.send_header("Vary", "Origin")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type,Idempotency-Key")
    handler.send_header("Access-Control-Expose-Headers", "Content-Type")


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    upstream_base: str = "https://api.dinq.me"

    def _is_api(self) -> bool:
        return self.path.startswith("/api/")

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self._is_api():
            self.send_response(204)
            _send_cors(self)
            self.end_headers()
            return
        super().do_OPTIONS()

    def do_GET(self) -> None:  # noqa: N802
        if self._is_api():
            self._proxy()
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self._is_api():
            self._proxy()
            return
        self.send_error(404, "POST only supported for /api/*")

    def _proxy(self) -> None:
        upstream = self.upstream_base.rstrip("/")
        target_url = f"{upstream}{self.path}"

        body = b""
        if self.command in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length") or "0")
            if length > 0:
                body = self.rfile.read(length)

        req_headers = _copy_request_headers(self)

        request = urllib.request.Request(
            target_url,
            data=body if body else None,
            headers=req_headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(request, timeout=180) as resp:
                self.send_response(resp.status)
                _send_cors(self)

                for key, value in resp.headers.items():
                    if key.lower() in HOP_BY_HOP_RESP_HEADERS:
                        continue
                    self.send_header(key, value)
                self.end_headers()

                # Stream bytes to client (works for SSE).
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except BrokenPipeError:
                        break
        except urllib.error.HTTPError as err:
            # Forward upstream error status + best-effort body.
            self.send_response(err.code)
            _send_cors(self)
            self.send_header("Content-Type", err.headers.get("Content-Type", "text/plain"))
            self.end_headers()
            try:
                self.wfile.write(err.read() or b"")
            except Exception:
                pass
        except Exception as err:  # noqa: BLE001
            self.send_response(502)
            _send_cors(self)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"proxy error: {err}\n".encode("utf-8"))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="DINQ Gateway playground dev server (static + /api proxy).")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--upstream", type=str, default=os.environ.get("DINQ_GATEWAY_BASE", "https://api.dinq.me"))
    args = parser.parse_args(argv)

    directory = os.path.dirname(os.path.abspath(__file__))

    handler_cls = ProxyHandler
    handler_cls.upstream_base = str(args.upstream or "https://api.dinq.me")

    # Bind static file directory for SimpleHTTPRequestHandler.
    def handler_factory(*inner_args, **inner_kwargs):
        return handler_cls(*inner_args, directory=directory, **inner_kwargs)

    class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

        if hasattr(socketserver.ThreadingTCPServer, "allow_reuse_port"):
            allow_reuse_port = True

    try:
        httpd = ReusableThreadingTCPServer((args.host, args.port), handler_factory)
    except OSError as err:
        if err.errno in (errno.EADDRINUSE, 10048):
            print(
                f"Error: {args.host}:{args.port} is already in use.\n"
                f"Try a different port: python dev_proxy.py --port {args.port + 1}\n"
                f"Or stop the process using it (Linux/WSL: lsof -i :{args.port} | Windows: netstat -ano | findstr :{args.port}).",
                file=sys.stderr,
            )
            return 2
        raise

    with httpd:
        print(f"Serving playground at http://{args.host}:{args.port}")
        print(f"Proxying /api/* -> {handler_cls.upstream_base}")
        print("Tip: set UI 'API Base' to this server (same origin).")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
