# Handover RCO – Versi Web

Dashboard issue dari spreadsheet handover. Fiturnya:

- Filter periode, tim, kategori, dan pencarian.
- Tabel yang setiap barisnya terhubung ke spreadsheet.
- Export rekap ke Telegram, dengan preview pesan sebelum dikirim.

Versi web memakai logika yang sama dengan bot (`handover_bot`), jadi angka dan format pesannya selalu
identik.

## Struktur

```
web/
├── Dockerfile              image web (build dari root project)
├── README.md               dokumen ini
├── deploy/
│   └── nginx.conf.example  contoh reverse proxy HTTPS untuk server
├── handover_web/           package Python
│   ├── __main__.py         python -m handover_web
│   ├── config.py           variabel WEB_* dari .env
│   ├── app.py              logika: ambil issue, link sheet, susun & kirim pesan
│   ├── server.py           HTTP server + route API + file statis
│   └── static/
│       ├── index.html      halaman dashboard
│       ├── css/app.css     tampilan (otomatis gelap/terang)
│       ├── js/app.js       filter, tabel, popup export
│       └── favicon.svg
└── tests/
    ├── conftest.py         contoh workbook (dipinjam dari tests/ bot)
    └── test_web.py
```

Yang dipakai bersama bot, dan ada di root project:

- `handover_bot/` (aturan klasifikasi dan format pesan)
- `.env`
- `requirements.txt`
- `docker-compose.yml`

Versi web tidak butuh dependensi tambahan: server memakai `http.server` bawaan Python.

## Menjalankan

### Docker (disarankan)

Dari root project:

```powershell
docker compose up -d --build        # bot + web
docker compose ps                   # STATUS web harus "healthy"
docker compose logs -f web
```

Buka **http://localhost:8080**.

### Lokal tanpa Docker (untuk development)

```powershell
$env:PYTHONPATH = "$PWD;$PWD\web"; $env:WEB_PORT = "8090"
.\.venv\Scripts\python.exe -m handover_web
```

Di VS Code cukup tekan **F5** dan pilih **"Web: jalankan lokal (port 8090)"**. Konfigurasinya ada di
`.vscode/launch.json`.

### Tes

```powershell
.\.venv\Scripts\python.exe -m pytest -q     # tes bot + web (pytest.ini di root)
```

Di VS Code: **Terminal → Run Task → Tes (pytest)**, atau buka panel Testing.

## Konfigurasi (`.env` di root)

| Variabel | Default | Keterangan |
|---|---|---|
| `WEB_HOST` | `127.0.0.1` (Docker: `0.0.0.0`) | alamat listen |
| `WEB_PORT` | `8080` | port |
| `WEB_PASSWORD` | kosong | login browser (username bebas). **Wajib** kalau web bisa dibuka dari jaringan |
| `WEB_CHAT_ID` | chat pertama `ALLOWED_CHAT_IDS` | tujuan tombol **Kirim ke Tele** |
| `TRANSIT_SPREADSHEET_ID` | ID spreadsheet transit | untuk link baris di tabel |

Variabel bot (`TELEGRAM_BOT_TOKEN`, `APPS_SCRIPT_URL`, `APPS_SCRIPT_KEY`, `TIMEZONE`, `REPORT_TITLE`, dst.)
ikut dipakai.

## Deploy

### 1. Di PC ini saja (default)

`docker-compose.yml` memetakan port ke `127.0.0.1:8080`, jadi web hanya bisa dibuka dari PC ini dan
tidak perlu password.

### 2. Dibuka dari PC lain di jaringan kantor

1. Isi `WEB_PASSWORD` di `.env`.
2. Di `docker-compose.yml`, ubah `"127.0.0.1:8080:8080"` menjadi `"8080:8080"`.
3. Jalankan `docker compose up -d`, lalu buka `http://<IP-PC-ini>:8080`.

Tanpa password, siapa pun di jaringan bisa mengirim pesan ke grup lewat bot.

### 3. Server Linux dengan HTTPS

1. Copy seluruh project ke server, termasuk `.env` dan `secrets/`. Install Docker.
2. Isi `WEB_PASSWORD` dan biarkan port tetap `127.0.0.1:8080:8080`.
3. Jalankan `docker compose up -d --build`.
4. Pasang nginx sebagai reverse proxy HTTPS. Contohnya ada di `deploy/nginx.conf.example`.

Container berjalan sebagai user non-root, punya `HEALTHCHECK` ke `/healthz`, dan otomatis restart
(`restart: unless-stopped`).

## API

| Method | Path | Isi |
|---|---|---|
| GET | `/healthz` | `{"ok": true}`, tanpa login |
| GET | `/api/config` | judul, tanggal hari ini, daftar tim, tujuan Telegram, versi |
| GET | `/api/issues?start=YYYY-MM-DD&end=YYYY-MM-DD[&refresh=1]` | daftar issue + link baris sheet (cache 60 detik) |
| POST | `/api/preview` | `{start, end, categories, teams, detail, split, keys}` → `{messages}` |
| POST | `/api/send` | sama dengan preview, lalu kirim ke Telegram → `{sent, chat}` |

`keys` berisi daftar `"<nama tab>#<nomor issue>"` yang sedang tampil di tabel, supaya isi pesan sama
dengan tabel. POST wajib memakai `Content-Type: application/json`. Aturan ini menutup celah form
lintas situs (CSRF).

## Keamanan

- Pesan error dibersihkan dari token bot dan key Apps Script sebelum ditampilkan.
- Header `Content-Security-Policy` aktif: hanya script dan css dari server sendiri yang dijalankan.
- File statis hanya dilayani dari folder `static/`; path `../` ditolak.
- Kolom catatan teknis (Note, IP, query SQL di PIC) tidak pernah dikirim ke browser. Aturannya sama
  dengan bot.
