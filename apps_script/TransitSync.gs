/**
 * Sync spreadsheet transit = cermin 1:1 tab "Issue ..." dari sheet asli.
 *
 * - Baris N di transit = baris N di sheet asli (isi, warna, format, merge, lebar kolom).
 * - Sheet asli HANYA DIBACA. Semua penulisan hanya ke spreadsheet transit.
 * - Tab transit yang sudah ada tidak dihapus (gid/link tetap sama), isinya ditimpa.
 *
 * Fungsi yang dipakai:
 *   syncTransit()        -> tab bulan ini + bulan lalu + tab Issue yang sudah ada di transit
 *   syncTransitAll()     -> semua tab Issue di sheet asli
 *   verifyTransit()      -> bandingkan isi & warna transit vs asli, tulis hasil ke log
 *
 * Jadwal otomatis: menu Pemicu -> syncTransit, Dipicu oleh waktu, Timer menit, Setiap 10 menit.
 * (Sengaja tidak memakai ScriptApp supaya tidak butuh izin tambahan "kelola trigger".)
 */

var TRANSIT_SOURCE_ID = "1lmIgK_GMZaeRUUc0Ea_K31jpRAn_P_PifWsm5PvjJsw";
var TRANSIT_TARGET_ID = "1UK5iVxAi8ROiUHGIjGeMLeMZAOUAh-nRRb75eb3F59A";
var TRANSIT_TAB_RE = /^\s*issue[\s_]+([A-Za-z]+)\.?[\s_]+(\d{2}|\d{4})\s*$/i;
var TRANSIT_BULAN = {
  jan: 1, januari: 1, feb: 2, februari: 2, mar: 3, maret: 3, apr: 4, april: 4, mei: 5, may: 5,
  jun: 6, juni: 6, jul: 7, juli: 7, ags: 8, agt: 8, agst: 8, agus: 8, agu: 8, agustus: 8, aug: 8,
  sep: 9, sept: 9, september: 9, okt: 10, oktober: 10, oct: 10, nov: 11, nop: 11, november: 11,
  des: 12, desember: 12, dec: 12
};

/** Menu di spreadsheet transit (project ini ter-bind ke transit). */
function onOpen() {
  SpreadsheetApp.getUi().createMenu("🚀 Sync Handover")
    .addItem("Sync bulan ini & bulan lalu", "syncTransit")
    .addItem("Sync semua tab Issue", "syncTransitAll")
    .addItem("Cek transit vs sheet asli", "verifyTransitMenu")
    .addToUi();
}

function verifyTransitMenu() {
  SpreadsheetApp.getUi().alert(verifyTransit().join("\n"));
}

function syncTransit() {
  return transitRun_(false);
}

function syncTransitAll() {
  return transitRun_(true);
}

function transitRun_(all) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) throw new Error("Sync transit lain masih berjalan");
  try {
    var src = SpreadsheetApp.openById(TRANSIT_SOURCE_ID);
    var dst = SpreadsheetApp.openById(TRANSIT_TARGET_ID);
    if (dst.getSpreadsheetTimeZone() !== src.getSpreadsheetTimeZone()) {
      dst.setSpreadsheetTimeZone(src.getSpreadsheetTimeZone());  // tanggal tidak geser sehari
    }
    if (dst.getSpreadsheetLocale() !== src.getSpreadsheetLocale()) {
      dst.setSpreadsheetLocale(src.getSpreadsheetLocale());  // angka tampil sama (141.1 vs 141,1)
    }
    // Sisa salinan sementara dari run yang gagal di tengah jalan.
    dst.getSheets().forEach(function (s) {
      if (/^(copy of|salinan)\s.*issue/i.test(s.getName())) dst.deleteSheet(s);
    });
    var names = transitTabsToSync_(src, dst, all);
    var done = [];
    names.forEach(function (name) {
      var t0 = Date.now();
      transitCopyTab_(src.getSheetByName(name), dst);
      done.push(name + " (" + Math.round((Date.now() - t0) / 1000) + " dtk)");
    });
    Logger.log("Sync transit selesai: " + done.join(", "));
    return done;
  } finally {
    lock.releaseLock();
  }
}

function transitTabsToSync_(src, dst, all) {
  var srcNames = src.getSheets().map(function (s) { return s.getName(); })
    .filter(function (n) { return TRANSIT_TAB_RE.test(n); });
  if (all) return srcNames;

  var tz = src.getSpreadsheetTimeZone();
  var now = new Date();
  var y = Number(Utilities.formatDate(now, tz, "yyyy"));
  var m = Number(Utilities.formatDate(now, tz, "M"));
  var wanted = [[y, m], m === 1 ? [y - 1, 12] : [y, m - 1]];
  var dstNames = dst.getSheets().map(function (s) { return s.getName(); });

  return srcNames.filter(function (n) {
    if (dstNames.indexOf(n) >= 0) return true;
    var ym = transitTabMonth_(n);
    return ym && wanted.some(function (w) { return w[0] === ym[0] && w[1] === ym[1]; });
  });
}

function transitTabMonth_(name) {
  var m = TRANSIT_TAB_RE.exec(name);
  if (!m) return null;
  var month = TRANSIT_BULAN[m[1].toLowerCase()];
  var year = Number(m[2]);
  if (year < 100) year += 2000;
  return month ? [year, month] : null;
}

