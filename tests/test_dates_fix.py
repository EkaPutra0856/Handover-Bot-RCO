from datetime import date

from handover_bot.models import RawRow, RawSheet
from handover_bot.rules import ColumnMap, build_issues
from handover_bot.service import fix_typo_dates

COLS = ColumnMap(tanggal=0, aplikasi=None, team=None, pelapor=1, status=2, pic=3)


def _rows(*dates):
    return RawSheet("Issue Juli 2026", [RawRow(n, [d, "1 ~a", None, None], [None] * 4)
                                         for n, d in enumerate(dates, start=3)])


def test_missing_date_uses_previous_row():
    out = build_issues(_rows("2026-07-02", " ", None), COLS)
    assert [(i.issue_no, i.tanggal) for i in out] == [(3, date(2026, 7, 2)), (4, date(2026, 7, 2)),
                                                      (5, date(2026, 7, 2))]


def test_empty_row_without_issue_skipped():
    sheet = RawSheet("t", [RawRow(3, ["2026-07-02", "1 ~a", None, None], [None] * 4),
                           RawRow(4, [None, None, None, None], [None] * 4)])
    assert [i.issue_no for i in build_issues(sheet, COLS)] == [3]


def test_typo_year_fixed_to_tab_year():
    issues = build_issues(_rows("2026-07-04", "2025-07-05", "2015-07-06", "2026-08-01"), COLS)
    fixed = fix_typo_dates(issues, 2026, 7)
    assert [i.tanggal for i in fixed] == [date(2026, 7, 4), date(2026, 7, 5), date(2026, 7, 6), date(2026, 8, 1)]


def test_wrong_month_uses_previous_date():
    issues = build_issues(_rows("2026-07-10", "2026-01-11"), COLS)
    assert [i.tanggal for i in fix_typo_dates(issues, 2026, 7)] == [date(2026, 7, 10), date(2026, 7, 10)]
