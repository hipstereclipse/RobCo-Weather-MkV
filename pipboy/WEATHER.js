// RobCo Weather for the Pip-Boy 3000 Mk V.
//
// The Mk V firmware loads USER/*.js as a bare script and runs it top to
// bottom; nothing ever invokes a returned closure (that is the Pip-Boy 3000
// loader contract, not this device's). When the user turns the mode dial
// away, the firmware calls the Pip.remove / Pip.removeSubmenu hooks, so all
// teardown is registered there - the same pattern as the official asteroid
// and text apps in thewandcompany/pip-boy.

// Take over cleanly from the INV > APPS submenu (official app preamble).
if (Pip.removeSubmenu) Pip.removeSubmenu();
delete Pip.removeSubmenu;
if (Pip.remove) Pip.remove();
delete Pip.remove;

(function() {
  const PATHS = ["USER/WEATHER.JSON", "WEATHER.JSON", "USER/WEATHER.json"];
  const TABS = ["ATMOS", "5-DAY", "SOLAR"];
  const CORN = 56; // horizontal inset for the top/bottom rows so the case
                   // opening does not clip the header/footer text. Bump this
                   // higher still if a unit's opening is even tighter.
  // Mk V: g renders straight to the 480x320 landscape LCD, but the case
  // shroud hides x < 38 and x > 438. Every draw below stays inside
  // x in [38, 438].
  const st = { d: null, e: null, l: 0, t: 0, m: 0, a: 0, f: 0, k: 0 };

  function num(v) { return v === undefined || v === null ? "--" : Math.round(v) + ""; }
  function unit() { return st.d && st.d.units && st.d.units.temp || "F"; }
  function cut(s, n) {
    s = s === undefined || s === null ? "--" : "" + s;
    return s.length > n ? s.substr(0, n) : s;
  }
  function font(n) {
    if (n === 3) { g.setFont("Monofonto23", 2); return; }
    if (n === 2) { g.setFont("Monofonto23"); return; }
    g.setFont("6x8", n === 1 ? 2 : 1);
  }
  function text(s, x, y, ax, ay) {
    g.setFontAlign(ax === undefined ? 0 : ax, ay === undefined ? -1 : ay);
    g.drawString(s, x, y);
  }
  function box(x0, y0, x1, y1, label) {
    g.drawRect(x0, y0, x1, y1);
    if (label) {
      font(0);
      g.clearRect(x0 + 7, y0, x0 + 15 + label.length * 6, y0 + 8);
      text(" " + label + " ", x0 + 9, y0 - 1, -1, -1);
    }
  }
  function gauge(x, y, w, v, max) {
    g.drawRect(x, y, x + w, y + 6);
    if (v === undefined || v === null || !isFinite(v)) return;
    const f = E.clip(Math.round((w - 2) * v / max), 0, w - 2);
    if (f > 0) g.fillRect(x + 1, y + 1, x + f, y + 5);
  }
  function scanMask() {
    for (let y = 33; y < 288; y += 8) g.clearRect(38, y, 438, y);
  }
  function hr(y) { g.drawLine(40, y, 436, y); }
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
    if (on) g.drawRect(x0, y0, x1, y1);
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
    const y = 66, bw = 396 / TABS.length;
    font(0);
    for (let i = 0; i < TABS.length; i++) {
      const x = 40 + i * bw;
      if (i === st.t) g.drawRect(x + 2, y, x + bw - 2, y + 15);
      text((i === st.t ? "> " : "  ") + TABS[i], x + bw / 2, y + 8, 0, 0);
    }
    hr(85);
  }
  function msg(a, b) {
    font(2);
    text(a, 238, 142, 0, 0);
    font(1);
    if (b) text(b, 238, 180, 0, 0);
  }

  function degree(x, y) {
    g.drawCircle(x + 5, y + 4, 4);
    font(1);
    text(unit(), x + 14, y + 6, -1, 0);
  }
  function thick(x0, y0, x1, y1) {
    g.drawLine(x0, y0, x1, y1);
    g.drawLine(x0 + 1, y0, x1 + 1, y1);
  }
  function sun(cx, cy, r) {
    const d = r + 10, s = r + 3, q = r / 2;
    g.drawCircle(cx, cy, r);
    g.drawCircle(cx, cy, r - 3);
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
    g.drawCircle(cx - r / 2, cy + 2, r / 2);
    g.drawCircle(cx + r / 2, cy + 2, r / 2);
    g.drawCircle(cx, cy - 4, r / 2 + 3);
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
    box(40, 96, 232, 246, "LOCAL ATMOS");
    box(240, 96, 436, 246, "INSTRUMENTS");

    wxIcon(c.code, 78, 136, 24);
    font(3);
    g.setFontAlign(-1, 0);
    g.drawString(num(c.temp), 118, 144);
    degree(200, 124);

    font(0);
    text("> CONDITION", 50, 181, -1, -1);
    if (c.time) text("OBS " + stamp(c.time), 222, 181, 1, -1);
    font(1);
    text(cut((c.desc || "--").toUpperCase(), 15), 50, 199, -1, -1);
    metricAt("HI", num(d0.hi), 72, 216);
    metricAt("LO", num(d0.lo), 126, 216);
    metricAt("RAIN", num(d0.pop) + "%", 188, 216);

    hilite(246, 104, 430, 127, st.t === 0 && st.a === 0);
    rowAt("FEELS", num(c.feels) + unit(), 252, 424, 116);
    hilite(246, 134, 430, 157, st.t === 0 && st.a === 1);
    rowAt("WIND", num(c.wind) + (c.dir ? " " + c.dir : ""), 252, 424, 146);
    hilite(246, 164, 430, 193, st.t === 0 && st.a === 2);
    rowAt("HUMID", num(c.humidity) + "%", 252, 424, 176);
    gauge(252, 188, 172, c.humidity, 100);
    hilite(246, 202, 430, 233, st.t === 0 && st.a === 3);
    rowAt("RAD UV", num(c.uv), 252, 424, 214);
    gauge(252, 226, 172, c.uv, 11);

    let detail;
    if (st.a === 0) detail = "FEELS " + num(c.feels) + unit() + "  ACTUAL " + num(c.temp) + unit();
    else if (st.a === 1) detail = "WIND " + num(c.wind) + (c.dir ? " " + c.dir : "") + " " + ((st.d.units && st.d.units.wind) || "");
    else if (st.a === 2) detail = "HUMID " + num(c.humidity) + "%  RAIN " + num(d0.pop) + "%";
    else detail = "UV " + num(c.uv) + "  " + (solarLine(loc) || "SOLAR QUIET");
    box(40, 250, 436, 282, "SELECTED TELEMETRY");
    font(1);
    text(cut(detail, 31), 50, 266, -1, 0);
  }

  function forecast(loc) {
    const days = loc.daily || [], n = Math.min(days.length, 5), cw = 396 / 5;
    if (st.f >= n && n > 0) st.f = n - 1;
    box(40, 96, 436, 222, "FORECAST BUFFER");
    font(0);
    text("5 ENTRIES  //  SELECT DAY WITH WHEEL", 52, 111, -1, -1);
    for (let i = 0; i < n; i++) {
      const d = days[i] || {};
      const x = 40 + i * cw;
      const cx = x + cw / 2;
      if (i > 0) g.drawLine(x, 126, x, 216);
      hilite(x + 4, 122, x + cw - 4, 216, i === st.f);
      font(1);
      text(d.d || ("D" + (i + 1)), cx, 134, 0, -1);
      wxIcon(d.code, cx, 169, 10);
      font(0);
      text(cut((d.desc || "--").toUpperCase(), 9), cx, 192, 0, -1);
      text(num(d.hi) + "/" + num(d.lo) + " " + num(d.pop) + "%", cx, 207, 0, -1);
    }
    const d = days[st.f] || {};
    box(40, 232, 436, 282, "ENTRY DETAIL");
    font(1);
    text(cut((d.date || d.d || ("D" + (st.f + 1))) + "  " +
      (d.desc || "--").toUpperCase(), 31), 50, 249, -1, -1);
    text("HI/LO " + num(d.hi) + "/" + num(d.lo), 50, 272, -1, 0);
    text("RAIN " + num(d.pop) + "%", 426, 272, 1, 0);
  }

  function kpGraph(sp, loc, x0, y0, x1, y1) {
    const k = sp.kpf || [], base = y1, span = y1 - (y0 + 5);
    if (!k.length) return;
    const need = loc.aurora && loc.aurora.needed !== undefined ? loc.aurora.needed : 99;
    font(0);
    text("KP", x0 - 18, y0 - 8, -1, -1);
    g.drawLine(x0, y0, x0, y1);
    g.drawLine(x0, y1, x1, y1);
    text("0", x0 - 4, base, 1, 0);
    for (let v = 3; v <= 9; v += 3) {
      const y = base - v / 9 * span;
      text("" + v, x0 - 4, y, 1, 0);
      g.drawLine(x0 - 2, y, x0 + 2, y);
    }
    const bw = (x1 - x0) / k.length;
    for (let i = 0; i < k.length; i++) {
      const v = E.clip(k[i], 0, 9);
      const y = base - v / 9 * span;
      const bx0 = x0 + i * bw + 1;
      const bx1 = x0 + (i + 1) * bw - 1;
      if (k[i] >= need || i === st.k) g.fillRect(bx0, y, bx1, base - 1);
      else g.drawRect(bx0, y, bx1, base - 1);
      if (i === st.k) {
        g.drawRect(bx0 - 3, y0 - 2, bx1 + 3, base + 2);
        g.drawRect(bx0 - 2, y0 - 1, bx1 + 2, base + 1);
      }
    }
    if (need <= 9) {
      const ty = base - need / 9 * span;
      for (let dx = x0; dx < x1; dx += 8) g.drawLine(dx, ty, dx + 4, ty);
    }
    for (let i = 0; sp.kpf_ticks && i < sp.kpf_ticks.length; i++) {
      const tk = sp.kpf_ticks[i];
      const tx = x0 + tk.i * bw;
      g.drawLine(tx, base, tx, base + 3);
      text(cut(tk.d || "", 5), tx, base + 5, 0, -1);
    }
  }
  function space(loc) {
    const sp = st.d.space, au = loc.aurora || {};
    if (!sp) { msg("NO SPACE DATA", "SYNC COMPANION"); return; }
    if (sp.kpf && st.k >= sp.kpf.length) st.k = sp.kpf.length - 1;
    if (st.k < 0) st.k = 0;
    box(40, 96, 232, 232, "ROBCO SOLAR RELAY");
    box(240, 96, 436, 232, "KP BUFFER");
    rowAt("FLARE", sp.flare || "NONE", 52, 220, 118);
    rowAt("R/S/G", (sp.r_scale || "R0") + " " + (sp.s_scale || "S0") + " " + (sp.g_scale || "G0"), 52, 220, 152);
    rowAt("KP NOW/PK", (sp.kp_now === undefined ? "--" : sp.kp_now) + " / " + (sp.kp_peak === undefined ? "--" : sp.kp_peak), 52, 220, 186);
    font(0);
    text(cut((sp.g_text || "FIELD QUIET").toUpperCase(), 25), 52, 216, -1, -1);
    text("KP FORECAST UTC", 252, 114, -1, -1);
    kpGraph(sp, loc, 274, 132, 424, 210);
    box(40, 242, 436, 282, "AURORA ESTIMATE");
    font(0);
    text("AURORA @ " + cut((loc.name || "").toUpperCase(), 18), 50, 258, -1, 0);
    font(2);
    text(au.chance || "UNKNOWN", 426, 258, 1, 0);
    font(1);
    text(cut(kpLabel(sp, st.k) + "  KP " + (sp.kpf && sp.kpf.length ? sp.kpf[st.k] : "--"), 15), 50, 276, -1, 0);
    text("NEED " + (au.needed === undefined ? "?" : au.needed) + " PK " +
      (au.maxkp === undefined ? "?" : au.maxkp), 426, 276, 1, 0);
  }

  function draw() {
    g.reset().clear();
    // reset() applies the UI theme on current firmware, but set the phosphor
    // foreground explicitly so a build that resets to plain white still
    // renders in the device color.
    if (g.theme && g.theme.fg !== undefined) g.setColor(g.theme.fg);
    header();
    if (st.e || !st.d) {
      msg(st.e || "NO DATA", "RUN COMPANION SYNC");
      font(0);
      text("EXPECTED: USER/WEATHER.JSON", 238, 212, 0, -1);
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
  function sfx(name, dir, k) {
    if (typeof Pip.playSound === "function") {
      try { Pip.playSound(name); return; } catch (e) {}
    }
    if (k === 1) Pip.knob1Click(dir); else Pip.knob2Click(dir);
  }
  function knob1(dir) {
    if (!st.d) { if (dir === 0) load(); draw(); return; }
    const loc = st.d.locations[st.l] || {};
    if (dir === 0) st.m = st.m ? 0 : 1;
    else if (st.m) setSel(sel() + dir, loc);
    else st.l = (st.l + dir + st.d.locations.length) % st.d.locations.length;
    sfx("SCROLL", dir, 1);
    draw();
  }
  function knob2(dir) {
    st.t = (st.t + (dir || 1) + TABS.length) % TABS.length;
    if (st.d) clampSel(st.d.locations[st.l] || {});
    sfx("TAB", dir, 2);
    draw();
  }
  function teardown() {
    Pip.removeListener("knob1", knob1);
    Pip.removeListener("knob2", knob2);
    if (Pip.audioStop) Pip.audioStop();
    delete Pip.remove;
    delete Pip.removeSubmenu;
  }

  // The firmware invokes these hooks (whichever exists) when the mode dial
  // is turned away; registering both matches the official apps.
  Pip.remove = teardown;
  Pip.removeSubmenu = teardown;
  // Ensure exclusivity on the knobs (official inputs-doc pattern) so a
  // previous app's leaked handler can't fight ours. Torch is left alone to
  // keep the stock flashlight toggle.
  Pip.removeAllListeners("knob1");
  Pip.removeAllListeners("knob2");
  Pip.on("knob1", knob1);
  Pip.on("knob2", knob2);
  load();
  draw();
})();
