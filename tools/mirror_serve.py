# -*- coding: utf-8 -*-
"""즉시로 자체 배포 미러 — 표준 라이브러리 기반 정적 HTTPS 파일 서버.

데이터/프로그램 배포 파일(manifest.json, *.db.xz, delta-*.json.xz,
app-latest.json, *.zip)이 있는 폴더를 읽기 전용으로 제공한다.
자체서명 인증서를 쓰며, 앱은 인증서(DER) sha256 고정(pinning)으로 검증한다.

실행(시스템d): ExecStart=python3 tools/mirror_serve.py \
    --dir /home/ubuntu/immediatelylaw-mirror \
    --cert /etc/immediatelylaw-mirror/cert.pem --key /etc/immediatelylaw-mirror/key.pem
"""
import argparse
import functools
import http.server
import re
import socketserver
import ssl

SAFE = re.compile(r"^[\w.\-]+\.?(json|xz|zip|txt|json\.xz)?$")


class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "immediatelylaw-mirror"

    def guess_type(self, path):
        if path.endswith(".json.xz"):
            return "application/x-xz"
        if path.endswith(".xz"):
            return "application/x-xz"
        return super().guess_type(path)

    def send_head(self):
        # 파일명 화이트리스트만 허용(디렉터리 목록·경로 탈출 차단)
        import os
        import urllib.parse
        rel = urllib.parse.urlparse(self.path).path.lstrip("/")
        if not SAFE.match(rel):
            self.send_error(404, "not found")
            return None
        full = os.path.join(self.directory or ".", rel)
        if not os.path.isfile(full):
            self.send_error(404, "not found")
            return None
        return super().send_head()

    def end_headers(self):
        p = self.path.split("?")[0]
        if p.endswith("manifest.json") or p.endswith("app-latest.json"):
            self.send_header("Cache-Control", "no-cache")
        elif p.startswith("delta-") or p.endswith(".db.xz"):
            self.send_header("Cache-Control", "max-age=86400")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("%s %s" % (self.address_string(), fmt % args), flush=True)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="배포 파일 폴더")
    ap.add_argument("--cert", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--port", type=int, default=443)
    a = ap.parse_args()

    handler = functools.partial(Handler, directory=a.dir)
    with Server(("0.0.0.0", a.port), handler) as httpd:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(a.cert, a.key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        print(f"즉시로 미러: https://0.0.0.0:{a.port} ← {a.dir}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
