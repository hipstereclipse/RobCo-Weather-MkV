(function() {
  const PATHS = ["USER/WEATHER.JSON", "WEATHER.JSON", "USER/WEATHER.json"];
  const TABS = ["ATMOS", "5-DAY", "SOLAR"];
  const CORN = 56; // horizontal inset for the top/bottom rows so the rounded
                   // display corners do not clip the header/footer text. Bump
                   // this higher still if a unit's glass is even more rounded.
  const st = { d: null, e: null, l: 0, t: 0, m: 0, a: 0, f: 0, k: 0 };

  function num(v) { return v === undefined || v === null ? "--" : Math.round(v) + ""; }
  function unit() { return st.d && st.d.units && st.d.units.temp || "F"; }
  function cut(s, n) {
    s = s === undefined || s === null ? "--" : "" + s;
    return s.length > n ? s.substr(0, n) : s;
  }
  function font(n) {
    if (n === 3) { h.setFont("Monofonto23", 2); return; }
    if (n === 2) { h.setFont("Monofonto23"); return; }
    h.setFont("6x8", n === 1 ? 2 : 1);
  }
  function text(s, x, y, ax, ay) {
    h.setFontAlign(ax === undefined ? 0 : ax, ay === undefined ? -1 : ay);
    h.drawString(s, x, y);
  }
  function box(x0, y0, x1, y1, label) {
    h.drawRect(x0, y0, x1, y1);
    if (label) {
      font(0);
      h.clearRect(x0 + 7, y0, x0 + 15 + label.length * 6, y0 + 8);
      text(" " + label + " ", x0 + 9, y0 - 1, -1, -1);
    }
  }
  function gauge(x, y, w, v, max) {
    h.drawRect(x, y, x + w, y + 6);
    if (v === undefined || v === null || !isFinite(v)) return;
    const f = E.clip(Math.round((w - 2) * v / max), 0, w - 2);
    if (f > 0) h.fillRect(x + 1, y + 1, x + f, y + 5);
  }
  function scanMask() {
    for (let y = 33; y < 288; y += 8) h.clearRect(8, y, 472, y);
  }
  function hr(y) { h.drawLine(12, y, 468, y); }
  function stamp(s) {
    if (!s) return "";
    s = ("" + s).replace("T", " ");
    return s.length >= 16 ? s.substr(5, 11) : s;
  }
  function kpLabel(sp, i) {
    if (sp && sp.kpt && sp.kpt[i]) {
      const s = "" + sp.kpt[i];
      const m = s.match(/^(\d\d\/\d\d)[ T](\d\d)(?::\d\d)?Z?$/i);
      if (m) {
        let hour = +m[2];
        const ap = hour >= 12 ? "PM" : "AM";
        hour = hour % 12;
        if (hour === 0) hour = 12;
        return m[1] + " " + hour + " " + ap + " UTC";
      }
      return s.replace(/Z$/i, " UTC").toUpperCase();
    }
    return "T+" + (i * 3) + "H";
  }
  function ageHours() {
    if (!st.d || !st.d.epoch) return null;
    const a = (Date.now() / 1000 - st.d.epoch) / 3600;
    return isFinite(a) && a >= 0 ? a : null;
  }
  function stale() {
    const a = ageHours();
    return a !== null && a > 12;
  }
  function ageLabel(a) {
    if (a === null) return "?";
    if (a < 1) return "<1H";
    return a < 48 ? Math.round(a) + "H" : Math.round(a / 24) + "D";
  }

  function load() {
    st.d = null;
    st.e = null;
    let f;
    for (let i = 0; i < PATHS.length && !f; i++) f = E.openFile(PATHS[i], "r");
    if (!f) { st.e = "NO WEATHER DATA"; return; }
    const txt = f.read(5601);
    f.close();
    if (!txt) { st.e = "NO WEATHER DATA"; return; }
    if (txt.length > 5600) { st.e = "DATA TOO LARGE"; return; }
    try {
      const d = JSON.parse(txt);
      if (!d || !d.locations || !d.locations.length) { st.e = "EMPTY DATA FILE"; return; }
      st.d = d;
      if (st.l >= d.locations.length) st.l = 0;
    } catch (e) {
      st.e = "BAD DATA FORMAT";
    }
  }

  function itemCount(loc) {
    if (st.t === 0) return 4;
    if (st.t === 1) {
      const n = loc && loc.daily ? loc.daily.length : 0;
      return E.clip(n, 1, 5);
    }
    const sp = st.d && st.d.space;
    const n = sp && sp.kpf ? sp.kpf.length : 0;
    return E.clip(n, 1, 24);
  }
  function sel() {
    return st.t === 0 ? st.a : st.t === 1 ? st.f : st.k;
  }
  function setSel(v, loc) {
    const n = itemCount(loc);
    v = (v + n) % n;
    if (st.t === 0) st.a = v;
    else if (st.t === 1) st.f = v;
    else st.k = v;
  }
  function clampSel(loc) { setSel(sel(), loc); }
  function hilite(x0, y0, x1, y1, on) {
    if (on) h.drawRect(x0, y0, x1, y1);
  }
  function header() {
    font(0);
    if (st.d && stale()) text("! CACHE " + ageLabel(ageHours()) + " OLD - SYNC", CORN, 10, -1, -1);
    else text("ROBCO INDUSTRIES (TM) TERMLINK", CORN, 10, -1, -1);
    if (st.d) {
      const n = st.m ? itemCount(st.d.locations[st.l] || {}) : st.d.locations.length;
      text((st.m ? "ITEM [" + (sel() + 1) : "SITE [" + (st.l + 1)) + "/" + n + "]", 480 - CORN, 10, 1, -1);
    }
    hr(24);
  }
  function footer() {
    const y = 294;
    hr(y - 6);
    font(0);
    text(st.m ? "WHEEL:ITEM PUSH:SITE K2:VIEW" : "WHEEL:SITE PUSH:ITEM K2:VIEW", CORN, y, -1, -1);
    if (st.d && st.d.generated) text((stale() ? "! " : "UPD ") + stamp(st.d.generated), 480 - CORN, y, 1, -1);
  }
  function title(loc) {
    font(1);
    text(cut((loc.name || "UNKNOWN").toUpperCase(), 24), CORN, 32, -1, -1);
    font(0);
    if (loc.region) text(cut((loc.region || "").toUpperCase(), 30), CORN, 51, -1, -1);
    text("SITE 0x" + (0xA100 + st.l * 0x23).toString(16).toUpperCase(), 480 - CORN, 51, 1, -1);
  }
  function tabs() {
    const y = 66, bw = 456 / TABS.length;
    font(0);
    for (let i = 0; i < TABS.length; i++) {
      const x = 12 + i * bw;
      if (i === st.t) h.drawRect(x + 2, y, x + bw - 2, y + 15);
      text((i === st.t ? "> " : "  ") + TABS[i], x + bw / 2, y + 8, 0, 0);
    }
    hr(85);
  }
  function msg(a, b) {
    font(2);
    text(a, 240, 142, 0, 0);
    font(1);
    if (b) text(b, 240, 180, 0, 0);
  }

  function degree(x, y) {
    h.drawCircle(x + 5, y + 4, 4);
    font(1);
    text(unit(), x + 14, y + 6, -1, 0);
  }
  function thick(x0, y0, x1, y1) {
    h.drawLine(x0, y0, x1, y1);
    h.drawLine(x0 + 1, y0, x1 + 1, y1);
  }
  function sun(cx, cy, r) {
    const d = r + 10, s = r + 3, q = r / 2;
    h.drawCircle(cx, cy, r);
    h.drawCircle(cx, cy, r - 3);
    thick(cx - d, cy, cx - s, cy);
    thick(cx + s, cy, cx + d, cy);
    thick(cx, cy - d, cx, cy - s);
    thick(cx, cy + s, cx, cy + d);
    thick(cx - q - 5, cy - q - 5, cx - q, cy - q);
    thick(cx + q, cy - q, cx + q + 5, cy - q - 5);
    thick(cx - q - 5, cy + q + 5, cx - q, cy + q);
    thick(cx + q, cy + q, cx + q + 5, cy + q + 5);
  }
  function cloud(cx, cy, r) {
    h.drawCircle(cx - r / 2, cy + 2, r / 2);
    h.drawCircle(cx + r / 2, cy + 2, r / 2);
    h.drawCircle(cx, cy - 4, r / 2 + 3);
    thick(cx - r, cy + r / 2 + 2, cx + r, cy + r / 2 + 2);
  }
  function wxIcon(code, cx, cy, r) {
    code = code || 0;
    if (code === 0) sun(cx, cy, r);
    else if (code < 3) { sun(cx - r / 2, cy - r / 2, Math.max(5, r / 2)); cloud(cx + 4, cy + 3, r); }
    else cloud(cx, cy, r);
    if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) {
      for (let i = -1; i <= 1; i++) {
        const x = cx + i * 8;
        thick(x, cy + r, x - 4, cy + r + 12);
      }
    } else if ((code >= 71 && code <= 77) || (code >= 85 && code <= 86)) {
      for (let i = -1; i <= 1; i++) {
        const x = cx + i * 8;
        thick(x - 4, cy + r + 6, x + 4, cy + r + 6);
        thick(x, cy + r + 2, x, cy + r + 10);
      }
    } else if (code >= 95) {
      thick(cx, cy + r - 3, cx - 6, cy + r + 9);
      thick(cx - 6, cy + r + 9, cx + 2, cy + r + 5);
      thick(cx + 2, cy + r + 5, cx - 1, cy + r + 15);
    } else if (code === 45 || code === 48) {
      for (let i = 0; i < 3; i++) thick(cx - r, cy + r + i * 6, cx + r, cy + r + i * 6);
    }
  }
  function rowAt(label, val, xL, xR, y) {
    font(0);
    text(label, xL, y, -1, 0);
    font(1);
    text(val, xR, y, 1, 0);
  }
  function metricAt(label, val, x, y) {
    font(0);
    text(label, x, y, 0, -1);
    font(1);
    text(val, x, y + 17, 0, 0);
  }
  function solarLine(loc) {
    const sp = st.d.space, au = loc.aurora;
    if (!sp) return "";
    let s = "SOLAR " + (sp.flare || "QUIET");
    if (sp.g_scale && sp.g_scale !== "G0") s += " " + sp.g_scale;
    if (au && au.chance && au.chance !== "UNLIKELY") s += "  AURORA " + au.chance;
    return s;
  }
  function current(loc) {
    const c = loc.current || {}, d0 = (loc.daily && loc.daily[0]) || {};
    box(14, 96, 236, 246, "LOCAL ATMOS");
    box(248, 96, 466, 246, "INSTRUMENTS");

    wxIcon(c.code, 70, 136, 24);
    font(3);
    h.setFontAlign(-1, 0);
    h.drawString(num(c.temp), 118, 144);
    degree(205, 124);

    font(0);
    text("> CONDITION", 24, 181, -1, -1);
    if (c.time) text("OBS " + stamp(c.time), 226, 181, 1, -1);
    font(1);
    text(cut((c.desc || "--").toUpperCase(), 18), 24, 199, -1, -1);
    metricAt("HI", num(d0.hi), 52, 216);
    metricAt("LO", num(d0.lo), 114, 216);
    metricAt("RAIN", num(d0.pop) + "%", 186, 216);

    hilite(254, 104, 460, 127, st.t === 0 && st.a === 0);
    rowAt("FEELS", num(c.feels) + unit(), 262, 454, 116);
    hilite(254, 134, 460, 157, st.t === 0 && st.a === 1);
    rowAt("WIND", num(c.wind) + (c.dir ? " " + c.dir : ""), 262, 454, 146);
    hilite(254, 164, 460, 193, st.t === 0 && st.a === 2);
    rowAt("HUMID", num(c.humidity) + "%", 262, 454, 176);
    gauge(262, 188, 192, c.humidity, 100);
    hilite(254, 202, 460, 233, st.t === 0 && st.a === 3);
    rowAt("RAD UV", num(c.uv), 262, 454, 214);
    gauge(262, 226, 192, c.uv, 11);

    let detail;
    if (st.a === 0) detail = "FEELS " + num(c.feels) + unit() + "  ACTUAL " + num(c.temp) + unit();
    else if (st.a === 1) detail = "WIND " + num(c.wind) + (c.dir ? " " + c.dir : "") + " " + ((st.d.units && st.d.units.wind) || "");
    else if (st.a === 2) detail = "HUMID " + num(c.humidity) + "%  RAIN " + num(d0.pop) + "%";
    else detail = "UV " + num(c.uv) + "  " + (solarLine(loc) || "SOLAR QUIET");
    box(14, 250, 466, 282, "SELECTED TELEMETRY");
    font(1);
    text(cut(detail, 36), 24, 266, -1, 0);
  }

  function forecast(loc) {
    const days = loc.daily || [], n = Math.min(days.length, 5), cw = 456 / 5;
    if (st.f >= n && n > 0) st.f = n - 1;
    box(14, 96, 466, 222, "FORECAST BUFFER");
    font(0);
    text("5 ENTRIES  //  SELECT DAY WITH WHEEL", 26, 111, -1, -1);
    for (let i = 0; i < n; i++) {
      const d = days[i] || {};
      const x = 12 + i * cw;
      const cx = x + cw / 2;
      if (i > 0) h.drawLine(x, 126, x, 216);
      hilite(x + 4, 122, x + cw - 4, 216, i === st.f);
      font(1);
      text(d.d || ("D" + (i + 1)), cx, 134, 0, -1);
      wxIcon(d.code, cx, 169, 10);
      font(0);
      text(cut((d.desc || "--").toUpperCase(), 9), cx, 192, 0, -1);
      text(num(d.hi) + "/" + num(d.lo) + " " + num(d.pop) + "%", cx, 207, 0, -1);
    }
    const d = days[st.f] || {};
    box(14, 232, 466, 282, "ENTRY DETAIL");
    font(1);
    text(cut((d.date || d.d || ("D" + (st.f + 1))) + "  " +
      (d.desc || "--").toUpperCase(), 36), 24, 249, -1, -1);
    text("HI/LO " + num(d.hi) + "/" + num(d.lo), 24, 272, -1, 0);
    text("RAIN " + num(d.pop) + "%", 456, 272, 1, 0);
  }

  function kpGraph(sp, loc, x0, y0, x1, y1) {
    const k = sp.kpf || [], base = y1, span = y1 - (y0 + 5);
    if (!k.length) return;
    const need = loc.aurora && loc.aurora.needed !== undefined ? loc.aurora.needed : 99;
    font(0);
    text("KP", x0 - 18, y0 - 8, -1, -1);
    h.drawLine(x0, y0, x0, y1);
    h.drawLine(x0, y1, x1, y1);
    text("0", x0 - 4, base, 1, 0);
    for (let v = 3; v <= 9; v += 3) {
      const y = base - v / 9 * span;
      text("" + v, x0 - 4, y, 1, 0);
      h.drawLine(x0 - 2, y, x0 + 2, y);
    }
    const bw = (x1 - x0) / k.length;
    for (let i = 0; i < k.length; i++) {
      const v = E.clip(k[i], 0, 9);
      const y = base - v / 9 * span;
      const bx0 = x0 + i * bw + 1;
      const bx1 = x0 + (i + 1) * bw - 1;
      if (k[i] >= need || i === st.k) h.fillRect(bx0, y, bx1, base - 1);
      else h.drawRect(bx0, y, bx1, base - 1);
      if (i === st.k) {
        h.drawRect(bx0 - 3, y0 - 2, bx1 + 3, base + 2);
        h.drawRect(bx0 - 2, y0 - 1, bx1 + 2, base + 1);
      }
    }
    if (need <= 9) {
      const ty = base - need / 9 * span;
      for (let dx = x0; dx < x1; dx += 8) h.drawLine(dx, ty, dx + 4, ty);
    }
    for (let i = 0; sp.kpf_ticks && i < sp.kpf_ticks.length; i++) {
      const tk = sp.kpf_ticks[i];
      const tx = x0 + tk.i * bw;
      h.drawLine(tx, base, tx, base + 3);
      text(cut(tk.d || "", 5), tx, base + 5, 0, -1);
    }
  }
  function space(loc) {
    const sp = st.d.space, au = loc.aurora || {};
    if (!sp) { msg("NO SPACE DATA", "SYNC COMPANION"); return; }
    if (sp.kpf && st.k >= sp.kpf.length) st.k = sp.kpf.length - 1;
    if (st.k < 0) st.k = 0;
    box(14, 96, 238, 232, "ROBCO SOLAR RELAY");
    box(250, 96, 466, 232, "KP BUFFER");
    rowAt("FLARE", sp.flare || "NONE", 26, 226, 118);
    rowAt("R/S/G", (sp.r_scale || "R0") + " " + (sp.s_scale || "S0") + " " + (sp.g_scale || "G0"), 26, 226, 152);
    rowAt("KP NOW/PK", (sp.kp_now === undefined ? "--" : sp.kp_now) + " / " + (sp.kp_peak === undefined ? "--" : sp.kp_peak), 26, 226, 186);
    font(0);
    text(cut((sp.g_text || "FIELD QUIET").toUpperCase(), 25), 26, 216, -1, -1);
    text("KP FORECAST UTC", 262, 114, -1, -1);
    kpGraph(sp, loc, 286, 132, 454, 210);
    box(14, 242, 466, 282, "AURORA ESTIMATE");
    font(0);
    text("AURORA @ " + cut((loc.name || "").toUpperCase(), 18), 24, 258, -1, 0);
    font(2);
    text(au.chance || "UNKNOWN", 456, 258, 1, 0);
    font(1);
    text(cut(kpLabel(sp, st.k) + "  KP " + (sp.kpf && sp.kpf.length ? sp.kpf[st.k] : "--"), 24), 24, 276, -1, 0);
    text("NEED " + (au.needed === undefined ? "?" : au.needed) + " PK " +
      (au.maxkp === undefined ? "?" : au.maxkp), 456, 276, 1, 0);
  }

  function draw() {
    h.reset().clear();
    header();
    if (st.e || !st.d) {
      msg(st.e || "NO DATA", "RUN COMPANION SYNC");
      font(0);
      text("EXPECTED: USER/WEATHER.JSON", 240, 212, 0, -1);
      scanMask();
      return;
    }
    const loc = st.d.locations[st.l] || {};
    clampSel(loc);
    title(loc);
    tabs();
    if (st.t === 0) current(loc);
    else if (st.t === 1) forecast(loc);
    else space(loc);
    footer();
    scanMask();
  }
  function knob1(dir) {
    if (!st.d) { if (dir === 0) load(); draw(); return; }
    const loc = st.d.locations[st.l] || {};
    if (dir === 0) st.m = st.m ? 0 : 1;
    else if (st.m) setSel(sel() + dir, loc);
    else st.l = (st.l + dir + st.d.locations.length) % st.d.locations.length;
    Pip.playSound("SCROLL");
    draw();
  }
  function knob2(dir) {
    st.t = (st.t + (dir || 1) + TABS.length) % TABS.length;
    if (st.d) clampSel(st.d.locations[st.l] || {});
    Pip.playSound("TAB");
    draw();
  }

  Pip.on("knob1", knob1);
  Pip.on("knob2", knob2);
  load();
  draw();

  return {
    id: "WEATHER",
    notDefault: true,
    fullscreen: true,
    remove: function() {
      Pip.removeListener("knob1", knob1);
      Pip.removeListener("knob2", knob2);
    }
  };
})
