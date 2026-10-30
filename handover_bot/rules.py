"""Aturan bisnis: pemetaan kolom, deteksi hijau, tim, sanitasi PIC, klasifikasi issue."""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass

from .dates import parse_cell_date
from .models import RGB, Category, Issue, RawSheet

_DONE_RE = re.compile(r"\b(done|close|closed|solved|selesai)\b", re.I)
_PIC_JUNK_RE = re.compile(
    r"select|update|delete|insert|http|bridrive|^\d{1,3}\.\d|d:\\|\.mdf|\.ldf|\bfrom\b|\bwhere\b|--",
    re.I,
)
_EMPTY_MARKERS = {"", "-", "--", "—", "tanpa pic", "n/a", "na", "pending"}


@dataclass(frozen=True)
class ColumnMap:
    tanggal: int
    aplikasi: int | None
    team: int | None      # None kalau tim menyatu di kolom pelapor
    pelapor: int | None
    status: int
    pic: int
    header_row: int | None = None  # nomor baris header fisik, None kalau tidak ketemu


# Layout sheet sumber kalau baris header tidak ditemukan (16 kolom, A-P):
# A Tanggal, B ISSUE, C Aplikasi, D Pelapor ("1 ~Nama"), ..., I Status, J Pic
DEFAULT_COLUMNS = ColumnMap(tanggal=0, aplikasi=2, team=None, pelapor=3, status=8, pic=9)

_HEADER_ALIASES = {
    "tanggal": {"tanggal", "tanggal lapor", "tgl", "tgl lapor", "date"},
    "aplikasi": {"aplikasi", "app", "apps", "aplikasi/modul"},
    "team": {"team", "tim"},
    "pelapor": {"pelapor"},
    "status": {"status"},
    "pic": {"pic"},
}


def _norm(v) -> str:
    return " ".join(str(v).split()).strip().lower() if v is not None else ""


def detect_columns(sheet: RawSheet, scan_rows: int = 6) -> ColumnMap | None:
    """Cari baris header (berisi 'Status' dan 'Pic') di beberapa baris teratas."""
    for row in sheet.rows[:scan_rows]:
        names = [_norm(v) for v in row.values]
        found: dict[str, int] = {}
        for idx, name in enumerate(names):
            for key, aliases in _HEADER_ALIASES.items():
                if name in aliases and key not in found:
                    found[key] = idx
        if "status" in found and "pic" in found:
            return ColumnMap(
                tanggal=found.get("tanggal", 0),
                aplikasi=found.get("aplikasi"),
                team=found.get("team"),
                pelapor=found.get("pelapor"),
                status=found["status"],
                pic=found["pic"],
                header_row=row.row_number,
            )
    return None


def _hue_in(rgb: RGB | None, lo: float, hi: float, min_sat: float) -> bool:
    if rgb is None:
        return False
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return lo <= h * 360 < hi and s >= min_sat and v >= 0.2


# Legenda di sheet: hijau = kelar, kuning = lagi dipegang, putih = kerjain,
# orange = menunggu tindak lanjut eksternal.
def is_green(rgb: RGB | None) -> bool:
    """Warna latar dianggap hijau kalau hue-nya di rentang hijau dan tidak abu-abu/putih."""
    return _hue_in(rgb, 70, 165, 0.08)


def is_yellow(rgb: RGB | None) -> bool:
    return _hue_in(rgb, 45, 70, 0.15)


def is_orange(rgb: RGB | None) -> bool:
    return _hue_in(rgb, 15, 45, 0.3)


