# Ringkasan Requirement (dari chat Gemini "Pengenalan dan Cara Pakai N8N", 29/10/2026)

## Tujuan
Bot Telegram "Handover Polisi – Team RCO": rekap issue Pending (Putih) & On Progress (Kuning) dari spreadsheet issue bulanan, buang yang Done, kelompokkan per Tim 1/2/3/ALL TEAM. Default chatId grup: -5023011113.

## Arsitektur lama (n8n)
Telegram Trigger -> Parse Command (JS) -> HTTP GET Apps Script WebApp (copy sumber -> spreadsheet transit, deteksi hijau -> Status "Done", pisah kolom Team) -> Google Sheets Get Rows (tab dinamis) -> Code JS (filter, sanitasi, chunk 3200 char) -> Telegram Send (parse_mode HTML).

Alasan transit: n8n Sheets node tak bisa baca warna sel & hanya 1 tab per eksekusi. Sheet1 = gabungan >1 bulan, tab "Issue <Bulan> <Tahun>" = 1 bulan.

## Sumber data
- Spreadsheet sumber: https://docs.google.com/spreadsheets/d/1lmIgK_GMZaeRUUc0Ea_K31jpRAn_P_PifWsm5PvjJsw (hanya akun ravicraft700@gmail.com yang punya akses).
- Tab: `Issue <NamaBulan> <Tahun>` mis. `Issue Oktober 2026`.
- Header di baris 2, data mulai baris 3 (baris 1 kadang tabel otomatis "Column 1..."; beberapa tab header hilang).
- Kolom sumber (16): A Tanggal, B ISSUE (deskripsi), C Aplikasi, D Pelapor (gabung tim, mis. "1 ~Aldi", "2 ~Putri", "3 temuan", "1.0"), E Media Laporan, F Penerima Laporan, G Pencatat Issue, H Waktu Lapor, I Status, J Pic, K Waktu Mulai, L Tanggal Finish, M Waktu Selesai, N Note (SQL/rahasia, DILARANG ke Telegram), O Aplikasi (IP), P Dokumentasi.
- Versi transit (17 kolom) menyisipkan kolom Team di D, Pelapor jadi E, Status J, Pic K.
- Nomor issue: user pernah koreksi "issue no 1 dimulai dari baris 3" pada sheet sumber.

## Aturan bisnis
- DONE (skip): Status mengandung done/close/closed/solved/selesai; Pic berisi "done"; ADA sel berwarna hijau di baris itu (apa pun status/PIC).
- PUTIH (pending): bukan done, Pic kosong/"-", Status kosong/"-"/"30/12/1899".
- KUNING (on progress): bukan done, Pic valid ATAU status lain (oncek, on progress, tbd...). Tampil PIC, fallback teks status.
- Sanitasi PIC: tolak >25 char, multiline, SQL keyword, IP, http/bridrive, path d:\, .mdf/.ldf.
- Tim: awalan 1 / "tim 1" -> Tim 1, dst; lainnya ALL TEAM.
- Filter tanggal pakai kolom A (Tanggal lapor), BUKAN Tanggal Finish.

## Perintah
/help, /start; /rekap Oktober [2026]; /rekap 13 Oktober 2026 | 13/10/2026; /rekap 5 Oktober 2026 : 7 Oktober 2026 | 05/10/2026 : 07/10/2026; lintas bulan /rekap 28 September 2026 : 2 Oktober 2026; /rekapdetail ... (tambah nama aplikasi di baris pending). Tanpa argumen = hari ini.

## Template output
```
<b>Handover Polisi – Team RCO</b>

01/10/2026 - 31/10/2026

📌 <b>Pendingan Issue (Belum Dikerjakan):</b>

<b>Tim 1</b>
01/10/2026 — Issue 15

<b>ALL TEAM</b>
01/10/2026 — Issue 53

⏳ <b>Issue On Progress (Kuning):</b>

01/10/2026 — Tim 1 — Issue 9 — Dana

------------------------------------
Total Pending: 84 Issue (Putih)
Total On Progress: 144 Issue (Kuning)
Total Keseluruhan: 228 Issue

Mohon bantuannya untuk ditelusuri rekan-rekan engineer
Terima kasih.
```
Detail mode: `DD/MM/YYYY — Issue X — NamaAplikasi`, judul `Handover Polisi (Detail) – Team RCO`. Pesan dipecah per baris utuh maks ~3200 char + `<i>(Part x/y)</i>`.

## Error lama
- Telegram "can't parse entities" (tag HTML terpotong / parse mode kosong).
- SQL bocor via PIC saat kolom bergeser.
- Semua masuk ALL TEAM (team di kolom pelapor).
- Hasil 0 issue (header "Tanggal" hilang -> cari header by name gagal).
- Hijau tidak terbaca n8n.

## Belum beres
- Angka Oktober 2026 versi Gemini: 1128 baris, 895 done, 84 putih, 144 kuning (belum divalidasi).
- Fungsi file Daily Checklist (1).xlsx belum jelas.
- Posisi header tidak konsisten antar tab.
