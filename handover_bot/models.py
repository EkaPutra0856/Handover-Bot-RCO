"""Struktur data bersama."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

TEAMS = ["Tim 1", "Tim 2", "Tim 3", "ALL TEAM"]

# Warna RGB 0-255, atau None kalau sel tidak berwarna.
RGB = tuple[int, int, int]


class Category(str, Enum):
    PENDING = "pending"    # Putih: belum disentuh
    PROGRESS = "progress"  # Kuning: sedang dikerjakan
    DONE = "done"          # Hijau / status selesai


@dataclass
class RawRow:
    """Satu baris mentah dari sumber (Google Sheets atau xlsx)."""

    row_number: int            # nomor baris fisik di sheet (1-based)
    values: list               # nilai sel berurutan dari kolom A
    colors: list[RGB | None]   # warna latar tiap sel, sejajar dengan `values`


@dataclass
class RawSheet:
    title: str
    rows: list[RawRow]


@dataclass
class Issue:
    sheet: str
    issue_no: int
    tanggal: date
    team: str
    aplikasi: str
    status: str
    pic: str
    category: Category
    done_reason: str = ""  # "status", "pic", atau "hijau"
    waiting_external: bool = False  # baris orange: menunggu tindak lanjut eksternal

    @property
    def label(self) -> str:
        """Nama PIC untuk ditampilkan; kalau PIC kosong, nama timnya."""
        return self.pic or self.team
