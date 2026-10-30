"""Logika versi web: ambil issue, link ke sheet, susun & kirim pesan Telegram.

Klasifikasi dan format pesan sama persis dengan bot (handover_bot.service + handover_bot.report).
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

from handover_bot.commands import Query
from handover_bot.models import TEAMS, Category, Issue
from handover_bot.report import build_messages
from handover_bot.service import collect_issues
from handover_bot.sources import make_source
from handover_bot.sources.apps_script import AppsScriptError
from handover_bot.sources.google_sheets import GoogleAuthError

from . import __version__
from .config import WebSettings

log = logging.getLogger(__name__)

CACHE_SECONDS = 60
GID_CACHE_SECONDS = 600
MAX_DAYS = 400
# Daftar tab di halaman htmlview spreadsheet publik: {name: "Issue Oktober 2026", pageUrl: "...", gid: "352493838"
_GID_RE = re.compile(r'name: "((?:[^"\\]|\\.)*)", pageUrl: "[^"]*", gid: "(\d+)"')


class WebError(Exception):
    """Error yang pesannya aman ditampilkan ke user."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def issue_key(i: Issue) -> str:
    return f"{i.sheet}#{i.issue_no}"


def parse_range(start: str | None, end: str | None) -> tuple[date, date]:
    try:
        s, e = date.fromisoformat(start or ""), date.fromisoformat(end or "")
    except ValueError:
        raise WebError("Tanggal tidak valid (format YYYY-MM-DD)") from None
    if e < s:
        raise WebError("Tanggal akhir lebih awal dari tanggal mulai")
    if (e - s).days > MAX_DAYS:
        raise WebError(f"Rentang maksimal {MAX_DAYS} hari")
    return s, e


def _unescape_js(s: str) -> str:
    s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)
    return re.sub(r"\\(.)", r"\1", s)


