# Bot Handover – Team RCO

Bot Telegram yang merekap issue dari spreadsheet **Issue &lt;Bulan&gt; &lt;Tahun&gt;**:
pending (putih), on progress (kuning), dan done (hijau). Hasilnya dikirim ke grup dengan format
*Handover Polisi – Team RCO*.

Versi ini menggantikan alur lama n8n + Apps Script + spreadsheet transit. Bot membaca Google Sheets
langsung lewat API, termasuk **warna sel** dan **beberapa tab sekaligus**. Karena itu `Sheet1` transit
dan Web App Apps Script tidak diperlukan lagi.

## Fitur

| Perintah | Isi |
|---|---|
| `/rekap [periode]` | Pending + on progress (format lama) |
| `/pending [periode]` | Hanya issue yang belum tersentuh |
| `/progress [periode]` | Hanya issue yang masih on going |
| `/done [periode]` | Hanya issue yang sudah selesai |
| `/doneprogress [periode]` | Done dan on progress, dikirim dalam 2 bubble chat |
| `/rekapdetail [periode]` | Rekap + nama aplikasi (bukan isi issue) |
| `/help`, `/id` | Panduan, chat id |

**Periode:** kosong (hari ini), `kemarin`, `minggu ini`, `bulan ini`, `bulan lalu`, `Oktober`,
`Oktober 2026`, `13 Oktober 2026`, `13/10/2026`, `5 Oktober 2026 : 7 Oktober 2026`, `5-7 Oktober 2026`,
`28 September 2026 : 2 Oktober 2026` (lintas bulan), `September : November 2026`.
Pemisah rentang boleh `:`, ` - `, `s/d`, `sampai`, atau `hingga`.

**Tambahan** (bisa digabung dengan semua perintah): `detail` (nama aplikasi), `pisah` (tiap kategori
di bubble terpisah), dan nama kategori `pending` / `progress` / `done`. Contoh: `/rekap done pending Oktober`.

## Aturan rekap

- **Done** (tidak masuk pending/progress): Status berisi done/close/closed/solved/selesai, PIC berisi
  "done", atau **ada sel berwarna hijau** di baris itu (hijau apa pun, termasuk hijau muda).
- **Pending (putih):** bukan done, PIC kosong atau `-`, Status kosong / `-` / `pending` / `30/12/1899`,
  dan baris tidak berwarna kuning atau orange.
- **On progress (kuning):** bukan done, dan PIC atau Status terisi, atau baris berwarna kuning atau orange.
  Yang ditampilkan nama PIC; kalau PIC kosong, teks status.
- **Orange** (sesuai legenda di baris 1 sheet: *menunggu tindak lanjut eksternal*) masuk on progress
  dengan tanda 🟠.
- **PIC disaring:** isi lebih dari 25 karakter, multiline, query SQL, IP, link, atau path otomatis dibuang,
  supaya catatan teknis tidak bocor ke Telegram. Kolom Note, IP, dan Dokumentasi tidak pernah dibaca.
- **Tim:** diambil dari kolom TEAM (`All` berarti ALL TEAM). Kalau kolom TEAM tidak ada atau kosong,
  diambil dari awalan kolom Pelapor:
  `1 ~Nama` masuk Tim 1, `Tim 2 - X` masuk Tim 2, dan seterusnya. Selain itu masuk ALL TEAM.
- **Filter tanggal** memakai kolom Tanggal (tanggal lapor), bukan Tanggal Finish.
- **Nomor issue** = nomor baris asli di sheet. Baris 3 berarti Issue 3.
- **Kolom dicari otomatis** dari baris header (`Tanggal`, `Aplikasi`, `Team`, `Pelapor`, `Status`, `Pic`)
  di 6 baris teratas. Tab tanpa header memakai layout tab lain, atau layout default sheet sumber
  (A Tanggal, C Aplikasi, D Pelapor, I Status, J Pic).
- Pesan panjang dipecah per baris utuh (maks ~3800 karakter) dengan penanda `(Part x/y)`.

