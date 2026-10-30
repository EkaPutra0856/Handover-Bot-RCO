"""Konfigurasi versi web (variabel WEB_* di .env), di atas Settings bot."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from handover_bot.config import Settings

DEFAULT_TRANSIT_ID = "1UK5iVxAi8ROiUHGIjGeMLeMZAOUAh-nRRb75eb3F59A"


@dataclass
class WebSettings:
    bot: Settings = field(default_factory=Settings)
    host: str = field(default_factory=lambda: os.getenv("WEB_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("WEB_PORT", "8080")))
    # Kosong = tanpa login. Wajib diisi kalau web bisa dibuka dari jaringan.
    password: str = field(default_factory=lambda: os.getenv("WEB_PASSWORD", ""))
    # Tujuan tombol "Kirim ke Tele"; kosong = chat pertama di ALLOWED_CHAT_IDS
    chat_id: str = field(default_factory=lambda: os.getenv("WEB_CHAT_ID", ""))
    # Spreadsheet transit (cermin publik) untuk link "buka baris di sheet"
    transit_spreadsheet_id: str = field(
        default_factory=lambda: os.getenv("TRANSIT_SPREADSHEET_ID", DEFAULT_TRANSIT_ID))

    @property
    def target_chat_id(self) -> int | None:
        if self.chat_id.strip():
            return int(self.chat_id)
        ids = self.bot.allowed_chat_ids
        return min(ids) if ids else None
