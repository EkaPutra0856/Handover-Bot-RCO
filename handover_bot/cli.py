"""Coba rekap tanpa Telegram.

python -m handover_bot.cli "/rekap Oktober 2026"
python -m handover_bot.cli "/pending 1/10/2026 : 5/10/2026 detail" --xlsx "data/Data HandOver.xlsx"
"""

import argparse
import logging
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .commands import CommandError, parse_command
from .config import Settings
from .report import build_messages
from .service import collect_issues
from .sources import make_source


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", help='perintah seperti di Telegram, mis. "/rekap Oktober 2026"')
    ap.add_argument("--xlsx", help="pakai file Excel ini sebagai sumber")
    ap.add_argument("--today", help="anggap hari ini tanggal YYYY-MM-DD")
    ap.add_argument("--stats", action="store_true", help="tampilkan statistik klasifikasi")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING)
    settings = Settings()
    if args.xlsx:
        settings.source_type, settings.xlsx_path = "xlsx", args.xlsx
    today = date.fromisoformat(args.today) if args.today else datetime.now(ZoneInfo(settings.timezone)).date()

    command = args.command.strip()
    if not command.startswith("/"):
        command = "/" + command
    try:
        query = parse_command(command, today)
    except CommandError as e:
        sys.exit(f"❌ {e}")
    issues, warnings = collect_issues(make_source(settings), query)
    messages = build_messages(issues, query, settings.report_title, warnings)
    for n, msg in enumerate(messages, start=1):
        print(f"===== Pesan {n}/{len(messages)} ({len(msg)} karakter) =====")
        print(msg)
    if args.stats:
        from collections import Counter

        print("===== Statistik =====")
        print("Kategori:", dict(Counter(i.category.value for i in issues)))
        print("Alasan done:", dict(Counter(i.done_reason for i in issues if i.done_reason)))
        print("Tim:", dict(Counter(i.team for i in issues)))


if __name__ == "__main__":
    main()
