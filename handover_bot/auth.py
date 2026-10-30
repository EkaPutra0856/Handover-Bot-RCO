"""Login Google sekali untuk membuat secrets/token.json.

Lokal:   python -m handover_bot.auth
Docker:  docker compose run --rm -p 8085:8085 bot python -m handover_bot.auth
Lalu buka URL yang muncul, login dengan akun yang punya akses spreadsheet (ravicraft700@gmail.com).
"""

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from .config import Settings
from .sources.google_sheets import SCOPES

PORT = int(os.getenv("OAUTH_PORT", "8085"))


def main() -> None:
    settings = Settings()
    secret = settings.client_secret_file
    if not secret.exists():
        sys.exit(f"File {secret} belum ada. Download OAuth Client ID (Desktop app) dari Google Cloud Console.")
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    in_docker = os.path.exists("/.dockerenv")
    creds = flow.run_local_server(
        host="localhost",
        bind_addr="0.0.0.0" if in_docker else None,
        port=PORT,
        open_browser=not in_docker,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message="Buka URL ini di browser lalu login:\n{url}\n",
        success_message="Login berhasil. Tab ini boleh ditutup.",
    )
    settings.token_file.parent.mkdir(parents=True, exist_ok=True)
    settings.token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"Token tersimpan di {settings.token_file}")


if __name__ == "__main__":
    main()
