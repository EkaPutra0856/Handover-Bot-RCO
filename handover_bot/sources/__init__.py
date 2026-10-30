"""Sumber data spreadsheet."""

from __future__ import annotations

import re
from typing import Protocol

from ..config import Settings
from ..dates import month_number
from ..models import RawSheet


class Source(Protocol):
    def list_titles(self) -> list[str]: ...

    def fetch(self, titles: list[str]) -> list[RawSheet]: ...


_TAB_RE = re.compile(r"^\s*issue[\s_]+([A-Za-z]+)\.?[\s_]+(\d{2}|\d{4})\s*$", re.I)


def find_month_tab(titles: list[str], year: int, month: int) -> str | None:
    """Cari tab bulanan: 'Issue Oktober 2026', 'Issue_Jan_2026', 'Issue Ags 25', ' Issue Mei 25', dst."""
    for t in titles:
        m = _TAB_RE.match(t)
        if not m:
            continue
        y = int(m.group(2))
        y = y + 2000 if y < 100 else y
        if y == year and month_number(m.group(1)) == month:
            return t
    return None


def make_source(settings: Settings) -> Source:
    if settings.source_type == "xlsx":
        from .xlsx import XlsxSource

        return XlsxSource(settings.xlsx_path)
    if settings.source_type == "appscript":
        from .apps_script import AppsScriptSource

        return AppsScriptSource(settings.apps_script_url, settings.apps_script_key)
    if settings.source_type == "google":
        from .google_sheets import GoogleSheetSource

        return GoogleSheetSource(settings)
    raise ValueError(
        f"SOURCE_TYPE tidak dikenal: {settings.source_type!r} (pakai 'appscript', 'google', atau 'xlsx')"
    )
