"""Ambil issue sesuai Query dari sumber data."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, timedelta

from .commands import Query
from .dates import NAMA_BULAN, last_day_of_month, months_between
from .models import Issue
from .rules import DEFAULT_COLUMNS, build_issues, detect_columns
from .sources import Source, find_month_tab

log = logging.getLogger(__name__)


def collect_issues(source: Source, query: Query) -> tuple[list[Issue], list[str]]:
    """Kembalikan (issue dalam rentang tanggal, peringatan untuk user)."""
    warnings: list[str] = []
    titles = source.list_titles()

    wanted: list[str] = []
    months: dict[str, tuple[int, int]] = {}
    for year, month in months_between(query.start, query.end):
        tab = find_month_tab(titles, year, month)
        if tab:
            wanted.append(tab)
            months[tab] = (year, month)
        else:
            warnings.append(f"Tab 'Issue {NAMA_BULAN[month - 1]} {year}' tidak ditemukan")

    sheets = source.fetch(wanted)
    tab_months = [months[s.title] for s in sheets]
    detected = {s.title: detect_columns(s) for s in sheets}
    # Tab tanpa header memakai layout tab lain yang header-nya ketemu.
    fallback = replace(next((c for c in detected.values() if c), DEFAULT_COLUMNS), header_row=None)

    issues: list[Issue] = []
    for sheet, (year, month) in zip(sheets, tab_months):
        cols = detected[sheet.title] or fallback
        if detected[sheet.title] is None:
            log.warning("Header tidak ditemukan di %r, pakai layout %s", sheet.title, cols)
        sheet_issues = fix_typo_dates(build_issues(sheet, cols), year, month)
        issues.extend(i for i in sheet_issues if query.start <= i.tanggal <= query.end)
    return issues, warnings


def fix_typo_dates(issues: list[Issue], year: int, month: int, slack_days: int = 7) -> list[Issue]:
    """Tanggal yang jauh di luar bulan tab dianggap salah ketik.

    Bulan & hari sama tapi tahun beda -> tahun diganti tahun tab; selain itu pakai tanggal issue sebelumnya.
    """
    lo = date(year, month, 1) - timedelta(days=slack_days)
    hi = last_day_of_month(year, month) + timedelta(days=slack_days)
    prev = None
    for i in issues:
        if not lo <= i.tanggal <= hi:
            fixed = None
            if i.tanggal.month == month:
                try:
                    fixed = i.tanggal.replace(year=year)
                except ValueError:
                    fixed = None
            fixed = fixed or prev
            if fixed:
                log.info("%s Issue %d: tanggal %s dikoreksi ke %s", i.sheet, i.issue_no, i.tanggal, fixed)
                i.tanggal = fixed
        if lo <= i.tanggal <= hi:
            prev = i.tanggal
    return issues
