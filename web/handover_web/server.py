"""HTTP server versi web (stdlib, tanpa dependensi tambahan).

Route:
  GET  /                 halaman dashboard
  GET  /static/...       css, js, ikon
  GET  /healthz          cek hidup (tanpa login, untuk Docker HEALTHCHECK / reverse proxy)
  GET  /api/config       judul, tanggal hari ini, daftar tim, tujuan Telegram
  GET  /api/issues       ?start=YYYY-MM-DD&end=YYYY-MM-DD[&refresh=1]
  POST /api/preview      {start, end, categories, teams, detail, split, keys} -> pesan
  POST /api/send         sama dengan preview, lalu kirim ke Telegram
"""

from __future__ import annotations

import base64
import hmac
import json
import logging
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .app import HandoverWeb, WebError
from .config import WebSettings

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).with_name("static")
MAX_BODY = 2_000_000
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".html": "text/html; charset=utf-8", ".svg": "image/svg+xml"}


def static_file(rel: str) -> Path | None:
    """File di dalam STATIC_DIR saja (tolak ../ dan path absolut)."""
    path = (STATIC_DIR / rel).resolve()
    if not path.is_relative_to(STATIC_DIR.resolve()) or not path.is_file():
        return None
    return path


def make_handler(app: HandoverWeb) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "HandoverWeb"
        sys_version = ""

        def log_message(self, fmt, *args):
            if self.path == "/healthz":
                return  # HEALTHCHECK Docker tiap 30 detik, tidak perlu dicatat
            log.info("%s %s", self.address_string(), app.scrub(fmt % args))

        def _reply(self, status: int, body: bytes, ctype: str, cache: str = "no-store") -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, obj) -> None:
            self._reply(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _static(self, rel: str) -> None:
            path = static_file(rel)
            if path is None:
                raise WebError("Tidak ditemukan", 404)
            ctype = TYPES.get(path.suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            # no-cache: browser boleh simpan, tapi selalu cek ulang supaya update langsung terpakai.
            self._reply(200, path.read_bytes(), ctype, cache="no-cache")

        def _authorized(self) -> bool:
            pw = app.settings.password
            if not pw:
                return True
            h = self.headers.get("Authorization", "")
            try:
                given = base64.b64decode(h[6:]).decode().partition(":")[2] if h.startswith("Basic ") else ""
            except (ValueError, UnicodeDecodeError):
                given = ""
            if hmac.compare_digest(given.encode(), pw.encode()):
                return True
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Handover RCO", charset="UTF-8"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False

        def _handle(self, fn) -> None:
            try:
                fn()
            except WebError as e:
                self._json(e.status, {"error": str(e)})
            except Exception:
                log.exception("Error di %s %s", self.command, app.scrub(self.path))
                self._json(500, {"error": "Terjadi error di server. Cek log container web."})

        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path == "/healthz":
                return self._json(200, {"ok": True})
            if not self._authorized():
                return
            qs = parse_qs(url.query)

            def run():
                if url.path in ("/", "/index.html"):
                    return self._static("index.html")
                if url.path.startswith("/static/"):
                    return self._static(url.path.removeprefix("/static/"))
                if url.path == "/api/config":
                    return self._json(200, app.config())
                if url.path == "/api/issues":
                    return self._json(200, app.issues_payload(
                        qs.get("start", [None])[0], qs.get("end", [None])[0], qs.get("refresh", ["0"])[0] == "1"))
                raise WebError("Tidak ditemukan", 404)

            self._handle(run)

        do_HEAD = do_GET

        def do_POST(self) -> None:
            if not self._authorized():
                return

            def run():
                # Wajib JSON: form lintas situs tidak bisa mengirim application/json tanpa izin CORS.
                if not self.headers.get("Content-Type", "").startswith("application/json"):
                    raise WebError("Content-Type harus application/json", 415)
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    raise WebError("Request terlalu besar", 413)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    raise WebError("JSON tidak valid") from None
                if not isinstance(body, dict):
                    raise WebError("JSON harus berupa object")
                path = urlparse(self.path).path
                if path == "/api/preview":
                    return self._json(200, {"messages": app.messages(body), "chat": app.chat_info()})
                if path == "/api/send":
                    return self._json(200, app.send(body))
                raise WebError("Tidak ditemukan", 404)

            self._handle(run)

    return Handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = WebSettings()
    if settings.host not in ("127.0.0.1", "localhost") and not settings.password:
        log.warning("WEB_PASSWORD kosong: pastikan port web tidak terbuka ke jaringan (lihat web/README.md)")
    server = ThreadingHTTPServer((settings.host, settings.port), make_handler(HandoverWeb(settings)))
    server.daemon_threads = True
    log.info("Web Handover siap di http://%s:%d (sumber: %s)", settings.host, settings.port,
             settings.bot.source_type)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
