from datetime import date, datetime

import pytest

from handover_bot.dates import parse_cell_date
from handover_bot.models import Category, RawRow, RawSheet
from handover_bot.rules import ColumnMap, build_issues, is_green, parse_team, sanitize_pic


def test_legend_colors():
    cols = ColumnMap(tanggal=0, aplikasi=None, team=None, pelapor=1, status=2, pic=3)
    y, o, g = (255, 255, 0), (255, 153, 0), (0, 255, 0)
    rows = [
        RawRow(1, ["2026-10-01", "1 ~a", None, None], [None] * 4),       # putih kosong -> pending
        RawRow(2, ["2026-10-01", "1 ~a", None, None], [y] * 4),          # kuning tanpa PIC -> progress
        RawRow(3, ["2026-10-01", "1 ~a", "oncek", "Bias"], [o] * 4),     # orange -> progress, eksternal
        RawRow(4, ["2026-10-01", "1 ~a", "oncek", "Bias"], [g] + [None] * 3),  # hijau -> done
        RawRow(5, ["2026-10-01", "1 ~a", "pending", None], [None] * 4),  # status "pending" -> pending
    ]
    out = {i.issue_no: i for i in build_issues(RawSheet("t", rows), cols)}
    assert out[1].category == Category.PENDING
    assert out[2].category == Category.PROGRESS and not out[2].waiting_external
    assert out[3].category == Category.PROGRESS and out[3].waiting_external
    assert out[4].category == Category.DONE
    assert out[5].category == Category.PENDING


@pytest.mark.parametrize("rgb, green", [
    ((183, 225, 205), True),   # #b7e1cd
    ((217, 234, 211), True),   # #d9ead3 light green 3
    ((0, 255, 0), True),
    ((106, 168, 79), True),    # #6aa84f
    ((39, 78, 19), True),      # #274e13
    ((143, 206, 0), True),     # #8fce00
    ((255, 255, 255), False),
    ((255, 255, 0), False),    # kuning
    ((255, 242, 204), False),  # kuning muda
    ((0, 255, 255), False),    # cyan
    ((217, 217, 217), False),  # abu-abu
    (None, False),
])
def test_is_green(rgb, green):
    assert is_green(rgb) is green


@pytest.mark.parametrize("team, pelapor, expected", [
    (None, "1 ~Aldi Pratama", "Tim 1"),
    (None, "2 ~Putri", "Tim 2"),
    (None, "3 temuan", "Tim 3"),
    (None, 2.0, "Tim 2"),
    (None, "1.0", "Tim 1"),
    (None, "Tim 3 - Budi", "Tim 3"),
    (None, "Aldi ~1", "Tim 1"),
    (None, "62 811-1122-993 ~Aldi", "ALL TEAM"),
    (None, "12 orang", "ALL TEAM"),
    (None, "IT Service Desk BRI", "ALL TEAM"),
    ("2", "1 ~Aldi", "Tim 2"),
    ("All", "1 ~Aldi", "ALL TEAM"),     # kolom TEAM terisi -> tidak menebak dari pelapor
    ("3", "temuan", "Tim 3"),
    ("", "2 ~Putri", "Tim 2"),
])
def test_parse_team(team, pelapor, expected):
    assert parse_team(team, pelapor) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Hendrik", "Hendrik"),
    ("  reynal ", "reynal"),
    ("select * from tbl", ""),
    ("172.18.141.71", ""),
    ("https://bridrive/x", ""),
    ("D:\\backup\\db.mdf", ""),
    ("baris\nbaru", ""),
    ("nama yang sangat panjang sekali lebih dari 25", ""),
    ("-", ""),
    ("done", ""),
    ("30/12/1899", ""),
    (None, ""),
    (12.5, ""),
])
def test_sanitize_pic(raw, expected):
    assert sanitize_pic(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    (datetime(2026, 10, 1, 8, 0), date(2026, 10, 1)),
    (46296, date(2026, 10, 1)),          # serial Google Sheets
    ("01/10/2026", date(2026, 10, 1)),
    ("1/10/26", date(2026, 10, 1)),
    ("1 Oktober 2026", date(2026, 10, 1)),
    ("Kamis, 1 Okt 2026", date(2026, 10, 1)),
    ("2026-10-01", date(2026, 10, 1)),
    ("Tanggal", None),
    ("30/12/1899", None),
    ("", None),
    (None, None),
])
def test_parse_cell_date(raw, expected):
    assert parse_cell_date(raw) == expected