def parse_team(team_val, pelapor_val) -> str:
    # Kolom TEAM yang terisi (termasuk "All") menentukan; pelapor hanya dipakai kalau TEAM kosong.
    sources = (team_val,) if team_val not in (None, "") else (pelapor_val,)
    for v in sources:
        if v is None or v == "":
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if int(v) in (1, 2, 3) and float(v) == int(v):
                return f"Tim {int(v)}"
            continue
        s = _norm(v)
        m = (
            re.match(r"^(?:tim|team)?\s*([123])(?:\.0+)?(?!\d)", s)
            or re.search(r"\b(?:tim|team)\s*([123])(?!\d)", s)
            or re.search(r"~\s*([123])(?!\d)", s)
        )
        if m:
            return f"Tim {m.group(1)}"
    return "ALL TEAM"


def clean_status(v) -> str:
    if v is None or not isinstance(v, str):
        return ""  # angka/tanggal/jam di kolom status bukan status
    s = re.sub(r"\d{1,2}/\d{1,2}/1899", "", v).strip()
    return "" if s.lower() in _EMPTY_MARKERS else s


def sanitize_pic(v) -> str:
    """Nama PIC yang aman ditampilkan; catatan teknis/SQL/IP/path dibuang."""
    if v is None or not isinstance(v, str):
        return ""
    s = re.sub(r"\d{1,2}/\d{1,2}/1899", "", v).strip()
    if not s or len(s) > 25 or "\n" in s or "\r" in s:
        return ""
    if _PIC_JUNK_RE.search(s) or s.lower() in _EMPTY_MARKERS or _DONE_RE.fullmatch(s):
        return ""
    return s


def safe_label(s: str) -> str:
    """Teks status untuk ditampilkan sebagai pengganti PIC."""
    if not s or len(s) > 25 or "\n" in s or _PIC_JUNK_RE.search(s):
        return ""
    return s


def clean_app(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if "\n" in s or len(s) > 40 else s


def _cell(values: list, idx: int | None):
    if idx is None or idx >= len(values):
        return None
    return values[idx]


def build_issues(sheet: RawSheet, cols: ColumnMap, green_scan_cols: int = 17) -> list[Issue]:
    issues: list[Issue] = []
    last_date = None
    for row in sheet.rows:
        if cols.header_row and row.row_number <= cols.header_row:
            continue
        tanggal = parse_cell_date(_cell(row.values, cols.tanggal))
        if tanggal is None:
            # Baris berisi issue tapi tanggalnya lupa diisi: pakai tanggal baris sebelumnya.
            raw_date = _cell(row.values, cols.tanggal)
            has_issue = any(
                isinstance(v, str) and v.strip() or isinstance(v, (int, float)) and not isinstance(v, bool)
                for i, v in enumerate(row.values[:cols.pic + 1]) if i != cols.tanggal
            )
            if last_date is None or not has_issue or (isinstance(raw_date, str) and raw_date.strip().lower() == "tanggal"):
                continue
            tanggal = last_date
        last_date = tanggal

        status = clean_status(_cell(row.values, cols.status))
        pic_raw = _cell(row.values, cols.pic)
        pic = sanitize_pic(pic_raw)
        colors = row.colors[:green_scan_cols]
        green = any(is_green(c) for c in colors)
        orange = any(is_orange(c) for c in colors)
        yellow = any(is_yellow(c) for c in colors)

        done_reason = ""
        if _DONE_RE.search(status):
            done_reason = "status"
        elif isinstance(pic_raw, str) and _DONE_RE.search(pic_raw):
            done_reason = "pic"
        elif green:
            done_reason = "hijau"

        if done_reason:
            category = Category.DONE
        elif not pic and not status and not (yellow or orange):
            category = Category.PENDING
        else:
            category = Category.PROGRESS

        issues.append(
            Issue(
                sheet=sheet.title,
                issue_no=row.row_number,
                tanggal=tanggal,
                team=parse_team(_cell(row.values, cols.team), _cell(row.values, cols.pelapor)),
                aplikasi=clean_app(_cell(row.values, cols.aplikasi)),
                status=safe_label(status),
                pic=pic,
                category=category,
                done_reason=done_reason,
                waiting_external=orange and category == Category.PROGRESS,
            )
        )
    return issues
