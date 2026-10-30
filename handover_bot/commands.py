"""Parse teks perintah Telegram menjadi Query rekap."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from .dates import last_day_of_month, month_number
from .models import Category


class CommandError(ValueError):
    """Perintah tidak bisa dipahami; pesannya ditampilkan ke user."""


@dataclass
class Query:
    start: date
    end: date
    categories: list[Category]
    detail: bool = False
    split: bool = False  # tiap kategori dikirim di bubble chat terpisah
    teams: list[str] | None = None  # None = semua tim (versi web bisa memilih tim)
    warnings: list[str] = field(default_factory=list)


# Perintah -> (kategori default, detail, split)
COMMANDS: dict[str, tuple[list[Category], bool, bool]] = {
    "rekap": ([Category.PENDING, Category.PROGRESS], False, False),
    "rekapdetail": ([Category.PENDING, Category.PROGRESS], True, False),
    "pending": ([Category.PENDING], False, False),
    "belum": ([Category.PENDING], False, False),
    "progress": ([Category.PROGRESS], False, False),
    "ongoing": ([Category.PROGRESS], False, False),
    "onprogress": ([Category.PROGRESS], False, False),
    "done": ([Category.DONE], False, False),
    "selesai": ([Category.DONE], False, False),
    "doneprogress": ([Category.DONE, Category.PROGRESS], False, True),
}

_CATEGORY_WORDS = {
    "pending": Category.PENDING, "belum": Category.PENDING, "putih": Category.PENDING,
    "progress": Category.PROGRESS, "ongoing": Category.PROGRESS, "kuning": Category.PROGRESS,
    "done": Category.DONE, "selesai": Category.DONE, "hijau": Category.DONE,
}

_RANGE_SEP = re.compile(r"\s*(?::|–|—|\bs/d\b|\bsd\b|\bsampai\b|\bhingga\b|\bto\b|\s-\s)\s*", re.I)
_DAY_SPAN = re.compile(r"^(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\.?(?:\s+(\d{4}))?$")


def parse_command(text: str, today: date) -> Query:
    text = (text or "").strip()
    m = re.match(r"^/(\w+)(?:@\w+)?\s*(.*)$", text, re.S)
    if not m:
        raise CommandError("Perintah harus diawali '/'. Ketik /help untuk panduan.")
    cmd, rest = m.group(1).lower(), m.group(2)
    if cmd not in COMMANDS:
        raise CommandError(f"Perintah /{cmd} tidak dikenal. Ketik /help untuk panduan.")

    categories, detail, split = COMMANDS[cmd]
    categories = list(categories)

    # Ambil kata kunci modifier, sisanya adalah periode.
    words, period_words, picked = rest.split(), [], []
    for w in words:
        lw = w.lower().strip(",")
        if lw == "detail":
            detail = True
        elif lw in ("pisah", "split"):
            split = True
        elif lw in _CATEGORY_WORDS:
            if _CATEGORY_WORDS[lw] not in picked:
                picked.append(_CATEGORY_WORDS[lw])
        else:
            period_words.append(w)
    if picked:
        categories = picked
        if len(picked) > 1:
            split = split or Category.DONE in picked

    start, end = parse_period(" ".join(period_words), today)
    return Query(start=start, end=end, categories=categories, detail=detail, split=split)


def parse_period(text: str, today: date) -> tuple[date, date]:
    s = " ".join(text.split()).strip()
    low = s.lower()
    if low in ("", "hari ini", "today"):
        return today, today
    if low in ("kemarin", "yesterday"):
        d = today - timedelta(days=1)
        return d, d
    if low == "minggu ini":
        return today - timedelta(days=today.weekday()), today
    if low == "bulan ini":
        return date(today.year, today.month, 1), last_day_of_month(today.year, today.month)
    if low == "bulan lalu":
        first = date(today.year, today.month, 1) - timedelta(days=1)
        return date(first.year, first.month, 1), first

    # "5-7 Oktober 2026"
    m = _DAY_SPAN.match(s)
    if m and month_number(m.group(3)):
        y = int(m.group(4)) if m.group(4) else today.year
        mon = month_number(m.group(3))
        return _ordered(_mk(y, mon, int(m.group(1))), _mk(y, mon, int(m.group(2))))

    parts = [p for p in _RANGE_SEP.split(s) if p.strip()]
    if len(parts) == 1:
        p = _parse_point(parts[0])
        y = p["y"] or today.year
        if p["m"] is None:
            raise CommandError(_bad_period(s))
        if p["d"] is None:  # bulan saja
            return date(y, p["m"], 1), last_day_of_month(y, p["m"])
        d = _mk(y, p["m"], p["d"])
        return d, d

    if len(parts) != 2:
        raise CommandError(_bad_period(s))

    a, b = _parse_point(parts[0]), _parse_point(parts[1])
    if b["m"] is None:
        raise CommandError(_bad_period(s))
    by = b["y"] or today.year
    am = a["m"] or b["m"]
    ay = a["y"] or (by - 1 if am > b["m"] else by)
    start = _mk(ay, am, a["d"] or 1)
    end = _mk(by, b["m"], b["d"] or last_day_of_month(by, b["m"]).day)
    return _ordered(start, end)


def _parse_point(s: str) -> dict:
    s = s.strip().rstrip(".")
    pats = [
        (r"^(\d{4})-(\d{1,2})-(\d{1,2})$", ("y", "m", "d")),
        (r"^(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?$", ("d", "m", "y")),
        (r"^(\d{1,2})\s+([A-Za-z]+)\.?(?:\s+(\d{2,4}))?$", ("d", "M", "y")),
        (r"^([A-Za-z]+)\.?(?:\s+(\d{4}))?$", ("M", "y")),
        (r"^(\d{1,2})$", ("d",)),
    ]
    for pat, keys in pats:
        m = re.match(pat, s)
        if not m:
            continue
        out = {"d": None, "m": None, "y": None}
        for k, v in zip(keys, m.groups()):
            if v is None:
                continue
            if k == "M":
                mon = month_number(v)
                if mon is None:
                    break
                out["m"] = mon
            else:
                n = int(v)
                out[k] = n + 2000 if k == "y" and n < 100 else n
        else:
            return out
    raise CommandError(_bad_period(s))


def _mk(y: int, m: int, d: int) -> date:
    try:
        return date(y, m, d)
    except ValueError:
        raise CommandError(f"Tanggal {d:02d}/{m:02d}/{y} tidak valid.") from None


def _ordered(a: date, b: date) -> tuple[date, date]:
    return (a, b) if a <= b else (b, a)


def _bad_period(s: str) -> str:
    return f"Periode '{s}' tidak dikenali. Contoh: /rekap Oktober 2026, /rekap 13/10/2026, /rekap 28 September 2026 : 2 Oktober 2026"
