import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest
import requests

from handover_bot.config import Settings
from handover_bot.sources.xlsx import XlsxSource
from handover_web.app import HandoverWeb, WebError, parse_range
from handover_web.config import WebSettings
from handover_web.server import make_handler, static_file

HTMLVIEW = ('items.push({name: "Issue Oktober 2026", pageUrl: "https:\\/\\/x\\/htmlview\\/sheet?headers\\x3dtrue&gid=352", '
            'gid: "352",initialSheet: ("352" == gid)});')


class FakeHttp:
    def __init__(self, fail_send=False):
        self.posts = []
        self.fail_send = fail_send

    def get(self, url, **kw):
        if "htmlview" in url:
            return SimpleNamespace(text=HTMLVIEW, raise_for_status=lambda: None)
        return SimpleNamespace(json=lambda: {"ok": True, "result": {"title": "TesBot"}})

    def post(self, url, json=None, **kw):
        if self.fail_send:
            raise requests.ConnectionError(f"boom {url}")
        self.posts.append(json)
        return SimpleNamespace(json=lambda: {"ok": True})


def _web(path, http=None, **kw):
    bot = Settings()
    bot.telegram_token = "123456:SECRET"
    bot.allowed_chat_ids = {-5023011113}
    s = WebSettings(bot=bot, chat_id="", password=kw.get("password", ""))
    return HandoverWeb(s, source=XlsxSource(path), http=http or FakeHttp())


BODY = {"start": "2026-10-01", "end": "2026-10-31", "categories": ["pending", "progress"]}


def test_issues_payload_has_links_and_categories(workbook_path):
    data = _web(workbook_path).issues_payload("2026-10-01", "2026-10-31")
    by_no = {i["issue_no"]: i for i in data["issues"]}
    assert by_no[3]["category"] == "pending" and by_no[3]["team"] == "Tim 1"
    assert by_no[6]["category"] == "done"
    assert by_no[3]["link"].endswith("#gid=352&range=A3")
    assert by_no[3]["key"] == "Issue Oktober 2026#3"
    assert 14 not in by_no


def test_parse_range_rejects_bad_input():
    with pytest.raises(WebError):
        parse_range("2026-10-31", "2026-10-01")
    with pytest.raises(WebError):
        parse_range("31/10/2026", "2026-10-31")


def test_preview_matches_bot_format(workbook_path):
    msgs = _web(workbook_path).messages(BODY)
    assert len(msgs) == 1
    assert msgs[0].startswith("<b>Handover Polisi – Team RCO</b>")
    assert "Total Pending: 4 Issue (Putih)" in msgs[0]


def test_preview_team_filter_hides_other_teams(workbook_path):
    msg = _web(workbook_path).messages({**BODY, "teams": ["Tim 1"]})[0]
    assert "<b>Tim 1</b>" in msg
    assert "<b>Tim 2</b>" not in msg and "Tim 3" not in msg
    assert "Total Pending: 3 Issue (Putih)" in msg


def test_preview_only_visible_keys(workbook_path):
    msg = _web(workbook_path).messages({**BODY, "keys": ["Issue Oktober 2026#3"]})[0]
    assert "Issue 3" in msg and "Issue 7" not in msg
    assert "Total Pending: 1 Issue (Putih)" in msg
    assert "Total On Progress: 0 Issue (Kuning)" in msg


def test_preview_requires_category(workbook_path):
    with pytest.raises(WebError):
        _web(workbook_path).messages({**BODY, "categories": []})


def test_send_posts_each_message(workbook_path):
    http = FakeHttp()
    res = _web(workbook_path, http).send({**BODY, "categories": ["done", "progress"], "split": True})
    assert res["sent"] == 2 and res["chat"]["title"] == "TesBot"
    assert all(p["chat_id"] == -5023011113 and p["parse_mode"] == "HTML" for p in http.posts)


def test_send_error_hides_token(workbook_path):
    with pytest.raises(WebError) as e:
        _web(workbook_path, FakeHttp(fail_send=True)).send(BODY)
    assert "SECRET" not in str(e.value)


@pytest.fixture
def server(workbook_path, request):
    app = _web(workbook_path, password=getattr(request, "param", ""))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _call(url, body=None, ctype="application/json", headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": ctype, **(headers or {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_http_endpoints(server):
    status, html = _call(server + "/")
    assert status == 200 and b"Export ke Chat" in html
    status, js = _call(server + "/static/js/app.js")
    assert status == 200 and b"api/preview" in js
    assert _call(server + "/static/../server.py")[0] == 404
    status, body = _call(server + "/api/issues?start=2026-10-01&end=2026-10-31")
    assert status == 200 and len(json.loads(body)["issues"]) == 11
    status, body = _call(server + "/api/preview", BODY)
    assert status == 200 and json.loads(body)["messages"]
    status, body = _call(server + "/api/issues?start=x&end=y")
    assert status == 400 and "tidak valid" in json.loads(body)["error"]


def test_post_requires_json(server):
    status, _ = _call(server + "/api/send", BODY, ctype="text/plain")
    assert status == 415


def test_static_file_blocks_traversal():
    assert static_file("css/app.css") is not None
    assert static_file("../server.py") is None
    assert static_file("../../handover_web/app.py") is None


@pytest.mark.parametrize("server", ["rahasia"], indirect=True)
def test_password(server):
    assert _call(server + "/api/config")[0] == 401
    assert _call(server + "/healthz")[0] == 200  # healthcheck tanpa login
    import base64

    auth = {"Authorization": "Basic " + base64.b64encode(b"rco:rahasia").decode()}
    assert _call(server + "/api/config", headers=auth)[0] == 200
