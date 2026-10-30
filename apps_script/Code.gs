/**
 * Web App pembaca spreadsheet issue untuk Bot Handover.
 *
 * Deploy (login sebagai akun yang punya akses spreadsheet sumber, mis. ravicraft700@gmail.com):
 *   1. https://script.google.com -> New project, tempel file ini.
 *   2. Ganti SECRET_KEY dengan nilai APPS_SCRIPT_KEY di .env bot.
 *   3. Deploy -> New deployment -> Web app
 *        Execute as: Me
 *        Who has access: Anyone
 *   4. Authorize, lalu salin URL Web App ke APPS_SCRIPT_URL di .env.
 *
 * Endpoint:
 *   ?key=...&action=titles               -> { ok, titles: [...] }
 *   ?key=...&action=fetch&tabs=["Issue Oktober 2026"]
 *        -> { ok, sheets: [{ title, values: [[...]], backgrounds: [["#rrggbb", ...]] }] }
 *   ?key=...&action=sync[&all=1]        -> sinkron spreadsheet transit
 *   ?key=...&action=verify              -> bandingkan transit vs sheet asli
 */

const SPREADSHEET_ID = "1lmIgK_GMZaeRUUc0Ea_K31jpRAn_P_PifWsm5PvjJsw";
const SECRET_KEY = "GANTI_DENGAN_APPS_SCRIPT_KEY";
const MAX_COLUMNS = 17; // kolom A-Q

function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.key !== SECRET_KEY) {
    return json_({ ok: false, error: "unauthorized" });
  }
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    if (p.action === "titles") {
      return json_({ ok: true, titles: ss.getSheets().map(function (s) { return s.getName(); }) });
    }
    // Spreadsheet transit (lihat TransitSync.gs); sheet asli hanya dibaca.
    if (p.action === "sync") {
      return json_({ ok: true, synced: p.all === "1" ? syncTransitAll() : syncTransit() });
    }
    if (p.action === "verify") {
      return json_({ ok: true, report: verifyTransit() });
    }
    if (p.action === "fetch") {
      const tz = ss.getSpreadsheetTimeZone();
      const tabs = JSON.parse(p.tabs || "[]");
      const sheets = [];
      tabs.forEach(function (name) {
        const sh = ss.getSheetByName(name);
        if (!sh) return;
        const rows = sh.getLastRow();
        const cols = Math.min(sh.getLastColumn(), MAX_COLUMNS);
        if (rows < 1 || cols < 1) {
          sheets.push({ title: name, values: [], backgrounds: [] });
          return;
        }
        const range = sh.getRange(1, 1, rows, cols);
        const values = range.getValues().map(function (row) {
          return row.map(function (v) { return cellValue_(v, tz); });
        });
        sheets.push({ title: name, values: values, backgrounds: range.getBackgrounds() });
      });
      return json_({ ok: true, sheets: sheets });
    }
    return json_({ ok: false, error: "unknown action" });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

// Tanggal dikirim sebagai "yyyy-MM-dd" sesuai zona waktu spreadsheet; sel jam saja (tahun 1899) dikosongkan.
function cellValue_(v, tz) {
  if (v instanceof Date) {
    if (v.getFullYear() < 1900) return "";
    return Utilities.formatDate(v, tz, "yyyy-MM-dd");
  }
  return v;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
