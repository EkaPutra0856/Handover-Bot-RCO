"""Baca spreadsheet lewat Apps Script Web App (apps_script/Code.gs) yang jalan sebagai pemilik akses."""

from __future__ import annotations

import json
import logging

import requests

from ..models import RGB, RawRow, RawSheet

log = logging.getLogger(__name__)
TIMEOUT = 60


class AppsScriptError(RuntimeError):
    pass


def _hex(color: str | None) -> RGB | None:
    if not color or not color.startswith("#") or len(color) != 7:
        return None
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    return None if rgb == (255, 255, 255) else rgb  # type: ignore[return-value]


class AppsScriptSource:
    def __init__(self, url: str, key: str):
        if not url or not key:
            raise AppsScriptError("APPS_SCRIPT_URL dan APPS_SCRIPT_KEY wajib diisi di .env")
        self.url, self.key = url, key

    def _call(self, **params) -> dict:
        try:
            resp = requests.get(self.url, params={"key": self.key, **params}, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            raise AppsScriptError(f"Gagal memanggil Apps Script: {e}") from e
        if not data.get("ok"):
            raise AppsScriptError(f"Apps Script menolak: {data.get('error')}")
        return data

    def list_titles(self) -> list[str]:
        return self._call(action="titles")["titles"]

    def fetch(self, titles: list[str]) -> list[RawSheet]:
        if not titles:
            return []
        data = self._call(action="fetch", tabs=json.dumps(titles))
        out = []
        for sh in data["sheets"]:
            bgs = sh.get("backgrounds") or []
            rows = [
                RawRow(
                    row_number=n,
                    values=[v if v != "" else None for v in vals],
                    colors=[_hex(c) for c in (bgs[n - 1] if n - 1 < len(bgs) else [])],
                )
                for n, vals in enumerate(sh["values"], start=1)
            ]
            log.info("Sheet %r: %d baris", sh["title"], len(rows))
            out.append(RawSheet(title=sh["title"], rows=rows))
        return out
