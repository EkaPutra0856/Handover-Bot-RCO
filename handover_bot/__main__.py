"""Jalankan bot: python -m handover_bot"""

import logging
import sys

from .bot import HandoverBot
from .config import Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings()
    if not settings.telegram_token:
        print("TELEGRAM_BOT_TOKEN belum diisi di .env", file=sys.stderr)
        sys.exit(2)  # exit 2 = salah konfigurasi, run-bot.ps1 tidak restart
    HandoverBot(settings).build_app().run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
