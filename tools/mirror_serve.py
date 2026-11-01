# -*- coding: utf-8 -*-
"""즉시로 배포 서버 — 읽기 전용 정적 HTTPS 파일 서버(범위 제한·격리 TLS 워커).

프로그램 배포 파일(manifest.json, *.db.xz, delta-*.json.xz, app-latest.json,
*.zip, 랜딩 페이지)만 공개용으로 제공한다. 자체서명 인증서를 쓰며, 앱은 인증서
(DER) sha256 고정(pinning)으로 검증한다. 요청당 연결은 닫아버리고(header_timeout),
동시 TLS 워커 수와 타임아웃에 상한이 있어 accept 루프가 멈추지 않는다.

실행( systemd): ExecStart=python3 tools/mirror_serve.py \
    --dir /home/ubuntu/immediatelylaw-mirror \
    --cert /etc/immediatelylaw-mirror/cert.pem --key /etc/immediatelylaw-mirror/key.pem
"""
import argparse
import functools
import http.server
import os
import re
import socket
import socketserver
import ssl
import threading
import urllib.parse


# 확장자 화이트리스트 + 단일 서브디렉터리(fonts/ 등 1단계)만 허용(다단계 경로 불허).
SAFE = re.compile(r"^(?:[\w.\-]+/)?[\w.\-]+\."
                  r"(json|xz|zip|txt|html|png|jpg|jpeg|svg|ico|mp4|woff2|woff)$")


class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "immediatelylaw-mirror"
    sys_version = ""

    def handle_one_request(self):
        self._header_timer = threading.Timer(
            self.server.header_timeout, self._expire_headers
        )
        self._header_timer.daemon = True
        self._header_timer.start()
        try:
            super().handle_one_request()
        finally:
            self._header_timer.cancel()
            self.close_connection = True

    def _expire_headers(self):
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def parse_request(self):
        result = super().parse_request()
        self._header_timer.cancel()
        self.close_connection = True
        return result

    def guess_type(self, path):
        if path.endswith(".json.xz") or path.endswith(".xz"):
            return "application/x-xz"
        if path.endswith(".woff2"):          # 서버 Python 버전 무관 고정 MIME
            return "font/woff2"              # (mimetypes 테이블은 버전에 따라 다름)
        if path.endswith(".woff"):
            return "font/woff"
        return super().guess_type(path)

    def send_head(self):
        try:
            rel = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path).lstrip("/")
        except ValueError:
            self.send_error(400, "invalid request target")
            return None
        if not rel:
            rel = "index.html"
        if not SAFE.fullmatch(rel):
            self.send_error(404, "not found")
            return None
        root = os.path.realpath(self.directory)
        full = os.path.realpath(os.path.join(root, rel))
        if os.path.commonpath((root, full)) != root or not os.path.isfile(full):
            self.send_error(404, "not found")
            return None
        return super().send_head()

    def end_headers(self):
        p = getattr(self, "path", "").split("?", 1)[0]
        if p.endswith(("manifest.json", "app-latest.json")):
            self.send_header("Cache-Control", "no-cache")
        elif p.endswith(".db.xz") or p.lstrip("/").startswith("delta-"):
            self.send_header("Cache-Control", "max-age=86400")
        elif p.endswith(".html") or p in ("", "/"):
            self.send_header("Cache-Control", "no-cache")
        elif p.endswith((".png", ".jpg", ".jpeg", ".mp4", ".ico", ".svg",
                         ".woff2", ".woff")):
            self.send_header("Cache-Control", "max-age=86400")
        self.send_header("Connection", "close")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.close_connection = True
        super().end_headers()

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 128

    def __init__(self, address, handler, context, *, max_connections=64,
                 handshake_timeout=5, header_timeout=10, io_timeout=30):
        self.context = context
        self.handshake_timeout = handshake_timeout
        self.header_timeout = header_timeout
        self.io_timeout = io_timeout
        self.slots = threading.BoundedSemaphore(max_connections)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def finish_request(self, request, client_address):
        # A stalled TLS handshake must never block the accept loop.
        try:
            request.settimeout(self.handshake_timeout)
            with self.context.wrap_socket(
                request, server_side=True, do_handshake_on_connect=False
            ) as tls:
                tls.do_handshake()
                tls.settimeout(self.io_timeout)
                super().finish_request(tls, client_address)
        except (OSError, TimeoutError):
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--cert", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--port", type=int, default=443)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--max-connections", type=int, default=64)
    ap.add_argument("--handshake-timeout", type=float, default=5)
    ap.add_argument("--header-timeout", type=float, default=10)
    ap.add_argument("--io-timeout", type=float, default=30)
    args = ap.parse_args()
    if args.max_connections < 1 or min(
        args.handshake_timeout, args.header_timeout, args.io_timeout
    ) <= 0:
        ap.error("connection limits and timeouts must be positive")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.cert, args.key)
    handler = functools.partial(Handler, directory=args.dir)
    with Server(
        (args.host, args.port), handler, context,
        max_connections=args.max_connections,
        handshake_timeout=args.handshake_timeout,
        header_timeout=args.header_timeout,
        io_timeout=args.io_timeout,
    ) as httpd:
        print(
            f"즉시로 배포 서버 https://{args.host}:{args.port} ← {args.dir} "
            f"(workers<={args.max_connections}, TLS={args.handshake_timeout}s "
            f"headers={args.header_timeout}s I/O={args.io_timeout}s)", flush=True
        )
        httpd.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
