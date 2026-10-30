"""Baca file Excel (.xlsx) lokal: nilai + warna isi sel."""

from __future__ import annotations

import colorsys
import logging
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

import openpyxl
from openpyxl.styles.colors import COLOR_INDEX

from ..models import RGB, RawRow, RawSheet

log = logging.getLogger(__name__)

_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
# Urutan indeks warna theme di Excel: lt1, dk1, lt2, dk2, accent1-6, hlink, folHlink
_THEME_ORDER = ["lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3",
                "accent4", "accent5", "accent6", "hlink", "folHlink"]
_MAX_COL = 17


def _hex_to_rgb(h: str) -> RGB | None:
    h = h.strip()[-6:]
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def _theme_colors(wb) -> list[RGB]:
    if not wb.loaded_theme:
        return []
    root = ET.fromstring(wb.loaded_theme)
    scheme = root.find(f".//{_A}clrScheme")
    if scheme is None:
        return []
    by_name = {}
    for child in scheme:
        name = child.tag.replace(_A, "")
        node = child[0] if len(child) else None
        if node is None:
            continue
        val = node.get("lastClr") or node.get("val")
        if val:
            by_name[name] = _hex_to_rgb(val)
    return [by_name.get(n) for n in _THEME_ORDER]


def _apply_tint(rgb: RGB, tint: float) -> RGB:
    if not tint:
        return rgb
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
    return tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, l, s))  # type: ignore[return-value]


def _fill_rgb(cell, theme: list) -> RGB | None:
    fill = cell.fill
    if fill is None or fill.fill_type != "solid":
        return None
    color = fill.fgColor
    if color.type == "rgb" and isinstance(color.rgb, str):
        if color.rgb.upper() == "00000000":  # default openpyxl = tanpa warna
            return None
        return _hex_to_rgb(color.rgb)
    if color.type == "indexed" and color.indexed is not None and color.indexed < len(COLOR_INDEX):
        return _hex_to_rgb(COLOR_INDEX[color.indexed])
    if color.type == "theme" and color.theme is not None and color.theme < len(theme) and theme[color.theme]:
        return _apply_tint(theme[color.theme], color.tint or 0.0)
    return None


class XlsxSource:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._cache: tuple[float, list[RawSheet]] | None = None
        self._lock = threading.Lock()

    def _load(self) -> list[RawSheet]:
        if not self.path.exists():
            raise FileNotFoundError(f"File Excel tidak ditemukan: {self.path}")
        mtime = self.path.stat().st_mtime
        with self._lock:
            if self._cache and self._cache[0] == mtime:
                return self._cache[1]
            wb = openpyxl.load_workbook(self.path, data_only=True)
            theme = _theme_colors(wb)
            sheets = []
            for ws in wb.worksheets:
                rows = []
                for r_idx, row in enumerate(ws.iter_rows(max_col=_MAX_COL), start=1):
                    rows.append(
                        RawRow(
                            row_number=r_idx,
                            values=[c.value for c in row],
                            colors=[_fill_rgb(c, theme) for c in row],
                        )
                    )
                sheets.append(RawSheet(title=ws.title, rows=rows))
            log.info("Memuat %s: %d sheet", self.path.name, len(sheets))
            self._cache = (mtime, sheets)
            return sheets

    def list_titles(self) -> list[str]:
        return [s.title for s in self._load()]

    def fetch(self, titles: list[str]) -> list[RawSheet]:
        by_title = {s.title: s for s in self._load()}
        return [by_title[t] for t in titles if t in by_title]
