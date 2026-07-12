# Agents.md — LLM Instructions for Pip-Boy 3000 Mk V App Conversion & Development

This file governs how LLM-powered agents behave when **converting**, generating, or
auditing app/game code in this repository. The target device is the **Pip-Boy 3000 Mk V**
(the Bethesda × The Wand Company Fallout-TV-series replica), **not** the newer Pip-Boy 3000
(Fallout 3 / New Vegas). The two devices share an Espruino architecture but differ in their
app model, so rules written for the 3000 do **not** transfer unchanged. Follow every rule
below strictly. Where a rule concerns hardware or firmware behavior, feature-detect rather
than assume (see §6.4 and §10).

Authoritative sources for this device:
- RobCo Industries **Mk V** developer docs: `https://log.robco-industries.org/documentation/pipboy-3000/`
  (note the Mk V lives under `pipboy-3000`, distinct from the 3000's `pipboy/3000/` tree).
- The community apps repo this file ships in: `CodyTolene/pip-boy-3000-mk-v-apps` (third
  iteration, hosted on `pip-boy.com`).
- Firmware / recovery: `beaverboy-12/The-Wand-Company-Pip-Boy-3000-Mk-V-Community-Guide`.

---

## Table of Contents

- [1. Project Context](#1-project-context)
- [2. Repository & App File Structure](#2-repository--app-file-structure)
- [3. The App Contract](#3-the-app-contract)
- [4. Code Generation Rules](#4-code-generation-rules)
- [5. Graphics (`h` / `g` / `bC`)](#5-graphics-h--g--bc)
- [6. Input & Hardware](#6-input--hardware)
- [7. Sound, Assets & Media Formats](#7-sound-assets--media-formats)
- [8. Registration & Metadata](#8-registration--metadata)
- [9. Conversion Rules (3000 → Mk V)](#9-conversion-rules-3000--mk-v)
- [10. Review & Audit Rules](#10-review--audit-rules)
- [11. Anti-Patterns (Do Not Generate)](#11-anti-patterns-do-not-generate)
- [12. Build, Minification & Deployment](#12-build-minification--deployment)
- [Appendix A: Mk V Hardware Pin Reference](#appendix-a-mk-v-hardware-pin-reference)
- [Appendix B: Quick Reference](#appendix-b-quick-reference)
- [Appendix C: Firmware Safety & Recovery](#appendix-c-firmware-safety--recovery)
- [Appendix D: Minimal Templates](#appendix-d-minimal-templates)

---

## 1. Project Context

- **Platform:** Pip-Boy 3000 Mk V — a wearable replica running **Espruino** (a JavaScript
  interpreter) on an STM32 board (Cortex-M4 class). Every app is JavaScript loaded from the
  SD card.
- **Display:** 320×480 px IPS panel, rendered in landscape. The drawing surface is therefore
  **480 wide × 320 tall** (`h.getWidth()` → 480, `h.getHeight()` → 320). The physical panel
  is wider than the case opening: the **visible** region is `x ∈ [38, 438]` (a 400×320 area),
  `y ∈ [0, 320]`. Keep all meaningful content inside those bounds or it hides behind the
  shroud. Prefer the global `BGRECT` (bounds of the content buffer) over hardcoding.
- **Input:** left **scroll wheel** (`knob1`), top **thumbwheel** (`knob2`), **torch** button,
  and the front **radio tuner** buttons. The three top-level modes (STATS / INV / DATA / MAP /
  RADIO) are selected by a physical **resistor-ladder dial**, not discrete buttons — read via
  `Pip.measurePin(MODE_SELECTOR)`. See §6.
- **Memory:** extremely constrained. Espruino stores source, variables, arrays, and objects
  as small fixed-size blocks ("JsVars") drawn from a tiny pool. Every declaration, array
  element, and object property consumes a block. Minimize declarations, inline single-use
  values, hardcode constants, and prefer typed arrays for dense numeric data. This is the
  single most important discipline in this repository — see §4.
- **Language:** JavaScript, Espruino subset. Supports `class`, arrow functions, `Promise`,
  typed arrays, `Math.randInt`, `E.clip`, `E.defrag`, etc. Does **NOT** support ES modules
  (`import`/`export`), `async`/`await`, or template literals (backtick strings).
- **Storage:** stock SD is **256 MB FAT16** (replaceable with a larger FAT32 card). Apps live
  in `USER/`, metadata in `APPINFO/`, on-demand modules in `MODULES/`, boot scripts in
  `USER_BOOT/`. Audio placed in `USER/` also appears under DATA > MAINTENANCE > "Play audio
  files".
- **Pip API (Mk V):** `https://log.robco-industries.org/documentation/pipboy-3000/`.
  General Espruino graphics/utilities: `https://www.espruino.com/Reference`.

---

## 2. Repository & App File Structure

Apps live under `apps/`, games under `games/`. One directory per submission, **PascalCase**:

```
apps/<MyAppName>/            (or games/<MyGameName>/)
├── <MyAppName>.js           # Source (unminified). Filename stem SHOULD match the metadata id.
├── <MyAppName>.min.js       # Minified + pretokenised build (see §12)
├── package.json             # Registration metadata for the build/registry (see §8)
├── README.md                # Description, controls, install steps, credits
├── ChangeLog                # Version history (dated, with PR links)
└── assets/                  # 4bpp .IMG bitmaps, .wav / .avi media, icons, data files
    └── ...
```

**Rules:**

- The `.min.js` must be functionally identical to the source — only whitespace, comments, and
  identifier names may differ, and the app-contract structure (§3) must be preserved.
- The metadata `id` maps the app to its on-device file. Keep the source filename, the `id`,
  and the on-card `USER/<id>.js` name consistent.
- Asset paths in metadata are relative to the app directory; the build rewrites them to
  card-relative paths.
- `ChangeLog` entries, newest first:
  ```
  <version> (<yyyy-mm-dd>)
  <PR-or-change-link>
  - <change description>
  ```

---

## 3. The App Contract

The Mk V supports **two** valid app forms. An agent working a conversion **must recognize
both**, because incoming code (and legacy Mk V apps) may use either. **New and converted apps
in this repository MUST use Form A** (the loader contract): it is what `pip-boy.com` expects,
it makes cleanup explicit, and it maximizes parity with the 3000 source you are converting
from.

### 3.1 Form A — Loader contract (REQUIRED for new/converted apps)

The app is an **anonymous function expression** (IIFE-shaped, but **not** self-invoked — the
loader invokes it) that returns an object exposing at least `id` and `remove`:

```js
(function() {
  // All state, handlers, and init live inside this closure.
  // Closing the app reclaims everything declared here automatically.

  return {
    id: "MYAPP",           // uppercase alphanumeric, no spaces/hyphens
    notDefault: true,      // a mode-button press navigates away and closes the app
    fullscreen: true,      // hide OS header/footer chrome
    remove: function() {
      // Detach EVERYTHING created outside the closure's automatic reclamation:
      // listeners, timers, watches, audio, open files. See §3.3.
    }
  };
});
```

- **Do NOT** append `()` to invoke the function. The loader/OS invokes it.
- `notDefault` and `fullscreen` are loader/firmware conventions — supported by the community
  loader and current firmware. If you cannot confirm them for a target firmware, the app must
  still exit cleanly (see Form B fallback) rather than trap the user.

### 3.2 Form B — Firmware-native script (recognize; convert TO Form A)

The raw firmware also loads any `USER/<name>.js` as a bare top-to-bottom script that appears
under **INV > APPS** and returns to the menu by calling **`submenuApps()`**. This is the form
shown in the official Mk V "Hello World":

```js
Pip.typeText("Hello World!").then(() =>
  setTimeout(() => {
    Pip.typeText("Nice app!").then(() => setTimeout(submenuApps, 3000));
  }, 3000)
);
```

There is no `remove()` hook in Form B — **you** must detach every listener/timer/watch
yourself immediately before calling `submenuApps()`, or they leak into the OS and other apps.
When converting Form B → Form A, move that teardown into `remove()` and drop the explicit
`submenuApps()` call (the loader handles navigation).

### 3.3 `remove()` requirements (Form A)

`remove()` MUST undo everything the app created that could outlive it. Maintain a strict
one-to-one teardown for each of these categories:

1. Every `Pip.on(...)` / `Pip.onExclusive(...)` → matching `Pip.removeListener(...)` (or
   `Pip.removeAllListeners("<event>")`).
2. Every `setInterval` → `clearInterval`; every `setTimeout` that may still be pending →
   `clearTimeout`.
3. Every `setWatch` → `clearWatch`.
4. `Pip.audioStop()` if the app played audio.
5. Close any file opened with `E.openFile(...)`.
6. `h.clear()` only if the app drew over non-app chrome (usually unnecessary for `fullscreen`).

`remove()` MUST **never** call `load()`, `E.reboot()`, `save()`, or `submenuApps()`. It must
exit cleanly and let the OS restore the prior state. It does not need a double-removal guard.

---

## 4. Code Generation Rules

Memory and code size are the priority of this repository. Apply every rule; violations are
rejected in review (§10).

### 4.1 Variables & allocation

- Use `const`/`let`; **never `var`**.
- **Minimize declarations.** Every variable is a scarce block. Inline single-use values.
  Hardcode true constants (screen dimensions, grid sizes, colors) rather than naming them.
- Screen size is constant: `const W = 480, H = 320;` (or read once via `h.getWidth()` /
  `h.getHeight()`) — never re-read per frame, never reassign.
- Group related constants into one object (`const C = {...}`) instead of many top-level
  `const`s.
- Do **not** alias the graphics instance (`let c = h`) — reference it directly (§5).
- Do **not** declare an `APP_ID` variable — put the id string literal in the return object.

### 4.2 Typed arrays & data

- Espruino stores normal arrays/objects as **linked lists**; access cost scales with element
  count. Put dense numeric data in **typed arrays** (`Uint8Array`, `Int16Array`,
  `Float32Array`, …) — contiguous, far faster, far cheaper.
- Pre-allocate typed arrays once and reuse; allocation needs a contiguous block and is slow.
- Use `TypedArray.set(src, offset)` for bulk copies and `DataView` for mixed-width access
  without copying.
- Avoid storing functions in arrays/objects and avoid nesting deeper than ~4 levels — both
  waste blocks.
- Keep strings short (≲256 chars each). Use `E.toFlatString(...)` for large contiguous
  buffers when needed.

### 4.3 Hot loops & directives

- Drive animation/logic from a single `setInterval(onFrame, 50)` (~20 fps target; pass `h` as
  an argument to avoid a closure lookup). Do **not** use `requestAnimationFrame` (absent).
- For performance-critical functions add a directive as the first statement:
  - `"ram"` — run from RAM (also pretokenises the function): the main frame loop.
  - `"jit"` — compile to native for tight numeric loops. One directive per function.
- Whitespace and comments inside loop bodies cost time every iteration — keep comments out of
  hot loops.
- In loops of 50+ iterations, bind a hot graphics method to a local
  (`let r = h.fillRect.bind(h);`). Do not do this for small loops — the block cost outweighs
  the saving.

### 4.4 Redraw discipline

- **Minimize pixels written per frame.** Use **dirty flags**: set a flag when state changes,
  redraw only the flagged region with `h.clearRect(...)` + targeted draws.
- Debounce redraws for continuous knob input: coalesce with a short `setTimeout` so the
  screen redraws once movement settles.
- Cache expensive results: pre-wrap text with `h.wrapString(...)` once and store the lines
  (and their pixel height) rather than re-wrapping per frame.

### 4.5 Deferred init & modules

- Defer heavy asset loading out of the constructor with `setTimeout(fn, 0)` so the app returns
  its contract object promptly; call `E.defrag()` before large allocations.
- Load modules from the SD card **on demand** and unload them:
  ```js
  Modules.addCached("Cron", require("fs").readFileSync("MODULES/Cron.min.js"));
  require("Cron");
  // ...use it...
  Modules.removeCached("Cron");
  ```
  Ship the `.min.js` form of any module.

### 4.6 Persistence

- Persist app config/state as JSON on the SD card via `require("fs")`:
  ```js
  require("fs").writeFileSync("USER/MYAPP.json", JSON.stringify(state));
  var state = JSON.parse(require("fs").readFileSync("USER/MYAPP.json"));
  ```
- **Never** call the global `save()` to persist app state — it snapshots the whole
  interpreter and is not app-scoped.

---

## 5. Graphics (`h` / `g` / `bC`)

The Mk V exposes both a firmware-level buffer set and (under the loader) an app graphics
instance. Resolve defensively so one codebase works across firmware/loader versions:

```js
var G = (typeof h !== "undefined" && h) ? h
      : (typeof bC !== "undefined" && bC) ? bC
      : g;
```

- **`h`** — app graphics instance provided by the loader contract (Form A). Preferred for new
  apps.
- **`g`** — full-screen firmware instance. **`bH` / `bC` / `bF`** — page header / content /
  footer buffers. `bC.flip()` blits the 2-bit offscreen content buffer to the panel **with the
  scanline effect**. `BGRECT` gives `bC`'s live bounds.
- Chain drawing calls: `G.setColor(n).setFontMonofonto16().setFontAlign(x, y).drawString(t, x, y)`.
- `setFontAlign(x, y)`: `-1` left/top, `0` center, `1` right/bottom.
- Fonts: `Fixedsys16`, `Monofonto14/16/18/23/28/36/96/120`. Both `G.setFont("Monofonto23")`
  and `G.setFontMonofonto23()` forms exist; prefer `G.setFont(name)` for portability across
  firmware where the chained setters may not all be present (feature-detect if unsure).
- Color is monochrome: pick a **single hue** at varying brightness for all screen content —
  never a second hue on-screen. Fallout-3 Pip-Boy green `#1AFF80`, New-Vegas amber `#FFB642`,
  terminal green `#6DDA76`; background is near-black. Under the buffer model, palette is set
  via `Pip.setPalette(pal)` (a 4-element array of 16-entry `Uint16Array`s) with colors from
  `G.toColor(r, g, b)`.
- Manual flips: only if you are driving rendering yourself. Set `Pip.lastFlip = getTime()`
  around an explicit `G.flip()` to suppress the OS auto-blit for that frame. For the default
  `setInterval` loop the OS auto-flush is already synchronized — do not add stray flips
  (causes tearing). `Pip.lastFlip` / `Pip.blitOptions` partial-update are loader/firmware
  conventions — feature-detect before relying on them.
- Prefer a single `G.drawImage(bitmap, x, y)` over many `fillRect`/`drawLine` calls for
  sprites; images must be **≤ 4bpp** bitmaps (see §7).

---

## 6. Input & Hardware

### 6.1 The three events

- `Pip.on("knob1", fn)` — left scroll wheel. `fn(dir)` where `dir > 0` = up/CW, `dir < 0` =
  down/CCW, `dir === 0` = press/click. The OS may pass a second arg `true` for a long press:
  `function onKnob1(dir, long) { if (dir === 0 && long) {...} }`.
- `Pip.on("knob2", fn)` — top thumbwheel, same `dir` semantics.
- `Pip.on("torch", fn)` — top torch button. Commonly the **exit / back** control.
- Detach with `Pip.removeListener("knob1", fn)` or `Pip.removeAllListeners("knob1")`. Some
  firmware exposes `Pip.onExclusive(...)` (registers as sole listener) — feature-detect; if
  absent, `removeAllListeners` then `on`.
- `Pip.knob1Click(dir)` / `Pip.knob2Click(dir)` play the native detent click audio
  (`UI/ROT_V_1.wav` / `UI/ROT_V_2.wav`; firmware < 2v24.206 used `UI/PREV.wav`). Call for
  authentic feedback.

```js
function onKnob1(dir) {
  if (dir) { selected = E.clip(selected + dir, 0, last); draw(); }  // rotate
  else { activate(selected); }                                      // click
}
Pip.on("knob1", onKnob1);
```

### 6.2 The mode-selector dial (Mk V-specific)

STATS / INV / DATA / MAP / RADIO are chosen by a physical **resistor ladder**, read as an
analog voltage — **not** discrete mode buttons (this is a key hardware difference from the
3000). Approximate voltages via `Pip.measurePin(MODE_SELECTOR)`:

| Position | ≈ Voltage |
|----------|-----------|
| STAT     | 0.03      |
| INV      | 1.35      |
| DATA     | 2.67      |
| MAP      | 4.02      |
| RADIO    | 5.35      |

Do not assume a "mode button" event exists. For Form A apps, `notDefault: true` means turning
the dial away navigates out of the app (firing `remove()`); do not try to intercept the dial
as a general-purpose input.

### 6.3 Buttons via `setWatch`

For buttons without a `Pip.on` event, `setWatch(fn, PIN, { edge: "rising", debounce: 20 })`
is acceptable — this is the exception, not the default, and every `setWatch` must be
`clearWatch`-ed in `remove()`. Never call a bare `clearWatch()` at init (it clears OS/system
watches). See Appendix A for pin names.

### 6.4 Feature-detection (mandatory)

This device exposes hardware and helpers the public docs do not fully specify, and behavior
differs across firmware. For any method not in the confirmed Mk V surface (Appendix B, "Mk V
confirmed"), check it exists and wrap the call:

```js
if (typeof Pip.someMethod === "function") { try { Pip.someMethod(); } catch (e) {} }
```

A missing feature must **degrade gracefully**, never crash the app or trap the user.

---

## 7. Sound, Assets & Media Formats

- **UI feedback:** `Pip.knob1Click(dir)` / `Pip.knob2Click(dir)` for detents;
  `Pip.audioBuiltin(name)` returns a byte buffer for built-ins (`"OK"`, `"OK2"`, `"PREV"`,
  `"NEXT"`, `"COLUMN"`, `"CLICK"`) for use with `Pip.audioStartVar`. `Pip.playSound("TAB")`
  exists on some firmware — feature-detect.
- **Playback:** `Pip.audioStart(path)` plays a WAV from the card (supports `{ repeat: true }`);
  `Pip.audioStartVar(buffer, opts)` plays an in-memory buffer
  (`{ encoding: "adpcm", sampleRate, blockAlign, overlap }`); `Pip.audioRead(path)` loads a
  WAV for rapid replay; `Pip.audioStop()` stops all audio. `Pip.setVol(0..33)` sets volume.
- **Stream, don't load.** Play large audio/video from the card; do not read big media fully
  into RAM. Video: `Pip.videoStart(path, { x, y, repeat })` / `Pip.videoStop()`.
- **Audio format** — 16-bit mono WAV, 16 kHz:
  ```sh
  ffmpeg -i in.ogg -ac 1 -ar 16000 out.wav
  ```
  (ADPCM `adpcm_ima_wav` is much smaller; prefer it for bundled effects.)
- **Video format** — MS-RLE, 8-bit paletted, ≤ 480 wide, ~12 fps, grayscale:
  ```sh
  ffmpeg -i in.mp4 -vf "scale=480:-1,format=gray" -r 12 -c:v msrle -pix_fmt pal8 \
    -c:a adpcm_ima_wav -ac 1 -ar 16000 out.avi
  ```
- **Images** — ≤ 4bpp bitmaps only. Convert with the Espruino Image Converter
  (`https://www.espruino.com/Image+Converter`) or the pip-boy.com image converter. Load via
  `eval(require("fs").readFileSync("USER/MYAPP/IMG.JS"))` or inline with `atob(...)` for small
  sprites; stream large images into `G.buffer` in chunks with `E.openFile`.

---

## 8. Registration & Metadata

Each app carries a `package.json` describing it to the build/registry. Minimum fields:

```json
{
  "name": "My App Name",
  "id": "myappname",
  "version": "1.0.0",
  "author": "@your-username",
  "description": "One-sentence description.",
  "type": "app",
  "icon": "assets/icon.png",
  "storage": [
    { "name": "USER/MYAPPNAME.js", "url": "MyAppName.min.js" }
  ]
}
```

| Field       | Rules |
|-------------|-------|
| `name`      | Human-readable display name for pip-boy.com. |
| `id`        | Lowercase alphanumeric (+ hyphens). Unique in the registry. Maps to the on-card `USER/<ID>.js` (uppercased). |
| `version`   | Semver. |
| `author`    | GitHub username(s), `@`-prefixed, space-separated. |
| `type`      | Exactly `"app"` or `"game"`. |
| `icon`      | PNG path relative to the app directory. |
| `storage`   | Array of `{ name, url }`: `name` = on-card path (`USER/<ID>.js`, plus any assets under `USER/<ID>/...`), `url` = file in the app directory (ship the `.min.js`). |

An **optional** `APPINFO/<id>.json` (`{ "id": "...", "name": "..." }`) can be placed on the
card so the firmware shows a friendly name for a bare `USER/<id>.js`; the APPINFO filename is
irrelevant — only the `id` inside links it to `USER/<id>.js`. Prefer the repository
`package.json` as the source of truth and treat `APPINFO` as a device-side convenience.

---

## 9. Conversion Rules (3000 → Mk V)

When converting an app written for the newer Pip-Boy 3000 to the Mk V, apply this mapping.
Preserve behavior; change only what the platform requires.

| Concern | Pip-Boy 3000 (source) | Pip-Boy 3000 Mk V (target) |
|---|---|---|
| Placement | ITEMS > MISC | **INV > APPS** |
| Metadata | `APPINFO/<ID>.info` (required) | repo `package.json` (§8); optional `APPINFO/<id>.json` on card |
| App JS location | `APPS/*.JS` | **`USER/<id>.js`** |
| App structure | closure + `remove()` (`notDefault`, `fullscreen`) | Form A (same shape) — keep it; ensure clean exit |
| Exit | OS closes app on navigate-away | dial navigate-away (Form A) or `submenuApps()` (Form B) |
| Graphics instance | `h` | `h` under the loader; `g` / `bC` (+ `bC.flip()`) natively — use the §5 resolver |
| Mode input | STATS/ITEMS/DATA **buttons** | **resistor-ladder dial** via `Pip.measurePin(MODE_SELECTOR)` — do not expect button events |
| Inventory/player APIs | `Player`, `DataFile`, `InvFile`, `player.additem()`, `player.sync()` | **Not available** — rework or remove the feature |
| Display bounds | 320×480 (validate) | 480×320 surface; keep content in `x ∈ [38, 438]` |
| Storage | (3000 card) | 256 MB FAT16; `USER/` apps, `MODULES/`, `USER_BOOT/`, `APPINFO/` |

**Procedure for each converted app:**

1. Confirm the app does not depend on `Player` / `DataFile` / `InvFile`. If it does, redesign
   that feature (SD-card JSON via `require("fs")` is the usual substitute for config/state) or
   drop it, and note the change in the PR.
2. Move code to `USER/<id>.js`; keep Form A structure and verify `remove()` detaches every
   listener/timer/watch and stops audio (§3.3).
3. Replace 3000 asset paths (`APPS/...`) with `USER/<id>/...`; re-encode media per §7.
4. Swap any hard reference to `h` for the §5 resolver if the app must also run against the raw
   `g`/`bC` buffers; respect the 38–438 visible bounds.
5. Replace any mode-**button** assumption with dial-aware behavior (§6.2). Map secondary
   actions onto `knob1` / `knob2` / `torch`.
6. Feature-detect every non-core `Pip.*` call (§6.4). Do not assume `onExclusive`,
   `playSound`, `blitOptions`, `lastFlip`, or chained font setters exist on all firmware.
7. Rebuild `.min.js` (§12), test open/close repeatedly on device, run the review checklist
   (§10).

Legacy Mk V apps you encounter may be **Form B** (bare `USER/*.js` ending in
`submenuApps()`). Convert them to Form A: wrap in the closure, move teardown into `remove()`,
remove the explicit `submenuApps()` call.

---

## 10. Review & Audit Rules

When auditing a PR, run every Mandatory check. Flag each failure with its rule ID and a
one-line reason.

### 10.1 Mandatory (hard) checks

| # | Check | How to verify |
|---|-------|---------------|
| R01 | Form A structure: source is a non-invoked `(function() {...})` with **no** trailing `()`. | Read source head/tail. |
| R02 | Return object has `id` (string) and `remove` (function). | Find the `return`. |
| R03 | Every `Pip.on`/`Pip.onExclusive` has a matching removal in `remove()`. | Cross-reference each registration. |
| R04 | Every `setInterval`/`setTimeout` handle is cleared in `remove()`. | Cross-reference each timer. |
| R05 | Every `setWatch` is `clearWatch`-ed in `remove()`. | Cross-reference each watch. |
| R06 | `remove()` never calls `load()`, `E.reboot()`, `save()`, or `submenuApps()`. | grep `remove()` body. |
| R07 | No `Player` / `DataFile` / `InvFile` / `player.*` usage (3000-only). | grep the source. |
| R08 | No mode-**button** assumption; mode input uses the dial model or is left to the OS. | Inspect input handling vs §6.2. |
| R09 | No unsupported ES features: no `async`/`await`, no `import`/`export`, no template literals. | grep `async`, `` ` ``, `import`. |
| R10 | Uses `Math.randInt(n)`, not `Math.floor(Math.random()*n)`. | grep `Math.random`. |
| R11 | Images are ≤ 4bpp bitmaps; audio 16 kHz mono WAV; video MS-RLE ≤ 480w. | Inspect `assets/`. |
| R12 | `package.json` `type` is `"app"` or `"game"`; `version` is valid semver; `id` maps to `USER/<ID>.js`. | Validate metadata. |
| R13 | `.min.js` exists, preserves Form A, and matches the source's behavior. | Spot-check structure/identifiers. |
| R14 | No OS globals deleted/reassigned; no bare `clearWatch()` at init. | grep risky assignments. |
| R15 | Non-core `Pip.*` calls are feature-detected/guarded. | Inspect against §6.4. |
| R16 | `README.md` (controls + description) and `ChangeLog` exist. | Read the files. |

### 10.2 Soft checks (recommend, do not block)

| # | Check | Rationale |
|---|-------|-----------|
| S01 | Dirty-flag redraw; minimal pixels per frame. | Latency, battery. |
| S02 | `"ram"` on the frame loop; `"jit"` on tight numeric loops. | Speed. |
| S03 | Heavy asset loading deferred with `setTimeout(0)`; `E.defrag()` before big allocs. | Responsive init, less fragmentation. |
| S04 | Typed arrays for dense numeric data; arrays/objects kept shallow. | Memory + speed. |
| S05 | Single-use values inlined; constants hardcoded; constants grouped. | Fewer blocks. |
| S06 | `h` referenced directly (no alias); §5 resolver used if targeting `g`/`bC` too. | Fewer blocks, portability. |
| S07 | Opens/closes repeatedly without crashing or leaking (verifies `remove()`). | Robustness. |
| S08 | Content stays within `x ∈ [38, 438]`. | Nothing hidden by the shroud. |

### 10.3 Output template

```markdown
## App Review: `<App Name>` (Mk V)

### Mandatory
- [x] R01 — Form A, not self-invoked
- [ ] R07 — Uses `player.additem` (3000-only); must be reworked
- ...

### Soft
- [x] S01 — Dirty flags used
- [ ] S05 — `W`/`H` reassigned in a reset function

### Verdict: FAIL — 1 mandatory check failed (R07).
```

---

## 11. Anti-Patterns (Do Not Generate)

| Anti-pattern | Why it is wrong |
|---|---|
| `var` | Wastes blocks; `const`/`let` are clearer. |
| `async`/`await`, `import`/`export`, template literals | Not supported by Espruino. |
| `Math.random()` | Use `Math.randInt(n)`. |
| `requestAnimationFrame`, `fetch`, `XMLHttpRequest` | Not available on the device. |
| `Player` / `DataFile` / `InvFile` / `player.*` | 3000-only APIs; absent on the Mk V. |
| Assuming STATS/ITEMS/DATA **button** events | Mk V mode input is a resistor-ladder dial (§6.2). |
| `load()` / `E.reboot()` / `save()` / `submenuApps()` inside `remove()` | Corrupts clean exit; the OS must restore prior state. |
| Global `save()` for app state | Snapshots the whole interpreter; use SD-card JSON. |
| Deleting/reassigning OS globals; bare `clearWatch()` at init | Destroys OS state; no app watches exist at init. |
| `let c = h` (aliasing the graphics instance) | Wastes a block; reference `h`/`G` directly. |
| Declaring an `APP_ID` constant | Put the id literal in the return object. |
| Storing functions in arrays/objects; nesting > 4 levels | Wastes blocks, hurts performance. |
| Strings > ~256 chars; images > 4bpp or unconverted | Wastes scarce blocks/storage. |
| Stray `h.flip()` inside a `setInterval` loop | Fights the OS auto-flush; causes tearing. |
| Reading large media fully into RAM | Stream from SD instead. |
| Calling undocumented `Pip.*` without a feature-detect guard | Firmware-dependent; must degrade gracefully. |

---

## 12. Build, Minification & Deployment

Produce `<App>.min.js` from the source in two passes.

**1. Minify** (preserve the Form A wrapper; do not strip side-effectful calls):

```sh
terser App.js -c negate_iife=false,side_effects=false -o App.min.js
```

**2. Pretokenise** with the Espruino CLI (numeric bytecode; ~10–20% faster parse/exec):

```sh
espruino App.min.js --config PRETOKENISE=2 --config SET_TIME_ON_WRITE=false -o App.min.js
```

**Local dev / test loop:**
- Repo tooling is Node-based: install deps (`yarn` / `npm install`), then run the local loader
  (`npm run start` → `http://localhost:3000`) to upload and test over Web Serial (Chrome).
- Or connect the device in the **Espruino Web IDE** over Web Serial and run code live in the
  left-hand console. **Never** click the center "Send to Espruino" / flash icons — you can
  overwrite the firmware. `espruino --watch` auto-uploads on save for a CLI workflow.
- Always **back up the entire SD card** before changing anything on the device. Reboot to see
  a newly added app under INV > APPS.

**Publishing:** open a PR to `CodyTolene/pip-boy-3000-mk-v-apps` with the app directory
(source, `.min.js`, `package.json`, `README.md`, `ChangeLog`, `assets/`) so it becomes
installable from pip-boy.com.

---

## Appendix A: Mk V Hardware Pin Reference

Aliases the firmware defines for the standard Espruino pins:

```
LED_RED = E4      LED_GREEN = E5    LED_BLUE = E6     LED_TUNING = E3
BTN_PLAY = A1     BTN_TUNEUP = E1   BTN_TUNEDOWN = E2 BTN_TORCH = A2
BTN_POWER = A0
KNOB1_A = B1      KNOB1_B = B0      KNOB1_BTN = A3
KNOB2_A = A10     KNOB2_B = A8
MODE_SELECTOR = A7    (resistor ladder; read with Pip.measurePin — see §6.2)
SDCARD_DETECT = A15   MEAS_ENB = C4   LCD_BL = B15
VUSB_PRESENT = A9  VUSB_MEAS = A5   VBAT_MEAS = A6   CHARGE_STAT = C5
RADIO_AUDIO = A4      (FM receiver: RDA5807M)
```

Fun facts the firmware bakes in: the system clock defaults to the moment the bombs fell
(`2077-10-23T09:47`); holding **torch + play + knob1** enters factory test mode.

---

## Appendix B: Quick Reference

**Mk V confirmed** (documented in the RobCo Mk V docs — safe to use without guarding):
`Pip.on("knob1"|"knob2"|"torch", fn)`, `Pip.removeListener`, `Pip.removeAllListeners`,
`Pip.knob1Click(dir)`, `Pip.knob2Click(dir)`, `Pip.typeText(text)` (→ Promise),
`Pip.audioStart(path)`, `Pip.audioStop()`, `Pip.isSDCardInserted()`, `Pip.getID()`,
`Pip.measurePin(pin, samples=10, factor=2)`, `Pip.offAnimation()`,
`Pip.offOrSleep({forceOff, immediate})`, `Pip.updateBrightness()` (uses `Pip.brightness`),
`submenuApps()` (Form B exit), `Modules.addCached`/`removeCached`, `require("fs")`,
`E.openFile`, `E.clip`, `E.defrag`, `Math.randInt`.

**Loader / newer-firmware conventions** (present in the community loader and current firmware,
but **feature-detect** before relying on them across versions): `Pip.onExclusive`,
`Pip.playSound("TAB"|"SCROLL")`, `Pip.audioStartVar`, `Pip.audioRead`, `Pip.audioBuiltin`,
`Pip.videoStart`/`videoStop`, `Pip.setVol`, `Pip.lastFlip`, `Pip.blitOptions.y1/y2`,
`Pip.shadeBox`, `Pip.screenGlitch`, `Pip.errorBox`, `Pip.log`, the `notDefault`/`fullscreen`
return-object flags, and chained font setters like `h.setFontMonofonto16()`.

**Graphics (`G` = h | bC | g):** `clear([c])`, `clearRect(x1,y1,x2,y2)`, `setColor(n)`,
`setBgColor(n)`, `setFont(name)`, `setFontAlign(x,y)`, `drawString(t,x,y)`,
`drawRect`/`fillRect`, `drawLine`, `drawCircle`/`fillCircle`, `drawImage(img,x,y[,opts])`,
`wrapString(t,w)`, `stringWidth(t)`, `getWidth()`→480, `getHeight()`→320, `reset()`;
buffer-model: `bC.flip()` (scanline blit), `BGRECT`, `Pip.setPalette(pal)`, `G.toColor(r,g,b)`.

**Espruino utility:** `process.memory()`, `E.getSizeOf(value, 1)`, `E.toFlatString`,
`E.sum`/`E.variance`, `DataView`, typed arrays.

Full references: Mk V API `https://log.robco-industries.org/documentation/pipboy-3000/`;
Espruino Graphics `https://www.espruino.com/Reference#Graphics`.

---

## Appendix C: Firmware Safety & Recovery

Agents must not generate code or instructions that risk bricking the device, and should
surface these facts when a contributor is flashing or recovering hardware:

- **Do not** trigger firmware writes from app code. The Espruino Web IDE "Send to Espruino"
  icons can overwrite firmware — avoid them for app development.
- **FW.js restore:** turning the radio tuner knob fully right to a distinct click and holding
  it while holding power at boot erases flash and copies `FW.js` from the SD card in its place.
- **DFU mode:** hold power + torch and press the hidden reset button under the foam cushion
  (near the battery) with a straightened paperclip; reflash `pipboy.bin` with the firmware
  upgrade utility or The Wand Company's web tool.
- Always keep a full SD-card backup and a copy of the OS ZIP / `pipboy.bin` before changes.

---

## Appendix D: Minimal Templates

**Form A (required for new/converted apps):**

```js
(function() {
  var G = (typeof h !== "undefined" && h) ? h : (typeof bC !== "undefined" && bC) ? bC : g;
  var sel = 0, tick;

  function draw() {
    G.clearRect(38, 40, 438, 300);
    G.setColor(3).setFont("Monofonto28").setFontAlign(0, 0)
     .drawString("SEL: " + sel, 240, 160);
  }
  function onKnob1(dir) {
    if (dir) { sel = E.clip(sel + dir, 0, 9); Pip.knob1Click(dir); draw(); }
  }
  function onTick() { /* animation/logic; set dirty flags, draw changed regions */ }

  Pip.on("knob1", onKnob1);
  tick = setInterval(onTick, 50);
  draw();

  return {
    id: "MYAPP",
    notDefault: true,
    fullscreen: true,
    remove: function() {
      clearInterval(tick);
      Pip.removeListener("knob1", onKnob1);
      Pip.audioStop();
    }
  };
});
```

**Form B (firmware-native; recognize, then convert to Form A):**

```js
// USER/MyApp.js  — appears under INV > APPS
Pip.on("knob1", onKnob1);
function onKnob1(dir) {
  if (dir === 0) {                       // click = exit
    Pip.removeListener("knob1", onKnob1); // MANUAL teardown before leaving
    submenuApps();
  }
}
```
