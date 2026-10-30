"""Baca Google Sheets langsung (nilai + warna sel) dengan OAuth akun pemilik akses."""

from __future__ import annotations

import logging
import threading

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..config import Settings
from ..models import RGB, RawRow, RawSheet

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
LAST_COLUMN = "Q"  # sheet sumber punya 16-17 kolom

log = logging.getLogger(__name__)


class GoogleAuthError(RuntimeError):
    pass


def load_credentials(settings: Settings) -> Credentials:
    path = settings.token_file
    if not path.exists():
        raise GoogleAuthError(
            f"Token Google belum ada ({path}). Jalankan login sekali: python -m handover_bot.auth"
        )
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            path.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise GoogleAuthError("Token Google tidak valid. Ulangi login: python -m handover_bot.auth")
    return creds


def _rgb(color: dict | None) -> RGB | None:
    if not color:
        return None
    # API menghilangkan komponen yang nilainya 0.
    return tuple(round(color.get(k, 0.0) * 255) for k in ("red", "green", "blue"))  # type: ignore[return-value]


def _value(cell: dict):
    ev = cell.get("effectiveValue")
    if not ev:
        return None
    for key in ("stringValue", "numberValue", "boolValue"):
        if key in ev:
            return ev[key]
    return None  # errorValue dll.


class GoogleSheetSource:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.spreadsheet_id = settings.spreadsheet_id
        self.format_key = "effectiveFormat" if settings.color_mode == "effective" else "userEnteredFormat"
        self._lock = threading.Lock()  # httplib2 tidak thread-safe

    def _service(self):
        return build("sheets", "v4", credentials=load_credentials(self.settings), cache_discovery=False)

    def list_titles(self) -> list[str]:
        with self._lock:
            resp = (
                self._service()
                .spreadsheets()
                .get(spreadsheetId=self.spreadsheet_id, fields="sheets.properties.title")
                .execute()
            )
        return [s["properties"]["title"] for s in resp.get("sheets", [])]

    def fetch(self, titles: list[str]) -> list[RawSheet]:
        if not titles:
            return []
        ranges = ["'{}'!A1:{}".format(t.replace("'", "''"), LAST_COLUMN) for t in titles]
        fields = (
            "sheets(properties.title,data(startRow,rowData(values("
            f"effectiveValue,{self.format_key}.backgroundColor))))"
        )
        with self._lock:
            resp = (
                self._service()
                .spreadsheets()
                .get(spreadsheetId=self.spreadsheet_id, ranges=ranges, includeGridData=True, fields=fields)
                .execute()
            )

        out = []
        for sheet in resp.get("sheets", []):
            title = sheet["properties"]["title"]
            rows: list[RawRow] = []
            for block in sheet.get("data", []):
                start = block.get("startRow", 0)
                for i, rd in enumerate(block.get("rowData", [])):
                    cells = rd.get("values", [])
                    rows.append(
                        RawRow(
                            row_number=start + i + 1,
                            values=[_value(c) for c in cells],
                            colors=[_rgb(c.get(self.format_key, {}).get("backgroundColor")) for c in cells],
                        )
                    )
            log.info("Sheet %r: %d baris", title, len(rows))
            out.append(RawSheet(title=title, rows=rows))
        return out
