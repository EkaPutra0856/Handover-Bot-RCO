from datetime import date

from handover_bot.commands import parse_command
from handover_bot.models import Category
from handover_bot.report import MAX_LEN, build_messages, chunk
from handover_bot.service import collect_issues
from handover_bot.sources.xlsx import XlsxSource

TODAY = date(2026, 10, 29)
TITLE = "Handover Polisi – Team RCO"


def _run(path, text):
    q = parse_command(text, TODAY)
    issues, warnings = collect_issues(XlsxSource(path), q)
    return q, issues, warnings


def test_classification(workbook_path):
    _, issues, warnings = _run(workbook_path, "/rekap Oktober 2026")
    assert warnings == []
    by_no = {i.issue_no: i for i in issues}
    assert 14 not in by_no  # tanggal 30 September difilter
    assert by_no[3].category == Category.PENDING and by_no[3].team == "Tim 1"
    assert by_no[4].category == Category.PROGRESS and by_no[4].pic == "Hendrik"
    assert by_no[5].done_reason == "status"
    assert by_no[6].done_reason == "hijau"
    assert by_no[7].category == Category.PENDING and by_no[7].pic == ""  # SQL tidak bocor
    assert by_no[8].category == Category.PROGRESS and by_no[8].label == "Tim 2" and by_no[8].team == "Tim 2"
    assert by_no[9].team == "ALL TEAM"
    assert by_no[10].category == Category.PENDING
    assert by_no[11].done_reason == "pic"
    assert by_no[12].done_reason == "hijau"
    assert by_no[13].category == Category.PROGRESS  # kuning bukan done


def test_rekap_message_format(workbook_path):
    q, issues, w = _run(workbook_path, "/rekap Oktober 2026")
    msgs = build_messages(issues, q, TITLE, w)
    assert len(msgs) == 1
    expected = """<b>Handover Polisi – Team RCO</b>

01/10/2026 - 31/10/2026

📌 <b>Pendingan Issue (Belum Dikerjakan):</b>

<b>Tim 1</b>
01/10/2026 — Issue 3
05/10/2026 — Issue 7
10/10/2026 — Issue 10

<b>Tim 2</b>
<i>Tidak ada pendingan</i>

<b>Tim 3</b>
<i>Tidak ada pendingan</i>

<b>ALL TEAM</b>
09/10/2026 — Issue 9

⏳ <b>Issue On Progress (Kuning):</b>

01/10/2026 — Tim 2 — Issue 4 — Hendrik
07/10/2026 — Tim 2 — Issue 8 — Tim 2
13/10/2026 — Tim 2 — Issue 13 — Puji

------------------------------------
Total Pending: 4 Issue (Putih)
Total On Progress: 3 Issue (Kuning)
Total Keseluruhan: 7 Issue

Mohon bantuannya untuk ditelusuri rekan-rekan engineer
Terima kasih."""
    assert msgs[0] == expected
    assert "select" not in msgs[0] and "172.18" not in msgs[0]


def test_detail_shows_app_only(workbook_path):
    q, issues, w = _run(workbook_path, "/rekapdetail 1 Oktober 2026")
    msg = build_messages(issues, q, TITLE, w)[0]
    assert "<b>Handover Polisi (Detail) – Team RCO</b>" in msg
    assert "01/10/2026 — Issue 3 — MPAYS" in msg
    assert "01/10/2026 — Tim 2 — Issue 4 — QRIS — Hendrik" in msg
    assert "deskripsi issue" not in msg


def test_cross_month_and_header_fallback(workbook_path):
    q, issues, w = _run(workbook_path, "/rekap 28 September 2026 : 2 Oktober 2026")
    nos = sorted((i.sheet, i.issue_no, i.category.value) for i in issues)
    assert ("Issue September 2026", 3, "pending") in nos
    assert ("Issue September 2026", 4, "progress") in nos
    assert ("Issue Oktober 2026", 3, "pending") in nos
    msg = build_messages(issues, q, TITLE, w)[0]
    assert "28/09/2026 - 02/10/2026" in msg
    assert "28/09/2026 — Issue 3" in msg


def test_missing_tab_warning(workbook_path):
    q, issues, w = _run(workbook_path, "/rekap November 2026")
    assert w == ["Tab 'Issue November 2026' tidak ditemukan"]
    msg = build_messages(issues, q, TITLE, w)[0]
    assert "⚠️" in msg and "Total Keseluruhan: 0 Issue" in msg


def test_doneprogress_two_bubbles(workbook_path):
    q, issues, w = _run(workbook_path, "/doneprogress Oktober 2026")
    msgs = build_messages(issues, q, TITLE, w)
    assert len(msgs) == 2
    assert "✅ <b>Issue Done (Hijau):</b>" in msgs[0] and "Total Done: 4 Issue (Hijau)" in msgs[0]
    assert "02/10/2026 — ALL TEAM — Issue 6 — ALL TEAM" in msgs[0]
    assert "Kuning" in msgs[1] and "Total Keseluruhan: 7 Issue" in msgs[1]
    assert "Total Keseluruhan" not in msgs[0]


def test_pending_only(workbook_path):
    q, issues, w = _run(workbook_path, "/pending Oktober 2026")
    msg = build_messages(issues, q, TITLE, w)[0]
    assert "On Progress" not in msg and "Total Pending: 4 Issue (Putih)" in msg
    assert "Total Keseluruhan" not in msg


def test_chunking_keeps_lines_whole():
    lines = [f"<b>Tim 1</b> 01/10/2026 — Issue {n}" for n in range(500)]
    parts = chunk(lines)
    assert len(parts) > 1
    for n, p in enumerate(parts, start=1):
        assert len(p) <= MAX_LEN + 40
        assert p.endswith(f"<i>(Part {n}/{len(parts)})</i>")
        assert p.count("<b>") == p.count("</b>")