class HandoverWeb:
    def __init__(self, settings: WebSettings, source=None, http=requests):
        self.settings = settings
        self.bot = settings.bot
        self.tz = ZoneInfo(self.bot.timezone)
        self.http = http
        self._source = source
        self._lock = threading.Lock()
        self._cache: dict[tuple[date, date], tuple[float, list[Issue], list[str]]] = {}
        self._gids: tuple[float, dict[str, str]] | None = None
        self._chat_title: str | None = None

    @property
    def source(self):
        if self._source is None:
            self._source = make_source(self.bot)
        return self._source

    def scrub(self, text: str) -> str:
        """Buang token/key dari pesan error sebelum ditampilkan atau dicatat."""
        for secret in (self.bot.apps_script_key, self.bot.telegram_token, self.settings.password):
            if secret:
                text = text.replace(secret, "***")
        return text

    # ---------- data ----------

    def load(self, start: date, end: date, refresh: bool = False) -> tuple[float, list[Issue], list[str]]:
        with self._lock:
            hit = self._cache.get((start, end))
        if hit and not refresh and time.time() - hit[0] < CACHE_SECONDS:
            return hit
        try:
            issues, warnings = collect_issues(self.source, Query(start, end, list(Category)))
        except (AppsScriptError, GoogleAuthError, FileNotFoundError) as e:
            raise WebError(f"Akses spreadsheet bermasalah: {self.scrub(str(e))}", 502) from None
        entry = (time.time(), issues, warnings)
        with self._lock:
            self._cache[(start, end)] = entry
        return entry

    def sheet_gids(self) -> dict[str, str]:
        if self._gids and time.time() - self._gids[0] < GID_CACHE_SECONDS:
            return self._gids[1]
        url = f"https://docs.google.com/spreadsheets/d/{self.settings.transit_spreadsheet_id}/htmlview"
        try:
            r = self.http.get(url, timeout=20)
            r.raise_for_status()
            gids = {_unescape_js(n): g for n, g in _GID_RE.findall(r.text)}
            self._gids = (time.time(), gids)
        except requests.RequestException as e:
            log.warning("Daftar tab transit tidak bisa dibaca: %s", e)
            gids = self._gids[1] if self._gids else {}
            # Coba lagi 1 menit lagi, bukan 10 menit.
            self._gids = (time.time() - GID_CACHE_SECONDS + 60, gids)
        return gids

    def sheet_url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.settings.transit_spreadsheet_id}/edit"

    def row_link(self, sheet: str, row: int, gids: dict[str, str]) -> str:
        gid = gids.get(sheet)
        return f"{self.sheet_url()}#gid={gid}&range=A{row}" if gid else self.sheet_url()

    def issues_payload(self, start: str | None, end: str | None, refresh: bool = False) -> dict:
        s, e = parse_range(start, end)
        fetched, issues, warnings = self.load(s, e, refresh)
        gids = self.sheet_gids()
        return {
            "start": s.isoformat(),
            "end": e.isoformat(),
            "fetched_at": datetime.fromtimestamp(fetched, self.tz).isoformat(timespec="seconds"),
            "warnings": warnings,
            "issues": [{
                "key": issue_key(i),
                "sheet": i.sheet,
                "issue_no": i.issue_no,
                "tanggal": i.tanggal.isoformat(),
                "team": i.team,
                "aplikasi": i.aplikasi,
                "status": i.status,
                "pic": i.pic,
                "label": i.label,
                "category": i.category.value,
                "done_reason": i.done_reason,
                "waiting_external": i.waiting_external,
                "link": self.row_link(i.sheet, i.issue_no, gids),
            } for i in issues],
        }

    # ---------- pesan ----------

    def messages(self, body: dict) -> list[str]:
        s, e = parse_range(body.get("start"), body.get("end"))
        try:
            wanted = {Category(c) for c in body.get("categories") or []}
        except ValueError:
            raise WebError("Kategori tidak dikenal") from None
        cats = [c for c in Category if c in wanted]
        if not cats:
            raise WebError("Pilih minimal satu kategori")
        teams = [t for t in TEAMS if t in (body.get("teams") or TEAMS)]
        if not teams:
            raise WebError("Pilih minimal satu tim")

        query = Query(s, e, cats, detail=bool(body.get("detail")), split=bool(body.get("split")),
                      teams=None if len(teams) == len(TEAMS) else teams)
        _, issues, warnings = self.load(s, e)
        issues = [i for i in issues if i.team in teams]
        keys = body.get("keys")
        if keys is not None:
            # Hanya baris yang sedang tampil di tabel (hasil pencarian / filter lain di browser).
            keyset = set(map(str, keys))
            issues = [i for i in issues if issue_key(i) in keyset]
        return build_messages(issues, query, self.bot.report_title, warnings)

    def chat_info(self) -> dict | None:
        chat_id = self.settings.target_chat_id
        if chat_id is None or not self.bot.telegram_token:
            return None
        if self._chat_title is None:
            try:
                r = self.http.get(f"https://api.telegram.org/bot{self.bot.telegram_token}/getChat",
                                  params={"chat_id": chat_id}, timeout=15)
                res = r.json().get("result") or {}
                self._chat_title = res.get("title") or res.get("username") or res.get("first_name") or ""
            except (requests.RequestException, ValueError):
                return {"id": chat_id, "title": ""}  # coba lagi di request berikutnya
        return {"id": chat_id, "title": self._chat_title}

    def send(self, body: dict) -> dict:
        chat = self.chat_info()
        if chat is None:
            raise WebError("Tujuan Telegram belum diatur (isi WEB_CHAT_ID atau ALLOWED_CHAT_IDS di .env)", 409)
        msgs = self.messages(body)
        url = f"https://api.telegram.org/bot{self.bot.telegram_token}/sendMessage"
        for n, text in enumerate(msgs, start=1):
            try:
                r = self.http.post(url, json={"chat_id": chat["id"], "text": text, "parse_mode": "HTML",
                                              "disable_web_page_preview": True}, timeout=30)
                data = r.json()
            except (requests.RequestException, ValueError):
                # Pesan exception requests memuat URL berisi token: jangan diteruskan.
                raise WebError(f"Gagal menghubungi Telegram (pesan {n}/{len(msgs)}). Coba lagi.", 502) from None
            if not data.get("ok"):
                raise WebError(f"Telegram menolak pesan {n}/{len(msgs)}: {data.get('description', '')}", 502)
        log.info("Web: %d pesan dikirim ke chat %s", len(msgs), chat["id"])
        return {"sent": len(msgs), "chat": chat}

    def config(self) -> dict:
        return {
            "version": __version__,
            "title": self.bot.report_title,
            "today": datetime.now(self.tz).date().isoformat(),
            "teams": TEAMS,
            "chat": self.chat_info(),
            "sheet_url": self.sheet_url(),
            "cache_seconds": CACHE_SECONDS,
        }
