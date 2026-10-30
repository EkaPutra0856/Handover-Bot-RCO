import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from handover_bot.bot import HandoverBot
from handover_bot.config import Settings


def _bot(path, allowed=()):
    s = Settings()
    s.telegram_token = "123456:TEST"
    s.source_type, s.xlsx_path = "xlsx", path
    s.allowed_chat_ids = set(allowed)
    return HandoverBot(s)


def _update(text, chat_id=-5023011113):
    chat = SimpleNamespace(id=chat_id, send_message=AsyncMock(), send_action=AsyncMock())
    return SimpleNamespace(effective_chat=chat, effective_message=SimpleNamespace(text=text)), chat


def test_rekap_sends_html(workbook_path):
    bot = _bot(workbook_path)
    upd, chat = _update("/rekap Oktober 2026")
    asyncio.run(bot.cmd_rekap(upd, None))
    text = chat.send_message.await_args.args[0]
    assert text.startswith("<b>Handover Polisi – Team RCO</b>")
    assert chat.send_message.await_args.kwargs["parse_mode"] == "HTML"


def test_doneprogress_two_messages(workbook_path):
    bot = _bot(workbook_path)
    upd, chat = _update("/doneprogress Oktober 2026")
    asyncio.run(bot.cmd_rekap(upd, None))
    assert chat.send_message.await_count == 2


def test_bad_period_replies_error(workbook_path):
    bot = _bot(workbook_path)
    upd, chat = _update("/rekap 40/10/2026")
    asyncio.run(bot.cmd_rekap(upd, None))
    assert chat.send_message.await_args.args[0].startswith("❌")


def test_whitelist_blocks_other_chats(workbook_path):
    bot = _bot(workbook_path, allowed=[-5023011113])
    upd, chat = _update("/rekap Oktober 2026", chat_id=999)
    asyncio.run(bot.cmd_rekap(upd, None))
    assert "belum diizinkan" in chat.send_message.await_args.args[0]


def test_app_builds(workbook_path):
    app = _bot(workbook_path).build_app()
    assert app.handlers
