from datetime import date

import pytest

from handover_bot.commands import CommandError, parse_command, parse_period
from handover_bot.models import Category

TODAY = date(2026, 10, 29)


@pytest.mark.parametrize("text, expected", [
    ("", (date(2026, 10, 29), date(2026, 10, 29))),
    ("kemarin", (date(2026, 10, 28), date(2026, 10, 28))),
    ("bulan ini", (date(2026, 10, 1), date(2026, 10, 31))),
    ("Oktober", (date(2026, 10, 1), date(2026, 10, 31))),
    ("februari 2028", (date(2028, 2, 1), date(2028, 2, 29))),
    ("13 Oktober 2026", (date(2026, 10, 13), date(2026, 10, 13))),
    ("13/10/2026", (date(2026, 10, 13), date(2026, 10, 13))),
    ("13-10-2026", (date(2026, 10, 13), date(2026, 10, 13))),
    ("5 Oktober 2026 : 7 Oktober 2026", (date(2026, 10, 5), date(2026, 10, 7))),
    ("05/10/2026 : 07/10/2026", (date(2026, 10, 5), date(2026, 10, 7))),
    ("28 September 2026 : 2 Oktober 2026", (date(2026, 9, 28), date(2026, 10, 2))),
    ("28 September s/d 2 Oktober 2026", (date(2026, 9, 28), date(2026, 10, 2))),
    ("28 Des 2025 - 3 Jan 2026", (date(2025, 12, 28), date(2026, 1, 3))),
    ("28 Desember : 3 Januari 2026", (date(2025, 12, 28), date(2026, 1, 3))),
    ("5-7 Oktober 2026", (date(2026, 10, 5), date(2026, 10, 7))),
    ("5 : 7 Oktober 2026", (date(2026, 10, 5), date(2026, 10, 7))),
    ("September : November 2026", (date(2026, 9, 1), date(2026, 11, 30))),
    ("7 Oktober 2026 : 5 Oktober 2026", (date(2026, 10, 5), date(2026, 10, 7))),
])
def test_parse_period(text, expected):
    assert parse_period(text, TODAY) == expected


@pytest.mark.parametrize("text", ["besok lusa", "32 Oktober 2026", "Oktober : Foo", "1 2 3"])
def test_parse_period_invalid(text):
    with pytest.raises(CommandError):
        parse_period(text, TODAY)


def test_commands_categories_and_flags():
    q = parse_command("/rekap Oktober", TODAY)
    assert q.categories == [Category.PENDING, Category.PROGRESS] and not q.detail and not q.split

    q = parse_command("/rekapdetail@HandoverBot Oktober 2026", TODAY)
    assert q.detail and q.start == date(2026, 10, 1)

    q = parse_command("/pending 13 Oktober 2026 detail", TODAY)
    assert q.categories == [Category.PENDING] and q.detail and q.start == date(2026, 10, 13)

    assert parse_command("/progress", TODAY).categories == [Category.PROGRESS]
    assert parse_command("/done Oktober", TODAY).categories == [Category.DONE]

    q = parse_command("/doneprogress Oktober", TODAY)
    assert q.categories == [Category.DONE, Category.PROGRESS] and q.split

    q = parse_command("/rekap Oktober pisah", TODAY)
    assert q.split

    q = parse_command("/rekap done pending Oktober", TODAY)
    assert q.categories == [Category.DONE, Category.PENDING] and q.split


def test_unknown_command():
    with pytest.raises(CommandError):
        parse_command("/foo", TODAY)
