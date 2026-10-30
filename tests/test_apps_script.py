from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from handover_bot.commands import parse_command
from handover_bot.models import Category
from handover_bot.service import collect_issues
from handover_bot.sources.apps_script import AppsScriptError, AppsScriptSource

HEADER = ["Tanggal", "ISSUE", "Aplikasi", "Pelapor", "Media", "Penerima", "Pencatat", "Waktu Lapor",
          "Status", "Pic", "", "", "", "Note", "IP", "Dok"]
W = "#ffffff"


def _resp(payload):
    r = MagicMock()
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def _fake_get(url, params, timeout):
    if params["action"] == "titles":
        return _resp({"ok": True, "titles": ["Sheet1", "Issue Oktober 2026"]})
    values = [
        ["Column 1"] + [""] * 15,
        HEADER,
        ["2026-10-01", "x", "MPAYS", "1 ~Aldi", "", "", "", "", "", "", "", "", "", "select *", "", ""],
        ["2026-10-02", "x", "QRIS", 2, "", "", "", "", "oncek", "Hendrik", "", "", "", "", "", ""],
        ["2026-10-03", "x", "JCB", "3 ~B", "", "", "", "", "", "", "", "", "", "", "", ""],
    ]
    bgs = [[W] * 16, [W] * 16, [W] * 16, [W] * 16, ["#b7e1cd"] + [W] * 15]
    return _resp({"ok": True, "sheets": [{"title": "Issue Oktober 2026", "values": values, "backgrounds": bgs}]})


def test_apps_script_source():
    src = AppsScriptSource("https://script.google.com/macros/s/x/exec", "k")
    with patch("handover_bot.sources.apps_script.requests.get", side_effect=_fake_get):
        q = parse_command("/rekap Oktober 2026", date(2026, 10, 29))
        issues, warnings = collect_issues(src, q)
    by_no = {i.issue_no: i for i in issues}
    assert warnings == []
    assert by_no[3].category == Category.PENDING and by_no[3].team == "Tim 1"
    assert by_no[4].category == Category.PROGRESS and by_no[4].team == "Tim 2"
    assert by_no[5].category == Category.DONE and by_no[5].done_reason == "hijau"


def test_apps_script_rejects():
    src = AppsScriptSource("https://x", "salah")
    with patch("handover_bot.sources.apps_script.requests.get",
               return_value=_resp({"ok": False, "error": "unauthorized"})):
        with pytest.raises(AppsScriptError, match="unauthorized"):
            src.list_titles()
