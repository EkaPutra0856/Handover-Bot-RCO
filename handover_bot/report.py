"""Susun pesan rekap Telegram (HTML)."""

from __future__ import annotations

from html import escape

from .commands import Query
from .dates import fmt, fmt_range
from .models import TEAMS, Category, Issue

# Batas Telegram 4096 karakter setelah parsing HTML; sisakan ruang untuk tag & penanda part.
MAX_LEN = 3800
SEPARATOR = "------------------------------------"

_HEADINGS = {
    Category.PENDING: "📌 <b>Pendingan Issue (Belum Dikerjakan):</b>",
    Category.PROGRESS: "⏳ <b>Issue On Progress (Kuning):</b>",
    Category.DONE: "✅ <b>Issue Done (Hijau):</b>",
}
_EMPTY = {
    Category.PENDING: "<i>Tidak ada issue pending</i>",
    Category.PROGRESS: "<i>Tidak ada issue on progress</i>",
    Category.DONE: "<i>Tidak ada issue done</i>",
}
_TOTALS = {
    Category.PENDING: "Total Pending: {} Issue (Putih)",
    Category.PROGRESS: "Total On Progress: {} Issue (Kuning)",
    Category.DONE: "Total Done: {} Issue (Hijau)",
}
_CLOSING = ["Mohon bantuannya untuk ditelusuri rekan-rekan engineer", "Terima kasih."]


def _app(issue: Issue, detail: bool) -> str:
    return f" — {escape(issue.aplikasi)}" if detail and issue.aplikasi else ""


def _section(cat: Category, issues: list[Issue], detail: bool, teams: list[str] | None = None) -> list[str]:
    lines = [_HEADINGS[cat], ""]
    items = [i for i in issues if i.category == cat]
    if not items:
        return lines + [_EMPTY[cat], ""]

    if cat == Category.PENDING:
        for team in teams or TEAMS:
            team_items = sorted((i for i in items if i.team == team), key=lambda i: (i.tanggal, i.issue_no))
            # Tim 1-3 selalu tampil supaya jelas tim yang kosong memang tidak punya pendingan.
            if not team_items and team == "ALL TEAM" and not teams:
                continue
            lines.append(f"<b>{team}</b>")
            lines += [f"{fmt(i.tanggal)} — Issue {i.issue_no}{_app(i, detail)}" for i in team_items]
            if not team_items:
                lines.append("<i>Tidak ada pendingan</i>")
            lines.append("")
    else:
        order = {t: n for n, t in enumerate(TEAMS)}
        for i in sorted(items, key=lambda i: (order[i.team], i.tanggal, i.issue_no)):
            wait = " 🟠 <i>(menunggu eksternal)</i>" if i.waiting_external else ""
            lines.append(f"{fmt(i.tanggal)} — {i.team} — Issue {i.issue_no}{_app(i, detail)} — {escape(i.label)}{wait}")
        lines.append("")
    return lines


def _header(query: Query, title: str, warnings: list[str]) -> list[str]:
    if query.detail:
        title = title.replace(" – ", " (Detail) – ", 1) if " – " in title else f"{title} (Detail)"
    lines = [f"<b>{escape(title)}</b>", "", fmt_range(query.start, query.end), ""]
    for w in warnings:
        lines.append(f"⚠️ <i>{escape(w)}</i>")
    if warnings:
        lines.append("")
    return lines


def _footer(query: Query, issues: list[Issue], cats: list[Category], grand_total: bool) -> list[str]:
    lines = [SEPARATOR]
    for cat in cats:
        lines.append(_TOTALS[cat].format(sum(1 for i in issues if i.category == cat)))
    if grand_total and len(query.categories) > 1:
        total = sum(1 for i in issues if i.category in query.categories)
        lines.append(f"Total Keseluruhan: {total} Issue")
    if grand_total and any(c in query.categories for c in (Category.PENDING, Category.PROGRESS)):
        lines += [""] + _CLOSING
    return lines


def build_messages(issues: list[Issue], query: Query, title: str, warnings: list[str] | None = None) -> list[str]:
    """Kembalikan daftar pesan siap kirim (sudah dipecah sesuai batas Telegram)."""
    warnings = warnings or []
    if not query.split or len(query.categories) == 1:
        lines = _header(query, title, warnings)
        for cat in query.categories:
            lines += _section(cat, issues, query.detail, query.teams)
        lines += _footer(query, issues, query.categories, grand_total=True)
        return chunk(lines)

    messages: list[str] = []
    for n, cat in enumerate(query.categories):
        last = n == len(query.categories) - 1
        lines = _header(query, title, warnings if n == 0 else [])
        lines += _section(cat, issues, query.detail, query.teams)
        lines += _footer(query, issues, [cat], grand_total=last)
        messages += chunk(lines)
    return messages


def chunk(lines: list[str], limit: int = MAX_LEN) -> list[str]:
    """Pecah per baris utuh supaya tag HTML tidak terpotong."""
    parts: list[str] = []
    cur = ""
    for line in lines:
        candidate = f"{cur}\n{line}" if cur else line
        if len(candidate) > limit and cur.strip():
            parts.append(cur.strip())
            cur = line
        else:
            cur = candidate
    if cur.strip():
        parts.append(cur.strip())
    if len(parts) > 1:
        parts = [f"{p}\n\n<i>(Part {i}/{len(parts)})</i>" for i, p in enumerate(parts, start=1)]
    return parts


def help_text() -> str:
    return "\n".join([
        "📖 <b>Panduan Bot Handover</b>",
        "",
        "<b>Perintah</b>",
        "/rekap — pending + on progress",
        "/pending — hanya yang belum tersentuh (putih)",
        "/progress — hanya yang masih on going (kuning)",
        "/done — hanya yang sudah selesai (hijau)",
        "/doneprogress — done &amp; on progress, 2 bubble chat",
        "/rekapdetail — rekap + nama aplikasi",
        "/id — tampilkan chat id",
        "",
        "<b>Periode</b> (bisa dipakai di semua perintah)",
        "<code>/rekap</code> — hari ini",
        "<code>/rekap kemarin</code> | <code>minggu ini</code> | <code>bulan ini</code>",
        "<code>/rekap Oktober</code> atau <code>/rekap Oktober 2026</code>",
        "<code>/rekap 13 Oktober 2026</code> atau <code>/rekap 13/10/2026</code>",
        "<code>/rekap 5 Oktober 2026 : 7 Oktober 2026</code>",
        "<code>/rekap 5-7 Oktober 2026</code>",
        "<code>/rekap 28 September 2026 : 2 Oktober 2026</code> (lintas bulan)",
        "<code>/rekap September : November 2026</code>",
        "",
        "<b>Tambahan</b>",
        "<code>detail</code> — tampilkan nama aplikasi, mis. <code>/pending Oktober detail</code>",
        "<code>pisah</code> — tiap kategori di bubble terpisah, mis. <code>/rekap Oktober pisah</code>",
        "<code>pending progress done</code> — pilih kategori, mis. <code>/rekap done pending Oktober</code>",
    ])