## Setup (sekali)

### 1. Python

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

Perintah ini membuat `.venv`, meng-install dependency, dan membuat `.env` dari `.env.example`.

### 2. Token Telegram

Isi `TELEGRAM_BOT_TOKEN` di `.env`, dari @BotFather. Kalau memakai bot yang sama dengan n8n,
**matikan dulu workflow n8n-nya**: satu bot hanya bisa dipakai oleh satu penerima update.

`ALLOWED_CHAT_IDS` membatasi siapa yang boleh memakai bot. Ketik `/id` di grup untuk melihat chat id-nya.

### 3. Akses Google Sheets lewat Apps Script (default, `SOURCE_TYPE=appscript`)

Spreadsheet sumber hanya bisa dibuka oleh ravicraft700@gmail.com. Karena itu bot memanggil Web App
Apps Script yang jalan atas nama akun tersebut. Web App ini hanya membaca: nilai sel dan warna latar,
langsung dari sheet sumber. Spreadsheet transit tidak dipakai lagi.

1. Login sebagai **ravicraft700@gmail.com**, buka https://script.google.com, lalu klik **New project**.
2. Hapus isi `Code.gs` bawaan, lalu tempel isi `secrets/Code.gs`. File ini sudah berisi `SECRET_KEY`
   yang sama dengan `APPS_SCRIPT_KEY` di `.env`. Simpan.
3. Klik **Deploy → New deployment → ⚙ Web app**, isi **Execute as: Me** dan
   **Who has access: Anyone**, lalu klik **Deploy** dan **Authorize access**.
4. Salin **Web app URL** (berakhiran `/exec`) ke `APPS_SCRIPT_URL` di `.env`.

Kalau kode Apps Script diubah, buka **Deploy → Manage deployments → Edit → Version: New version**
supaya URL-nya tetap sama.

### 3b. Alternatif: Google Sheets API (OAuth, `SOURCE_TYPE=google`)

1. Buka https://console.cloud.google.com, lalu buat project baru (nama bebas).
2. Buka **APIs & Services → Library**, cari **Google Sheets API**, lalu klik **Enable**.
3. Buka **APIs & Services → OAuth consent screen**:
   - User type **External**, isi nama app dan email.
   - Scope tidak perlu diisi.
   - Di **Test users**, tambahkan `ravicraft700@gmail.com`.
   - Setelah selesai, klik **Publish app → In production**. Tanpa langkah ini token kedaluwarsa tiap 7 hari.
4. Buka **APIs & Services → Credentials → Create credentials → OAuth client ID**, pilih tipe
   **Desktop app**, lalu download JSON-nya. Simpan sebagai `secrets/client_secret.json`.
5. Login sekali:

   ```powershell
   .\.venv\Scripts\python.exe -m handover_bot.auth
   ```

   Browser akan terbuka. Login dengan **ravicraft700@gmail.com**. Kalau muncul "Google hasn't verified
   this app", klik **Advanced → Go to … (unsafe)**: app ini milikmu sendiri dan hanya meminta akses
   baca spreadsheet. Token tersimpan di `secrets/token.json`.

### 4. Coba tanpa Telegram

```powershell
.\.venv\Scripts\python.exe -m handover_bot.cli "/rekap Oktober 2026" --stats
```

`--stats` menampilkan jumlah per kategori, alasan done, dan per tim. Angka ini bisa dicocokkan dengan sheet.

### 5. Jalankan bot

```powershell
powershell -ExecutionPolicy Bypass -File run-bot.ps1
```

Bot otomatis restart kalau crash. Untuk berhenti, tekan Ctrl+C.

## Versi web

Dashboard di folder **`web/`**: filter, tabel yang terhubung ke spreadsheet, dan export rekap ke
Telegram. Jalankan `docker compose up -d --build`, lalu buka **http://localhost:8080**.
Struktur, konfigurasi, dan cara deploy ada di **[web/README.md](web/README.md)**.

