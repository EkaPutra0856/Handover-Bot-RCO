"""Handler Telegram."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import BotCommand, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from .commands import COMMANDS, CommandError, parse_command
from .config import Settings
from .report import build_messages, help_text
from .service import collect_issues
from .sources import make_source
from .sources.apps_script import AppsScriptError
from .sources.google_sheets import GoogleAuthError

log = logging.getLogger(__name__)

MENU = [
    ("rekap", "Rekap pending + on progress"),
    ("pending", "Hanya issue belum tersentuh"),
    ("progress", "Hanya issue on going"),
    ("done", "Hanya issue selesai"),
    ("doneprogress", "Done & on progress (2 bubble)"),
    ("rekapdetail", "Rekap + nama aplikasi"),
    ("help", "Panduan"),
    ("id", "Tampilkan chat id"),
]


class HandoverBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._source = None
        self.tz = ZoneInfo(settings.timezone)

    @property
    def source(self):
        # Dibuat saat dipakai, supaya bot tetap bisa start (/help, /id) walau sumber belum dikonfigurasi.
        if self._source is None:
            self._source = make_source(self.settings)
        return self._source

    def _allowed(self, update: Update) -> bool:
        ids = self.settings.allowed_chat_ids
        return not ids or update.effective_chat.id in ids

    async def _reply(self, update: Update, text: str) -> None:
        await update.effective_chat.send_message(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._allowed(update):
            return await self._denied(update)
        await self._reply(update, help_text())

    async def cmd_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(update, f"Chat id: <code>{update.effective_chat.id}</code>")

    async def _denied(self, update: Update) -> None:
        log.warning("Chat %s ditolak (tidak ada di ALLOWED_CHAT_IDS)", update.effective_chat.id)
        await self._reply(update, f"⛔ Chat ini belum diizinkan. Chat id: <code>{update.effective_chat.id}</code>")

    async def cmd_rekap(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._allowed(update):
            return await self._denied(update)
        text = update.effective_message.text or ""
        today = datetime.now(self.tz).date()
        try:
            query = parse_command(text, today)
        except CommandError as e:
            return await self._reply(update, f"❌ {e}")

        log.info("Chat %s: %r -> %s..%s %s", update.effective_chat.id, text, query.start, query.end,
                 [c.value for c in query.categories])
        await update.effective_chat.send_action(ChatAction.TYPING)
        try:
            issues, warnings = await asyncio.to_thread(lambda: collect_issues(self.source, query))
        except (GoogleAuthError, AppsScriptError) as e:
            log.error("Akses Google: %s", e)
            return await self._reply(update, f"❌ Akses spreadsheet bermasalah: {e}")
        except FileNotFoundError as e:
            return await self._reply(update, f"❌ {e}")

        for msg in build_messages(issues, query, self.settings.report_title, warnings):
            await self._reply(update, msg)

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.exception("Error saat memproses update", exc_info=context.error)
        if isinstance(update, Update) and update.effective_chat:
            await self._reply(update, "❌ Terjadi error saat membuat rekap. Cek log bot.")

    async def _post_init(self, app: Application) -> None:
        await app.bot.set_my_commands([BotCommand(c, d) for c, d in MENU])
        me = await app.bot.get_me()
        log.info("Bot @%s siap (sumber: %s)", me.username, self.settings.source_type)

    def build_app(self) -> Application:
        app = Application.builder().token(self.settings.telegram_token).post_init(self._post_init).build()
        app.add_handler(CommandHandler(["start", "help"], self.cmd_help))
        app.add_handler(CommandHandler("id", self.cmd_id))
        app.add_handler(CommandHandler(list(COMMANDS), self.cmd_rekap))
        app.add_error_handler(self.on_error)
        return app
