// ============================================================================
//  PIP-OS WEATHER  -  Cached weather terminal for the Pip-Boy 3000
//  Reads forecast data written to the SD card by the companion script.
//  Displays current conditions + 5-day forecast for multiple locations.
//
//  CONTROLS
//    Scroll wheel  (knob1 rotate) ... change location
//    Thumbwheel    (knob2 rotate) ... switch view  (CURRENT <-> FORECAST)
//    Scroll click  (knob1 click)  ... toggle view
//    ITEMS button                 ... exit  (notDefault:true)
//
//  NOTE: per the RobCo 3000 docs, the in-scope graphics instance / font
//  names can vary by firmware. This app resolves the graphics object
//  defensively (h -> g) and falls back on fonts, so tweak the two
//  helpers below if your firmware exposes different names.
// ============================================================================
(function() {

  // --- Resolve the graphics instance (3000 example uses `h`, Mk V uses `g`) -
  var G = (typeof h !== "undefined") ? h
        : (typeof g !== "undefined") ? g
        : null;

  // Where the companion script writes data (first match wins)
  var DATA_PATHS = ["USER/WEATHER.JSON", "WEATHER.JSON", "USER/WEATHER.json"];

  // Flag the cache as stale once it is older than this many hours.
  var STALE_HOURS = 12;

  var state = {
    data: null,   // parsed payload
    err:  null,   // error string if load failed
    loc:  0,      // selected location index
    tab:  0       // 0 = CURRENT, 1 = FORECAST
  };

  var blinkOn = true;     // toggled by the stale-warning blink timer
  var blinkTimer = null;

  // ---------------------------------------------------------------- fonts ---
  function fontBig() {
    // Big numerals for the temperature
    try { G.setFont("Monofonto23", 2); return; } catch (e) {}
    try { G.setFontVector(54); return; } catch (e) {}
    G.setFont("6x8", 6);
  }
  function fontHead() {
    try { G.setFont("Monofonto23"); return; } catch (e) {}
    try { G.setFontVector(24); return; } catch (e) {}
    G.setFont("6x8", 3);
  }
  function fontSmall() {
    try { G.setFont("6x8", 2); return; } catch (e) {}
    G.setFont("6x8");
  }
  function fontTiny() {
    try { G.setFont("6x8"); return; } catch (e) {}
  }

  // --------------------------------------------------------------- loading --
  function loadData() {
    state.data = null;
    state.err = null;
    var fs;
    try { fs = require("fs"); } catch (e) { state.err = "NO FS MODULE"; return; }
    var txt = null;
    for (var i = 0; i < DATA_PATHS.length; i++) {
      try {
        txt = fs.readFileSync(DATA_PATHS[i]);
        if (txt) break;
      } catch (e) { txt = null; }
    }
    if (!txt) { state.err = "NO WEATHER DATA"; return; }
    try {
      var d = JSON.parse(txt.toString());
      if (!d || !d.locations || !d.locations.length) { state.err = "EMPTY DATA FILE"; return; }
      state.data = d;
      if (state.loc >= d.locations.length) state.loc = 0;
    } catch (e) {
      state.err = "BAD DATA FORMAT";
    }
    refreshBlink();
  }

  // ----------------------------------------------------- stale tracking -----
  // Returns the age of the cache in hours, or null if it can't be determined.
  function dataAgeHours() {
    if (!state.data || !state.data.epoch) return null;
    var now = Date.now() / 1000;            // UTC epoch seconds (timezone-safe)
    var age = (now - state.data.epoch) / 3600;
    if (!isFinite(age) || age < 0) return null;  // bad/forward device clock
    return age;
  }
  function isStale() {
    var a = dataAgeHours();
    return a !== null && a > STALE_HOURS;
  }
  function ageLabel(h) {
    if (h === null) return "?";
    if (h < 1) return "<1H";
    if (h < 48) return Math.round(h) + "H";
    return Math.round(h / 24) + "D";
  }
  function refreshBlink() {
    if (isStale()) {
      if (!blinkTimer) blinkTimer = setInterval(function () {
        blinkOn = !blinkOn;
        draw();
      }, 700);
    } else if (blinkTimer) {
      clearInterval(blinkTimer);
      blinkTimer = null;
      blinkOn = true;
    }
  }

  // ------------------------------------------------------ weather glyphs ----
  // Simple vector icons drawn from primitives so they read at any palette.
  function iconSun(cx, cy, r, night) {
    if (night) {
      // crescent moon
      G.fillCircle(cx, cy, r * 0.65);
      try { G.setColor(0); } catch (e) {}
      G.fillCircle(cx + r * 0.35, cy - r * 0.25, r * 0.6);
      try { G.setColor(1); } catch (e) {}
      return;
    }
    G.fillCircle(cx, cy, r * 0.55);
    var a;
    for (a = 0; a < 8; a++) {
      var ang = a * Math.PI / 4;
      var sx = cx + Math.cos(ang) * r * 0.85;
      var sy = cy + Math.sin(ang) * r * 0.85;
      var ex = cx + Math.cos(ang) * r * 1.25;
      var ey = cy + Math.sin(ang) * r * 1.25;
      G.drawLine(sx, sy, ex, ey);
    }
  }
  function iconCloud(cx, cy, r) {
    G.fillCircle(cx - r * 0.55, cy + r * 0.15, r * 0.5);
    G.fillCircle(cx + r * 0.55, cy + r * 0.15, r * 0.5);
    G.fillCircle(cx, cy - r * 0.2, r * 0.6);
    G.fillRect(cx - r * 0.95, cy + r * 0.15, cx + r * 0.95, cy + r * 0.6);
  }
  function iconRain(cx, cy, r) {
    iconCloud(cx, cy - r * 0.25, r * 0.85);
    var i;
    for (i = -1; i <= 1; i++) {
      var x = cx + i * r * 0.5;
      G.drawLine(x, cy + r * 0.55, x - r * 0.18, cy + r * 1.05);
    }
  }
  function iconSnow(cx, cy, r) {
    iconCloud(cx, cy - r * 0.25, r * 0.85);
    var i;
    for (i = -1; i <= 1; i++) {
      var x = cx + i * r * 0.5, y = cy + r * 0.8;
      G.drawLine(x - 5, y, x + 5, y);
      G.drawLine(x, y - 5, x, y + 5);
      G.drawLine(x - 4, y - 4, x + 4, y + 4);
      G.drawLine(x - 4, y + 4, x + 4, y - 4);
    }
  }
  function iconStorm(cx, cy, r) {
    iconCloud(cx, cy - r * 0.25, r * 0.85);
    G.fillPoly([
      cx,           cy + r * 0.4,
      cx - r * 0.3, cy + r * 0.4,
      cx,           cy + r * 0.95,
      cx + r * 0.1, cy + r * 0.6,
      cx + r * 0.35,cy + r * 0.6
    ]);
  }
  function iconFog(cx, cy, r) {
    var i;
    for (i = 0; i < 4; i++) {
      var y = cy - r * 0.6 + i * r * 0.45;
      G.drawLine(cx - r * (i % 2 ? 0.7 : 1), y, cx + r * (i % 2 ? 1 : 0.7), y);
    }
  }
  function iconPartly(cx, cy, r, night) {
    iconSun(cx - r * 0.45, cy - r * 0.4, r * 0.65, night);
    iconCloud(cx + r * 0.15, cy + r * 0.2, r * 0.8);
  }

  // map WMO weather code -> icon category
  function drawIcon(code, cx, cy, r, isDay) {
    var night = !isDay;
    if (code === 0) return iconSun(cx, cy, r, night);
    if (code === 1 || code === 2) return iconPartly(cx, cy, r, night);
    if (code === 3) return iconCloud(cx, cy, r);
    if (code === 45 || code === 48) return iconFog(cx, cy, r);
    if (code >= 51 && code <= 67) return iconRain(cx, cy, r);
    if (code >= 71 && code <= 77) return iconSnow(cx, cy, r);
    if (code >= 80 && code <= 82) return iconRain(cx, cy, r);
    if (code >= 85 && code <= 86) return iconSnow(cx, cy, r);
    if (code >= 95) return iconStorm(cx, cy, r);
    return iconCloud(cx, cy, r);
  }

  // ----------------------------------------------------------- drawing ------
  function W() { return G.getWidth(); }
  function H() { return G.getHeight(); }

  function hr(y) {
    G.drawLine(12, y, W() - 12, y);
  }

  function drawDegree(x, y, unit) {
    // small degree ring + unit letter, placed at (x,y) baseline-ish
    G.drawCircle(x + 5, y + 4, 4);
    fontSmall();
    G.setFontAlign(-1, 0);
    G.drawString(unit || "F", x + 14, y + 6);
  }

  function drawHeader() {
    var d = state.data;
    var n = d ? d.locations.length : 0;
    fontTiny();
    if (!isStale()) {                 // banner reuses this space when stale
      G.setFontAlign(-1, -1);
      G.drawString("PIP-OS WEATHER MONITOR", 12, 4);
    }
    if (d) {
      G.setFontAlign(1, -1);
      G.drawString("[" + (state.loc + 1) + "/" + n + "]", W() - 12, 4);
    }
    hr(18);
  }

  function drawFooter() {
    var y = H() - 14;
    hr(y - 4);
    fontTiny();
    G.setFontAlign(-1, -1);
    G.drawString("WHEEL:LOC  THUMB:VIEW  ITEMS:EXIT", 12, y);
    if (state.data && state.data.generated) {
      G.setFontAlign(1, -1);
      var pre = isStale() ? "! STALE " : "UPD ";
      G.drawString(pre + shortStamp(state.data.generated), W() - 12, y);
    }
  }

  // Blinking warning shown (top-left, where the header label normally sits)
  // when the cached data is older than STALE_HOURS.
  function drawStaleBanner() {
    if (!blinkOn) return;                  // blink off-phase: draw nothing
    var x0 = 10, x1 = W() - 58, y0 = 1, y1 = 15;
    G.drawRect(x0, y0, x1, y1);
    G.drawRect(x0 + 1, y0 + 1, x1 - 1, y1 - 1);
    fontTiny();
    G.setFontAlign(0, 0);
    G.drawString("! CACHED DATA " + ageLabel(dataAgeHours()) + " OLD - SYNC SOON !",
      (x0 + x1) / 2, (y0 + y1) / 2);
  }

  function shortStamp(s) {
    // accept "YYYY-MM-DD HH:MM" or ISO; show "MM-DD HH:MM"
    if (!s) return "";
    s = ("" + s).replace("T", " ");
    if (s.length >= 16) return s.substr(5, 11);
    return s;
  }

  function tempUnit() {
    return (state.data && state.data.units && state.data.units.temp) || "F";
  }
  function windUnit() {
    return (state.data && state.data.units && state.data.units.wind) || "mph";
  }

  function drawLocationTitle(loc) {
    fontHead();
    G.setFontAlign(0, -1);
    G.drawString(loc.name || "UNKNOWN", W() / 2, 18);
    if (loc.region) {
      fontTiny();
      G.setFontAlign(0, -1);
      G.drawString(loc.region, W() / 2, 42);
    }
  }

  var TABS = ["CURRENT", "FORECAST", "SPACE WX"];

  function drawTabs(active) {
    var y = 56;
    fontTiny();
    var bw = (W() - 24) / TABS.length;
    var i;
    for (i = 0; i < TABS.length; i++) {
      var x0 = 12 + i * bw;
      if (i === active) G.drawRect(x0 + 3, y, x0 + bw - 3, y + 15);
      G.setFontAlign(0, 0);
      G.drawString(TABS[i], x0 + bw / 2, y + 7);
    }
    hr(76);
  }

  // centered label-over-value cell (used in grids)
  function drawStat(label, value, x, y, w) {
    fontTiny();
    G.setFontAlign(0, -1);
    G.drawString(label, x + w / 2, y);
    fontSmall();
    G.setFontAlign(0, -1);
    G.drawString(value, x + w / 2, y + 12);
  }

  // single-line label (left) + value (right), for side panels
  function drawStatRow(label, value, xL, xR, y) {
    fontTiny();
    G.setFontAlign(-1, 0);
    G.drawString(label, xL, y);
    fontSmall();
    G.setFontAlign(1, 0);
    G.drawString(value, xR, y);
  }

  function drawCurrent(loc) {
    var c = loc.current || {};
    var midY = 150;

    // LEFT: condition icon + big temperature
    drawIcon(c.code | 0, 84, midY, 40, c.is_day ? 1 : 0);
    fontBig();
    G.setFontAlign(1, 0);
    var t = (c.temp === undefined ? "--" : Math.round(c.temp)) + "";
    var tx = 286;
    G.drawString(t, tx, midY);
    drawDegree(tx, midY - 14, tempUnit());

    // condition + solar/aurora tie-in, centered under the icon/temp
    var lcx = 150;
    fontSmall();
    G.setFontAlign(0, -1);
    G.drawString((c.desc || "--").toUpperCase(), lcx, midY + 52);
    var sl = solarLine(loc);
    if (sl) {
      fontTiny();
      G.setFontAlign(0, -1);
      G.drawString(sl, lcx, midY + 74);
    }

    // RIGHT: stat panel
    G.drawLine(300, 86, 300, 286);
    var xL = 314, xR = W() - 14;
    drawStatRow("FEELS", (c.feels === undefined ? "--" : Math.round(c.feels)) + tempUnit(), xL, xR, 116);
    drawStatRow("WIND", (c.wind === undefined ? "--" : Math.round(c.wind)) + (c.dir ? " " + c.dir : ""), xL, xR, 154);
    drawStatRow("HUMIDITY", (c.humidity === undefined ? "--" : Math.round(c.humidity)) + "%", xL, xR, 192);
    drawStatRow("RAD (UV)", (c.uv === undefined ? "--" : Math.round(c.uv)) + "", xL, xR, 230);
    fontTiny();
    G.setFontAlign(0, -1);
    if (c.time) G.drawString("OBSERVED " + shortStamp(c.time), (xL + xR) / 2, 258);
  }

  function drawForecast(loc) {
    var days = loc.daily || [];
    var n = Math.min(days.length, 5);
    fontTiny();
    G.setFontAlign(0, -1);
    G.drawString("5-DAY FORECAST   (HI/LO  -  RAIN%)", W() / 2, 84);
    var colW = (W() - 24) / 5;
    var i;
    for (i = 0; i < n; i++) {
      var d = days[i];
      var cx = 12 + colW * i + colW / 2;
      if (i > 0) G.drawLine(12 + colW * i, 104, 12 + colW * i, 262);
      // day label
      fontSmall();
      G.setFontAlign(0, -1);
      G.drawString(d.d || ("D" + (i + 1)), cx, 108);
      // icon
      drawIcon(d.code | 0, cx, 162, 22, 1);
      // hi / lo
      var hi = (d.hi === undefined ? "--" : Math.round(d.hi));
      var lo = (d.lo === undefined ? "--" : Math.round(d.lo));
      fontSmall();
      G.setFontAlign(0, -1);
      G.drawString(hi + "/" + lo, cx, 202);
      // precip chance
      fontTiny();
      G.setFontAlign(0, -1);
      G.drawString((d.pop === undefined ? "--" : Math.round(d.pop)) + "%", cx, 228);
    }
  }

  // --- space-weather interpretation helpers --------------------------------
  function flareLevel(cls) {
    if (!cls) return 0;
    var c = ("" + cls).charAt(0).toUpperCase();
    return c === "X" ? 3 : c === "M" ? 2 : c === "C" ? 1 : 0;
  }
  function scaleNum(s) {
    if (!s) return 0;
    var m = ("" + s).match(/\d+/);
    return m ? parseInt(m[0], 10) : 0;
  }
  function solarActive(sp) {
    if (!sp) return false;
    return flareLevel(sp.flare) >= 2 || scaleNum(sp.g_scale) >= 1 ||
           scaleNum(sp.s_scale) >= 1 || scaleNum(sp.r_scale) >= 1;
  }
  // Compact one-liner shown on the CURRENT view so space wx ties into weather.
  function solarLine(loc) {
    var sp = state.data.space;
    if (!sp) return null;
    var s;
    if (solarActive(sp)) {
      s = "SOLAR " + (sp.flare || "ACTIVE");
      if (scaleNum(sp.g_scale) >= 1) s += " / " + sp.g_scale;
      else if (scaleNum(sp.s_scale) >= 1) s += " / " + sp.s_scale;
    } else {
      s = "SOLAR QUIET";
    }
    var au = loc.aurora;
    if (au && au.chance && au.chance !== "UNLIKELY") s += "   AURORA " + au.chance;
    return s;
  }

  // 3-day planetary Kp bar graph with a per-location aurora threshold line.
  function drawKpGraph(sp, loc, x0, y0, x1, y1) {
    var kpf = sp.kpf || [];
    var base = y1;                          // Kp=0 baseline
    var span = y1 - y0;                     // pixels for Kp 0..9
    function ky(kp) { return base - (Math.max(0, Math.min(9, kp)) / 9) * span; }
    // axis + Kp gridlines (3/6/9)
    G.drawLine(x0, y0, x0, y1);
    G.drawLine(x0, y1, x1, y1);
    fontTiny();
    var gl, glv = [3, 6, 9];
    for (gl = 0; gl < 3; gl++) {
      var gy = ky(glv[gl]);
      G.setFontAlign(1, 0);
      G.drawString(glv[gl] + "", x0 - 2, gy);
    }
    // bars - filled when Kp reaches this location's aurora threshold
    var needed = (loc.aurora && loc.aurora.needed !== undefined) ? loc.aurora.needed : 99;
    var n = kpf.length || 1;
    var bw = (x1 - x0) / n;
    var i;
    for (i = 0; i < kpf.length; i++) {
      var bx0 = x0 + i * bw + 1, bx1 = x0 + (i + 1) * bw - 1;
      var by = ky(kpf[i]);
      if (kpf[i] >= needed) G.fillRect(bx0, by, bx1, base - 1);
      else G.drawRect(bx0, by, bx1, base - 1);
    }
    // aurora threshold (dashed) - the tie to THIS location
    if (needed <= 9) {
      var ty = ky(needed), dx;
      for (dx = x0; dx < x1; dx += 6) G.drawLine(dx, ty, dx + 3, ty);
      fontTiny();
      G.setFontAlign(-1, -1);
      G.drawString("AURORA Kp" + needed, x0 + 3, y0 - 1);
    }
    // day ticks
    var ticks = sp.kpf_ticks || [];
    for (i = 0; i < ticks.length; i++) {
      var tx = x0 + ticks[i].i * bw;
      G.drawLine(tx, base, tx, base + 3);
      fontTiny();
      G.setFontAlign(0, -1);
      G.drawString(ticks[i].d, tx, base + 4);
    }
  }

  function drawSpace(loc) {
    var sp = state.data.space;
    if (!sp) {
      fontSmall();
      G.setFontAlign(0, 0);
      G.drawString("NO SPACE WX DATA", W() / 2, H() / 2 - 10);
      fontTiny();
      G.drawString("RE-SYNC WITH COMPANION", W() / 2, H() / 2 + 16);
      return;
    }
    // --- LEFT COLUMN: solar scales + planetary Kp -------------------------
    fontTiny();
    G.setFontAlign(-1, -1);
    G.drawString("SOLAR ACTIVITY", 14, 84);
    var cw = (228 - 12) / 2;
    drawStat("FLARE", (sp.flare || "NONE"), 12, 104, cw);
    drawStat("R-SCALE", (sp.r_scale || "R0"), 12 + cw, 104, cw);
    drawStat("S-SCALE", (sp.s_scale || "S0"), 12, 150, cw);
    drawStat("G-SCALE", (sp.g_scale || "G0"), 12 + cw, 150, cw);
    fontSmall();
    G.setFontAlign(-1, -1);
    G.drawString("PLANETARY Kp " + (sp.kp_now === undefined ? "--" : sp.kp_now), 14, 196);
    fontTiny();
    G.setFontAlign(-1, -1);
    G.drawString((sp.g_text ? sp.g_text.toUpperCase() : "FIELD QUIET"), 14, 216);

    // --- RIGHT COLUMN: 3-day Kp graph (with this location's threshold) ----
    G.drawLine(244, 84, 244, 248);
    fontTiny();
    G.setFontAlign(-1, -1);
    G.drawString("Kp 3-DAY FORECAST", 252, 84);
    drawKpGraph(sp, loc, 274, 104, W() - 14, 226);

    // --- BOTTOM: aurora verdict for this location -------------------------
    var au = loc.aurora || {};
    hr(250);
    fontTiny();
    G.setFontAlign(-1, 0);
    G.drawString("AURORA @ " + (loc.name || ""), 14, 264);
    fontHead();
    G.setFontAlign(1, 0);
    G.drawString((au.chance || "UNKNOWN"), W() - 14, 264);
    fontTiny();
    G.setFontAlign(-1, -1);
    if (au.needed !== undefined) {
      G.drawString("NEEDS Kp " + au.needed + "   PEAK Kp " +
        (au.maxkp === undefined ? "?" : au.maxkp), 14, 282);
    }
  }

  function drawMessage(msg, sub) {
    fontHead();
    G.setFontAlign(0, 0);
    G.drawString(msg, W() / 2, H() / 2 - 16);
    fontSmall();
    G.setFontAlign(0, 0);
    if (sub) G.drawString(sub, W() / 2, H() / 2 + 20);
  }

  function draw() {
    G.reset().clear();
    drawHeader();

    if (state.err || !state.data) {
      drawMessage(state.err || "NO DATA",
        "RUN THE COMPANION APP TO SYNC");
      fontTiny();
      G.setFontAlign(0, -1);
      G.drawString("EXPECTED: USER/WEATHER.JSON", W() / 2, H() / 2 + 50);
      return;
    }

    var loc = state.data.locations[state.loc];
    drawLocationTitle(loc);
    drawTabs(state.tab);
    if (state.tab === 0) drawCurrent(loc);
    else if (state.tab === 1) drawForecast(loc);
    else drawSpace(loc);
    if (isStale()) drawStaleBanner();
    drawFooter();
  }

  // ------------------------------------------------------------- input ------
  function click() {
    try { Pip.knob1Click && Pip.knob1Click(0); } catch (e) {}
    try { Pip.audioBuiltin && Pip.audioBuiltin("CLICK"); } catch (e) {}
  }

  function onKnob1(dir) {
    if (!state.data) { if (dir === 0) loadData(); draw(); return; }
    var n = state.data.locations.length;
    if (dir === 0) {            // click advances the view
      state.tab = (state.tab + 1) % TABS.length;
    } else {
      state.loc = (state.loc + dir + n) % n;
    }
    click();
    draw();
  }

  function onKnob2(dir) {
    if (dir === 0) return;
    state.tab = (state.tab + dir + TABS.length) % TABS.length;
    click();
    draw();
  }

  // ------------------------------------------------------------- boot --------
  Pip.on("knob1", onKnob1);
  Pip.on("knob2", onKnob2);
  loadData();
  draw();

  return {
    id: "WEATHER",
    notDefault: true,
    fullscreen: true,
    remove: function () {
      if (blinkTimer) { clearInterval(blinkTimer); blinkTimer = null; }
      Pip.removeListener("knob1", onKnob1);
      Pip.removeListener("knob2", onKnob2);
    }
  };
})
