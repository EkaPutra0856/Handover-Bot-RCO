"""Utilitas tanggal berbahasa Indonesia."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

NAMA_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

# Nama lengkap, singkatan Indonesia, dan singkatan Inggris -> nomor bulan (1-12)
_BULAN_ALIAS = {
    "januari": 1, "jan": 1, "january": 1,
    "februari": 2, "feb": 2, "pebruari": 2, "february": 2,
    "maret": 3, "mar": 3, "march": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "jun": 6, "june": 6,
    "juli": 7, "jul": 7, "july": 7,
    "agustus": 8, "agu": 8, "agt": 8, "ags": 8, "agst": 8, "agus": 8, "aug": 8, "august": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "oct": 10, "october": 10,
    "november": 11, "nov": 11, "nop": 11,
    "desember": 12, "des": 12, "dec": 12, "december": 12,
}

# Serial tanggal Google Sheets / Excel dihitung dari 30 Desember 1899.
_SERIAL_EPOCH = date(1899, 12, 30)


def month_number(name: str) -> int | None:
    return _BULAN_ALIAS.get(name.strip().lower().rstrip("."))


def fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def fmt_range(start: date, end: date) -> str:
    return fmt(start) if start == end else f"{fmt(start)} - {fmt(end)}"


def last_day_of_month(year: int, month: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def months_between(start: date, end: date) -> list[tuple[int, int]]:
    """Daftar (tahun, bulan) dari bulan `start` sampai bulan `end`, inklusif."""
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def from_serial(serial: float) -> date | None:
    # Rentang wajar saja: serial 1 (1899) sampai ~tahun 2200.
    if not 1 <= serial < 110000:
        return None
    return _SERIAL_EPOCH + timedelta(days=int(serial))


_RE_TEXT = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{2,4})")
_RE_NUMERIC = re.compile(r"^(\d{1,4})[/\-.](\d{1,2})[/\-.](\d{1,4})")


def parse_cell_date(value) -> date | None:
    """Parse isi sel kolom Tanggal: datetime, serial angka, atau teks DD/MM/YYYY / '1 Oktober 2026'."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date() if value.year > 1900 else None
    if isinstance(value, date):
        return value if value.year > 1900 else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return from_serial(float(value))

    s = str(value).strip()
    if not s or "1899" in s:
        return None
    # Buang nama hari di depan: "Rabu, 1 Oktober 2026"
    s = re.sub(r"^[A-Za-z]+,\s*", "", s)

    m = _RE_TEXT.match(s)
    if m:
        mon = month_number(m.group(2))
        if mon:
            return _safe_date(_year(m.group(3)), mon, int(m.group(1)))

    m = _RE_NUMERIC.match(s)
    if m:
        a, b, c = m.groups()
        if len(a) == 4:  # YYYY-MM-DD
            return _safe_date(int(a), int(b), int(c))
        return _safe_date(_year(c), int(b), int(a))  # DD/MM/YYYY (format Indonesia)
    return None


def _year(s: str) -> int:
    y = int(s)
    return y + 2000 if y < 100 else y


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None