## Spreadsheet transit

Bot tidak memakai spreadsheet transit; transit hanya cermin untuk dilihat orang.
`apps_script/TransitSync.gs` (di project Apps Script yang sama dengan `Code.gs`) menyalin tab
`Issue ...` dari sheet asli ke transit **per sel**: baris N di transit = baris N di sheet asli,
lengkap dengan warna, format, merge, dan lebar kolom. Sheet asli hanya dibaca.

- `syncTransit` — tab bulan ini, bulan lalu, dan tab Issue yang sudah ada di transit.
- `syncTransitAll` — semua tab Issue.
- `verifyTransit` — hitung sel yang beda isi/warna antara transit dan sheet asli (lihat log).
- Jadwal otomatis: di Apps Script buka **Pemicu → Tambahkan Pemicu**, pilih `syncTransit`,
  **Dipicu oleh waktu → Timer menit → Setiap 10 menit**. Sudah terpasang sejak 30 Okt 2026.

Lewat endpoint Web App: `?key=...&action=sync` (tambah `&all=1` untuk semua tab) dan `?key=...&action=verify`.

## Mode Excel (tanpa Google)

Simpan file Excel di `data/`, lalu di `.env` isi `SOURCE_TYPE=xlsx` dan `XLSX_PATH=data/NamaFile.xlsx`.
Warna isi sel di Excel ikut terbaca. Untuk tes cepat:

```powershell
.\.venv\Scripts\python.exe -m handover_bot.cli "/rekap Oktober 2026" --xlsx "data\Data HandOver.xlsx" --stats
```

## Docker

```powershell
docker compose build
docker compose run --rm -p 8085:8085 bot python -m handover_bot.auth   # login Google sekali
docker compose up -d
docker compose logs -f
```

Docker Desktop di PC ini belum bisa jalan karena WSL2 butuh **Virtual Machine Platform** dan
virtualisasi aktif di BIOS. Untuk mengaktifkannya, jalankan `wsl --install --no-distribution` di
PowerShell **Run as Administrator**, nyalakan virtualisasi (Intel VT-x / AMD SVM) di BIOS, lalu restart.

## Konfigurasi `.env`

| Variabel | Default | Keterangan |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | – | wajib |
| `SOURCE_TYPE` | `appscript` | `appscript`, `google`, atau `xlsx` |
| `APPS_SCRIPT_URL` | – | URL Web App `/exec` |
| `APPS_SCRIPT_KEY` | – | sama dengan `SECRET_KEY` di Apps Script |
| `SPREADSHEET_ID` | ID sheet sumber | |
| `XLSX_PATH` | `data/Data HandOver.xlsx` | untuk `SOURCE_TYPE=xlsx` |
| `ALLOWED_CHAT_IDS` | kosong (semua) | pisahkan dengan koma |
| `COLOR_MODE` | `user` | `effective` = ikut warna dari conditional formatting |
| `TIMEZONE` | `Asia/Jakarta` | untuk "hari ini" |
| `REPORT_TITLE` | `Handover Polisi – Team RCO` | |
| `WEB_*`, `TRANSIT_SPREADSHEET_ID` | | versi web, lihat [web/README.md](web/README.md) |

## Struktur kode

```
handover_bot/
  commands.py   parse perintah & periode
  dates.py      tanggal Indonesia, serial Sheets
  rules.py      deteksi kolom, hijau, tim, sanitasi PIC, klasifikasi
  service.py    pilih tab per bulan, gabungkan, filter tanggal
  report.py     format pesan HTML + pecah pesan
  bot.py        handler Telegram
  sources/      google_sheets.py (API + OAuth), xlsx.py (openpyxl)
  auth.py       login Google sekali
  cli.py        tes rekap dari terminal
tests/          pytest (jalankan: .\.venv\Scripts\python.exe -m pytest)
web/            versi web (lihat web/README.md)
.vscode/        launch (F5), task Docker & tes untuk VS Code
```