/** Salin satu tab sumber ke tab bernama sama di transit, persis per sel. */
function transitCopyTab_(srcSheet, dst) {
  var name = srcSheet.getName();
  var rows = srcSheet.getMaxRows();
  var cols = srcSheet.getMaxColumns();

  // Salinan utuh (format, warna, merge, validasi, conditional format) ke transit;
  // PASTE_NORMAL di bawah ikut membawa conditional format.
  var temp = srcSheet.copyTo(dst);
  try {
    // Filter yang menyembunyikan baris membuat paste melompati baris tersembunyi -> baris bergeser.
    transitDropFilter_(temp);
    transitFreezeValues_(srcSheet, temp, rows, cols);
    transitFixColors_(srcSheet, temp, rows, cols);
    var target = dst.getSheetByName(name);
    if (!target) {
      temp.setName(name);
      transitRestoreFilter_(srcSheet, temp);
      temp = null;
      return;
    }

    try {
      transitDropFilter_(target);
      target.showRows(1, target.getMaxRows());
      target.setFrozenRows(0);
      target.setFrozenColumns(0);
      transitResize_(target, rows, cols);
      var full = target.getRange(1, 1, rows, cols);
      full.breakApart();
      target.clear();
      target.clearConditionalFormatRules();
      full.clearDataValidations();

      var tempRange = temp.getRange(1, 1, rows, cols);
      tempRange.copyTo(full, SpreadsheetApp.CopyPasteType.PASTE_NORMAL, false);
      tempRange.copyTo(full, SpreadsheetApp.CopyPasteType.PASTE_COLUMN_WIDTHS, false);
      target.setFrozenRows(srcSheet.getFrozenRows());
      target.setFrozenColumns(srcSheet.getFrozenColumns());
      // getRowHeight per baris terlalu lambat (>6 menit); tinggi baris disesuaikan ke isi.
      target.autoResizeRows(1, rows);
      transitRestoreFilter_(srcSheet, target);
    } catch (e) {
      // Tab transit tidak bisa ditimpa (mis. berisi tabel): ganti dengan salinan baru.
      Logger.log("Tab " + name + " diganti utuh: " + e);
      var index = target.getIndex();
      dst.deleteSheet(target);
      temp.setName(name);
      transitRestoreFilter_(srcSheet, temp);
      dst.setActiveSheet(temp);
      dst.moveActiveSheet(index);
      temp = null;
    }
  } finally {
    if (temp) dst.deleteSheet(temp);
  }
}

/** Rumus di sheet asli bisa merujuk tab lain -> di transit tulis hasil nilainya saja. */
function transitFreezeValues_(srcSheet, target, rows, cols) {
  var srcRange = srcSheet.getRange(1, 1, rows, cols);
  var formulas = srcRange.getFormulas();
  var values = null;
  // Hanya sel berumus yang ditimpa; setValues seluruh range bisa mengubah teks seperti "141.143" jadi angka.
  formulas.forEach(function (r, i) {
    r.forEach(function (f, j) {
      if (!f) return;
      values = values || srcRange.getValues();
      target.getRange(i + 1, j + 1).setValue(values[i][j]);
    });
  });
}

function transitDropFilter_(sheet) {
  var f = sheet.getFilter();
  if (f) f.remove();
}

/** Filter polos di range yang sama dengan sumber (tanpa kriteria, jadi tidak ada baris yang disembunyikan). */
function transitRestoreFilter_(srcSheet, sheet) {
  var f = srcSheet.getFilter();
  if (f) sheet.getRange(f.getRange().getA1Notation()).createFilter();
}

/** Warna tema bisa beda antar spreadsheet -> tulis warna latar & font sebagai hex dari sumber. */
function transitFixColors_(srcSheet, sheet, rows, cols) {
  var srcRange = srcSheet.getRange(1, 1, rows, cols);
  var range = sheet.getRange(1, 1, rows, cols);
  range.setBackgrounds(srcRange.getBackgrounds());
  range.setFontColors(srcRange.getFontColors());
}

function transitResize_(sheet, rows, cols) {
  var r = sheet.getMaxRows(), c = sheet.getMaxColumns();
  if (r < rows) sheet.insertRowsAfter(r, rows - r);
  if (r > rows) sheet.deleteRows(rows + 1, r - rows);
  if (c < cols) sheet.insertColumnsAfter(c, cols - c);
  if (c > cols) sheet.deleteColumns(cols + 1, c - cols);
}

/** Bandingkan nilai tampil & warna latar transit vs asli untuk tab yang ada di keduanya. */
function verifyTransit() {
  var src = SpreadsheetApp.openById(TRANSIT_SOURCE_ID);
  var dst = SpreadsheetApp.openById(TRANSIT_TARGET_ID);
  var report = [];
  dst.getSheets().forEach(function (t) {
    var s = src.getSheetByName(t.getName());
    if (!s || !TRANSIT_TAB_RE.test(t.getName())) return;
    var rows = Math.max(s.getLastRow(), t.getLastRow());
    var cols = Math.max(s.getLastColumn(), t.getLastColumn());
    var a = s.getRange(1, 1, rows, cols), b = t.getRange(1, 1, rows, cols);
    var av = a.getDisplayValues(), bv = b.getDisplayValues();
    var ab = a.getBackgrounds(), bb = b.getBackgrounds();
    var diffValues = 0, diffColors = 0, first = [];
    for (var i = 0; i < rows; i++) {
      for (var j = 0; j < cols; j++) {
        var dv = av[i][j] !== bv[i][j], dc = ab[i][j] !== bb[i][j];
        if (dv) diffValues++;
        if (dc) diffColors++;
        if ((dv || dc) && first.length < 5) first.push(String.fromCharCode(65 + j) + (i + 1));
      }
    }
    report.push(t.getName() + ": " + rows + " baris x " + cols + " kolom, beda nilai " + diffValues +
      ", beda warna " + diffColors + (first.length ? " (contoh: " + first.join(" ") + ")" : ""));
  });
  Logger.log(report.join("\n"));
  return report;
}
