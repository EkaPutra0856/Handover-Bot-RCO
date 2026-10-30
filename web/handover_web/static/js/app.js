(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const CATS = ["pending", "progress", "done"];
  const CAT_LABEL = { pending: "Pending", progress: "On Progress", done: "Done" };
  const DONE_REASON = { status: "status selesai", pic: "PIC berisi done", hijau: "baris hijau" };
  const PAGE = 300;
  const STORE = "handover-web-filters-v1";

  const st = {
    config: null, data: null, loading: false, error: "",
    start: "", end: "", preset: "month",
    teams: [], cats: ["pending", "progress"], orange: false, q: "",
    sort: { key: "tanggal", dir: 1 }, limit: PAGE,
    detail: false, split: false,
  };

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const parseIso = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const fmtDate = (s) => { const [y, m, d] = s.split("-"); return `${d}/${m}/${y}`; };
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

  function presetRange(p) {
    const t = parseIso(st.config.today);
    const monday = addDays(t, -((t.getDay() + 6) % 7));
    switch (p) {
      case "today": return [t, t];
      case "yesterday": return [addDays(t, -1), addDays(t, -1)];
      case "week": return [monday, t];
      case "lastweek": return [addDays(monday, -7), addDays(monday, -1)];
      case "month": return [new Date(t.getFullYear(), t.getMonth(), 1), t];
      case "lastmonth": return [new Date(t.getFullYear(), t.getMonth() - 1, 1), new Date(t.getFullYear(), t.getMonth(), 0)];
    }
  }

  // ---------- state persistence ----------
  function save() {
    try {
      localStorage.setItem(STORE, JSON.stringify({ preset: st.preset, start: st.start, end: st.end, teams: st.teams, cats: st.cats,
        orange: st.orange, sort: st.sort, detail: st.detail, split: st.split, auto: $("#auto").checked }));
    } catch (e) { /* storage tidak tersedia */ }
  }
  function restore() {
    try { return JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) { return null; }
  }

  // ---------- api ----------
  async function api(path, body) {
    const opt = body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
    let r;
    try { r = await fetch(path, opt); } catch (e) { throw new Error("Server web tidak bisa dihubungi"); }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
    return data;
  }

  let reqId = 0;
  async function load(refresh = false) {
    if (!st.start || !st.end) return;
    const id = ++reqId;
    st.loading = true; st.error = "";
    render();
    $("#table-card").classList.add("loading");
    $("#refresh").disabled = true;
    try {
      const data = await api(`/api/issues?start=${st.start}&end=${st.end}${refresh ? "&refresh=1" : ""}`);
      if (id !== reqId) return;
      st.data = data; st.limit = PAGE;
    } catch (e) {
      if (id !== reqId) return;
      st.error = e.message;
    } finally {
      if (id === reqId) {
        st.loading = false;
        $("#table-card").classList.remove("loading");
        $("#refresh").disabled = false;
        render();
      }
    }
  }

  // ---------- filtering ----------
  function matchesBase(i) {
    if (!st.teams.includes(i.team)) return false;
    if (st.orange && !i.waiting_external) return false;
    if (st.q) {
      const q = st.q.toLowerCase();
      const hay = `${i.issue_no} ${i.aplikasi} ${i.pic} ${i.status} ${i.team} ${i.label}`.toLowerCase();
      if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  }
  const visibleRows = () => (st.data?.issues || []).filter((i) => matchesBase(i) && st.cats.includes(i.category));

  function sorted(rows) {
    const { key, dir } = st.sort;
    const teamIdx = (t) => st.config.teams.indexOf(t);
    const val = (i) => key === "team" ? teamIdx(i.team) : key === "category" ? CATS.indexOf(i.category)
      : key === "issue_no" ? i.issue_no : String(i[key] ?? "").toLowerCase();
    return rows.slice().sort((a, b) => {
      const x = val(a), y = val(b);
      if (x < y) return -dir; if (x > y) return dir;
      return a.tanggal < b.tanggal ? -1 : a.tanggal > b.tanggal ? 1 : a.issue_no - b.issue_no;
    });
  }

  // ---------- render ----------
  const COLS = [
    { key: "tanggal", label: "Tanggal" },
    { key: "issue_no", label: "Issue" },
    { key: "team", label: "Tim" },
    { key: "aplikasi", label: "Aplikasi" },
    { key: "label", label: "PIC / Status" },
    { key: "category", label: "Kategori" },
    { key: null, label: "" },
  ];

  function renderHead() {
    $("#thead").innerHTML = COLS.map((c) => {
      if (!c.key) return '<th style="width:44px;cursor:default"></th>';
      const on = st.sort.key === c.key;
      return `<th data-k="${c.key}" class="${on ? "sorted" : ""}">${c.label} <span class="arr">${on ? (st.sort.dir > 0 ? "▲" : "▼") : "▲▼"}</span></th>`;
    }).join("");
  }

  function catBadge(i) {
    const tip = i.category === "done" && i.done_reason ? ` title="Done karena ${esc(DONE_REASON[i.done_reason] || i.done_reason)}"` : "";
    let html = `<span class="badge ${i.category}"${tip}><span class="dot ${i.category}"></span>${CAT_LABEL[i.category]}</span>`;
    if (i.waiting_external) html += ` <span class="badge orange" title="Menunggu tindak lanjut eksternal">Eksternal</span>`;
    return html;
  }

  function renderTable(rows) {
    const shown = rows.slice(0, st.limit);
    // Nama tab hanya perlu ditampilkan kalau periode mencakup lebih dari satu bulan.
    const multiTab = new Set((st.data?.issues || []).map((i) => i.sheet)).size > 1;
    $("#tbody").innerHTML = shown.map((i) => {
      const who = i.pic ? esc(i.pic) : (i.category === "pending" ? '<span class="muted">—</span>' : `<span class="muted">${esc(i.status || i.team)}</span>`);
      const rc = i.waiting_external ? "r-orange" : `r-${i.category}`;
      return `<tr class="${rc}">
        <td class="mono">${fmtDate(i.tanggal)}</td>
        <td class="mono issue-no">${i.issue_no}${multiTab ? `<div class="muted" style="font-size:11.5px;font-weight:400;white-space:nowrap">${esc(i.sheet.replace(/^Issue\s+/i, ""))}</div>` : ""}</td>
        <td><span class="team-tag">${esc(i.team)}</span></td>
        <td>${esc(i.aplikasi) || '<span class="muted">—</span>'}</td>
        <td>${who}</td>
        <td class="cat-cell">${catBadge(i)}</td>
        <td><a class="open-link" href="${esc(i.link)}" target="_blank" rel="noopener" title="Buka baris ${i.issue_no} di spreadsheet">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg></a></td>
      </tr>`;
    }).join("");
    const empty = $("#empty");
    empty.hidden = rows.length > 0 || st.loading;
    if (!rows.length) empty.innerHTML = st.data ? "Tidak ada issue yang cocok dengan filter." : "";
    const more = rows.length - shown.length;
    $("#more").hidden = more <= 0;
    if (more > 0) $("#more-btn").textContent = `Tampilkan ${Math.min(more, PAGE)} lagi (sisa ${more})`;
  }

  function renderStats(base) {
    if (!st.data) {
      $("#stats").innerHTML = CATS.concat("total").map((c) =>
        `<div class="card stat ${c}"><div class="l">${CAT_LABEL[c] || "Total issue"}</div><div class="n muted">…</div><div class="pct">&nbsp;</div></div>`).join("");
      return;
    }
    const n = (c) => base.filter((i) => i.category === c).length;
    const total = base.length || 1;
    $("#stats").innerHTML = CATS.map((c) => `
      <button class="card stat ${c} ${st.cats.includes(c) ? "" : "off"}" data-c="${c}" title="Klik untuk tampilkan/sembunyikan ${CAT_LABEL[c]}">
        <div class="l"><span class="dot ${c}"></span>${CAT_LABEL[c]}</div>
        <div class="n">${n(c)}</div>
        <div class="pct">${Math.round((n(c) / total) * 100)}% dari total</div>
      </button>`).join("") + `
      <div class="card stat total">
        <div class="l">Total issue</div>
        <div class="n">${base.length}</div>
        <div class="pct">${st.start ? `${fmtDate(st.start)}${st.start !== st.end ? " – " + fmtDate(st.end) : ""}` : ""}</div>
      </div>`;
  }

  function renderTeams() {
    const all = (st.data?.issues || []).filter((i) => (!st.orange || i.waiting_external));
    $("#teams").innerHTML = st.config.teams.map((t) => {
      const rows = all.filter((i) => i.team === t);
      const c = Object.fromEntries(CATS.map((k) => [k, rows.filter((i) => i.category === k).length]));
      const tot = rows.length || 1;
      return `<div class="team-row ${st.teams.includes(t) ? "" : "off"}" data-t="${esc(t)}" title="Klik: tampilkan hanya ${esc(t)}. Shift+klik: tambah/kurangi">
        <div class="tr-h"><b>${esc(t)}</b><span class="muted">${c.pending} pending · ${c.progress} progress · ${c.done} done</span></div>
        <div class="bar">${CATS.map((k) => `<span class="b-${k}" style="width:${(c[k] / tot) * 100}%"></span>`).join("")}</div>
      </div>`;
    }).join("");
  }

  function renderApps(base) {
    const counts = {};
    base.filter((i) => i.category !== "done").forEach((i) => { const a = i.aplikasi || "(tanpa nama)"; counts[a] = (counts[a] || 0) + 1; });
    const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);
    $("#apps").innerHTML = top.length ? top.map(([a, n]) => `
      <div class="app-row" data-app="${esc(a)}" title="Cari ${esc(a)}"><span class="app-name">${esc(a)}</span><span class="app-count">${n}</span></div>`).join("")
      : '<div class="muted" style="padding:8px 0">Tidak ada issue yang belum selesai.</div>';
  }

  function renderMessages() {
    let html = "";
    if (st.error) html += `<div class="error">⚠️ ${esc(st.error)}</div>`;
    for (const w of st.data?.warnings || []) html += `<div class="warn">⚠️ ${esc(w)}</div>`;
    $("#msg-area").innerHTML = html;
  }

  function render() {
    document.querySelectorAll("#presets button").forEach((b) => b.classList.toggle("on", b.dataset.p === st.preset));
    $("#start").value = st.start; $("#end").value = st.end;
    document.querySelectorAll("#team-chips .chip").forEach((b) => b.classList.toggle("on", st.teams.includes(b.dataset.t)));
    document.querySelectorAll("#cat-chips .chip").forEach((b) => b.classList.toggle("on", st.cats.includes(b.dataset.c)));
    $("#only-orange").classList.toggle("on", st.orange);
    renderMessages();
    if (st.loading) {
      $("#fetched").innerHTML = '<span class="spin"></span> Mengambil data…';
    } else if (st.data) {
      const t = new Date(st.data.fetched_at);
      $("#fetched").textContent = `Data diambil ${t.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}`;
    } else {
      $("#fetched").textContent = st.error ? "Gagal mengambil data" : "";
    }
    const base = (st.data?.issues || []).filter(matchesBase);
    const rows = sorted(base.filter((i) => st.cats.includes(i.category)));
    renderHead();
    renderStats(base);
    renderTable(rows);
    renderTeams();
    renderApps(base);
    $("#count").textContent = st.data ? `${rows.length} issue` : "";
    $("#export").disabled = !st.data || !st.cats.length || !st.teams.length;
    $("#csv").disabled = !rows.length;
    save();
  }

  // ---------- export modal ----------
  let previewReq = 0, lastMessages = [];
  function exportBody() {
    return { start: st.start, end: st.end, categories: st.cats, teams: st.teams, detail: st.detail, split: st.split,
      keys: visibleRows().map((i) => i.key) };
  }
  async function preview() {
    const id = ++previewReq;
    $("#preview").innerHTML = '<div class="bubble"><span class="spin"></span> Menyusun pesan…</div>';
    $("#send").disabled = true; $("#copy").disabled = true;
    hideConfirm();
    try {
      const data = await api("/api/preview", exportBody());
      if (id !== previewReq) return;
      lastMessages = data.messages;
      const now = new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
      $("#preview").innerHTML = data.messages.map((m) =>
        `<div class="bubble"><div class="bot-name">Handover Bot</div>${m}<span class="bmeta">${now}</span></div>`).join("");
      const chat = data.chat;
      $("#target").innerHTML = chat ? `Tujuan: <b>${esc(chat.title || "Chat")}</b> <span class="mono">(${chat.id})</span>` : "Tujuan Telegram belum diatur di .env";
      $("#opt-info").textContent = `${data.messages.length} pesan · ${visibleRows().length} issue`;
      $("#send").disabled = !chat; $("#copy").disabled = false;
    } catch (e) {
      if (id !== previewReq) return;
      $("#preview").innerHTML = `<div class="bubble" style="color:var(--danger)">❌ ${esc(e.message)}</div>`;
    }
  }
  function openModal() {
    $("#opt-detail").checked = st.detail; $("#opt-split").checked = st.split;
    $("#modal").classList.add("show");
    preview();
  }
  function closeModal() { $("#modal").classList.remove("show"); hideConfirm(); }
  function hideConfirm() { $("#confirm").classList.remove("show"); }

  function plainText(html) {
    const d = document.createElement("div");
    d.innerHTML = html;
    return d.textContent;
  }

  async function send() {
    const btn = $("#confirm-yes");
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Mengirim…';
    try {
      const r = await api("/api/send", exportBody());
      closeModal();
      toast(`✅ ${r.sent} pesan terkirim ke ${r.chat.title || r.chat.id}`);
    } catch (e) {
      toast(`❌ ${e.message}`, true);
    } finally {
      btn.disabled = false; btn.textContent = "Ya, kirim sekarang";
    }
  }

  // ---------- csv ----------
  function downloadCsv() {
    const rows = sorted(visibleRows());
    const cell = (v) => {
      let s = String(v ?? "");
      if (/^[=+\-@]/.test(s)) s = "'" + s;  // cegah formula injection di Excel
      return /[;"\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const head = ["Tanggal", "Tab", "Issue", "Tim", "Aplikasi", "PIC", "Status", "Kategori", "Menunggu Eksternal", "Link"];
    const lines = [head, ...rows.map((i) => [fmtDate(i.tanggal), i.sheet, i.issue_no, i.team, i.aplikasi, i.pic, i.status,
      CAT_LABEL[i.category], i.waiting_external ? "Ya" : "", i.link])].map((r) => r.map(cell).join(";"));
    const blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `handover_${st.start}_${st.end}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  let toastTimer;
  function toast(text, err = false) {
    const t = $("#toast");
    t.textContent = text; t.classList.toggle("err", err); t.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), 3500);
  }

  // ---------- events ----------
  function setPreset(p) {
    const [a, b] = presetRange(p);
    st.preset = p; st.start = iso(a); st.end = iso(b);
    load();
  }
  function bind() {
    $("#presets").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setPreset(b.dataset.p); });
    const onDate = () => {
      const s = $("#start").value, e = $("#end").value;
      if (!s || !e) return;
      st.preset = ""; st.start = s <= e ? s : e; st.end = s <= e ? e : s;
      load();
    };
    $("#start").addEventListener("change", onDate);
    $("#end").addEventListener("change", onDate);

    $("#team-chips").addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      const t = b.dataset.t;
      st.teams = st.teams.includes(t) ? st.teams.filter((x) => x !== t) : st.config.teams.filter((x) => x === t || st.teams.includes(x));
      st.limit = PAGE; render();
    });
    const toggleCat = (c) => {
      st.cats = st.cats.includes(c) ? st.cats.filter((x) => x !== c) : CATS.filter((x) => x === c || st.cats.includes(x));
      st.limit = PAGE; render();
    };
    $("#cat-chips").addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) toggleCat(b.dataset.c); });
    $("#stats").addEventListener("click", (e) => { const b = e.target.closest(".stat[data-c]"); if (b) toggleCat(b.dataset.c); });
    $("#only-orange").addEventListener("click", () => { st.orange = !st.orange; st.limit = PAGE; render(); });
    $("#teams").addEventListener("click", (e) => {
      const r = e.target.closest(".team-row"); if (!r) return;
      const t = r.dataset.t;
      if (e.shiftKey) st.teams = st.teams.includes(t) ? st.teams.filter((x) => x !== t) : st.config.teams.filter((x) => x === t || st.teams.includes(x));
      else st.teams = st.teams.length === 1 && st.teams[0] === t ? st.config.teams.slice() : [t];
      st.limit = PAGE; render();
    });
    $("#apps").addEventListener("click", (e) => {
      const r = e.target.closest(".app-row"); if (!r || r.dataset.app === "(tanpa nama)") return;
      st.q = r.dataset.app; $("#q").value = st.q; st.limit = PAGE; render();
    });
    let qTimer;
    $("#q").addEventListener("input", (e) => { clearTimeout(qTimer); qTimer = setTimeout(() => { st.q = e.target.value.trim(); st.limit = PAGE; render(); }, 150); });
    $("#reset").addEventListener("click", () => {
      st.teams = st.config.teams.slice(); st.cats = ["pending", "progress"]; st.orange = false; st.q = ""; $("#q").value = "";
      st.sort = { key: "tanggal", dir: 1 };
      setPreset("month");
    });
    $("#thead").addEventListener("click", (e) => {
      const th = e.target.closest("th[data-k]"); if (!th) return;
      const k = th.dataset.k;
      st.sort = { key: k, dir: st.sort.key === k ? -st.sort.dir : 1 };
      render();
    });
    $("#more-btn").addEventListener("click", () => { st.limit += PAGE; render(); });
    $("#refresh").addEventListener("click", () => load(true));
    $("#csv").addEventListener("click", downloadCsv);
    $("#export").addEventListener("click", openModal);
    $("#x").addEventListener("click", closeModal);
    $("#close").addEventListener("click", closeModal);
    $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
    $("#opt-detail").addEventListener("change", (e) => { st.detail = e.target.checked; save(); preview(); });
    $("#opt-split").addEventListener("change", (e) => { st.split = e.target.checked; save(); preview(); });
    $("#copy").addEventListener("click", async () => {
      const text = lastMessages.map(plainText).join("\n\n");
      try { await navigator.clipboard.writeText(text); toast("📋 Teks disalin"); }
      catch (e) { toast("Browser menolak akses clipboard", true); }
    });
    $("#send").addEventListener("click", () => {
      const chat = $("#target b")?.textContent || "Telegram";
      $("#confirm-text").innerHTML = `Kirim <b>${lastMessages.length} pesan</b> ke <b>${esc(chat)}</b>?`;
      $("#confirm").classList.add("show");
    });
    $("#confirm-no").addEventListener("click", hideConfirm);
    $("#confirm-yes").addEventListener("click", send);

    let autoTimer;
    const setAuto = () => { clearInterval(autoTimer); if ($("#auto").checked) autoTimer = setInterval(() => load(true), 5 * 60 * 1000); save(); };
    $("#auto").addEventListener("change", setAuto);
    setAuto();

    document.addEventListener("keydown", (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
      if (e.key === "Escape" && $("#modal").classList.contains("show")) return closeModal();
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "/") { e.preventDefault(); $("#q").focus(); }
      else if (e.key === "r" || e.key === "R") load(true);
      else if (e.key === "e" || e.key === "E") { if (!$("#export").disabled) openModal(); }
    });
  }

  async function init() {
    try {
      st.config = await api("/api/config");
    } catch (e) {
      $("#msg-area").innerHTML = `<div class="error">⚠️ ${esc(e.message)}</div>`;
      $("#fetched").textContent = "Gagal memuat";
      return;
    }
    $("#title").textContent = st.config.title;
    document.title = st.config.title;
    $("#sheet-link").href = st.config.sheet_url;
    $("#team-chips").innerHTML = st.config.teams.map((t) => `<button class="chip" data-t="${esc(t)}">${esc(t)}</button>`).join("");
    st.teams = st.config.teams.slice();

    const saved = restore();
    if (saved) {
      st.teams = (saved.teams || st.teams).filter((t) => st.config.teams.includes(t));
      st.cats = (saved.cats || st.cats).filter((c) => CATS.includes(c));
      st.orange = !!saved.orange; st.detail = !!saved.detail; st.split = !!saved.split;
      if (saved.sort?.key) st.sort = saved.sort;
      $("#auto").checked = !!saved.auto;
    }
    bind();
    if (saved?.preset) setPreset(saved.preset);
    else if (saved?.start && saved?.end) { st.preset = ""; st.start = saved.start; st.end = saved.end; load(); }
    else setPreset("month");
  }
  init();
})();
