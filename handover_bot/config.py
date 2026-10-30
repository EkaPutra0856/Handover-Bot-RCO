"""Konfigurasi dari environment variable / file .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_SPREADSHEET_ID = "1lmIgK_GMZaeRUUc0Ea_K31jpRAn_P_PifWsm5PvjJsw"


def _ids(raw: str) -> set[int]:
    return {int(x) for x in raw.replace(";", ",").split(",") if x.strip()}


@dataclass
class Settings:
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    # "appscript" = lewat Apps Script Web App, "google" = Google Sheets API via OAuth, "xlsx" = file Excel lokal
    source_type: str = field(default_factory=lambda: os.getenv("SOURCE_TYPE", "appscript").lower())
    apps_script_url: str = field(default_factory=lambda: os.getenv("APPS_SCRIPT_URL", ""))
    apps_script_key: str = field(default_factory=lambda: os.getenv("APPS_SCRIPT_KEY", ""))
    spreadsheet_id: str = field(default_factory=lambda: os.getenv("SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID))
    xlsx_path: Path = field(default_factory=lambda: Path(os.getenv("XLSX_PATH", "data/Data HandOver.xlsx")))
    secrets_dir: Path = field(default_factory=lambda: Path(os.getenv("SECRETS_DIR", "secrets")))
    # "user" = warna isi sel manual, "effective" = termasuk conditional formatting
    color_mode: str = field(default_factory=lambda: os.getenv("COLOR_MODE", "user").lower())
    allowed_chat_ids: set[int] = field(default_factory=lambda: _ids(os.getenv("ALLOWED_CHAT_IDS", "")))
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Jakarta"))
    report_title: str = field(default_factory=lambda: os.getenv("REPORT_TITLE", "Handover Polisi – Team RCO"))

    @property
    def token_file(self) -> Path:
        return self.secrets_dir / "token.json"

    @property
    def client_secret_file(self) -> Path:
        return self.secrets_dir / "client_secret.json"
