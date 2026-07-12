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
- [5. Graphics (`g` / buffers / `Pip.blitImage`)](#5-graphics-g--buffers--pipblitimage)
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
- [Appendix D: Minimal Template](#appendix-d-minimal-template)

---

## 1. Project Context

- **Platform:** Pip-Boy 3000 Mk V — a wearable replica running **Espruino** (a JavaScript
  interpreter) on an STM32 board (Cortex-M4 class). Every app is JavaScript loaded from the
  SD card.
- **Display:** 320×480 px IPS panel, rendered in landscape. The drawing surface is therefore
  **480 wide × 320 tall** (`g.getWidth()` → 480, `g.getHeight()` → 320). The physical panel
  is wider than the case opening: the **visible** region is `x ∈ [38, 438]` (a 400×320 area),
  `y ∈ [0, 320]`. Keep all meaningful content inside those bounds or it hides behind the
  shroud.
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
├── <MyAppName>.min.js       # Plain minified build (see §12; never pretokenised)
├── metadata.json            # Registration metadata for the pip-boy.com registry (see §8)
├── README.md                # Description, controls, install steps, credits
├── ChangeLog                # Version history (dated, with PR links)
└── assets/                  # 4bpp bitmaps, .wav / .avi media, icons, data files
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

> **Correction (2026-07-12).** Earlier revisions of this file described a "Form A loader
> contract" (a non-invoked `(function(){...})` returning `{id, remove, notDefault,
> fullscreen}`) as REQUIRED for the Mk V and claimed "the loader invokes it." **That is the
> Pip-Boy 3000's app model, and it is wrong for this device.** Nothing on the Mk V — stock
> firmware or pip-boy.com — invokes such a closure; a file shipped in that shape evaluates to
> an unused function, draws nothing, registers no handlers, and traps the user on the app
> launch screen until reboot. Verified against the official Mk V docs
> (`robco-industries.org/documentation/pipboy/3000mkv/creating-apps`), the official firmware
> apps (`thewandcompany/pip-boy`, e.g. `asteroid`, `text`), and the pip-boy.com registry apps
> (`CodyTolene/pip-boy-3000-mk-v-apps`, e.g. `diceroller`).

### 3.1 The one real contract: bare script + teardown hooks

The firmware loads `USER/<name>.js` as a **bare top-to-bottom script** that appears under
**INV > APPS**. The script executes at load; it takes over the screen, registers its own
input handlers, and registers teardown on the `Pip.remove` / `Pip.removeSubmenu` hooks,
which the firmware calls when the user turns the mode dial away. Explicit "back to the apps
menu" is `submenuApps()` (after running your own teardown). Standard shape, as used by the
official apps:

```js
// Take over cleanly from the INV > APPS submenu (official app preamble).
if (Pip.removeSubmenu) Pip.removeSubmenu();
delete Pip.removeSubmenu;
if (Pip.remove) Pip.remove();
delete Pip.remove;

(function() {
  // state, helpers, handlers — kept out of the global scope

  function onKnob1(dir) { /* ... */ }

  function teardown() {
    Pip.removeListener("knob1", onKnob1);
    // clearInterval/clearTimeout/clearWatch anything you created
    if (Pip.audioStop) Pip.audioStop();
    delete Pip.remove;
    delete Pip.removeSubmenu;
  }

  // The firmware invokes whichever hook exists on dial-away; official apps
  // use one or the other (asteroid: Pip.remove, text: Pip.removeSubmenu) —
  // registering the same teardown on both is safe and robust.
  Pip.remove = teardown;
  Pip.removeSubmenu = teardown;
  Pip.on("knob1", onKnob1);
  // draw first frame
})();
```

Note the closure **is invoked** — it exists only for scoping, not as a loader handshake.
The official "Hello World" is the same contract in miniature:

```js
Pip.typeText("Hello World!").then(() =>
  setTimeout(() => {
    Pip.typeText("Nice app!").then(() => setTimeout(submenuApps, 3000));
  }, 3000)
);
```

There is **no** `id` / `notDefault` / `fullscreen` return object. Do not generate one.

### 3.2 Recognizing the 3000 shape in incoming code

Code being ported from the Pip-Boy 3000 (or written against old revisions of this file) will
be a **non-invoked** `(function(){ ... })` returning `{id, remove, ...}`. Convert it: add the
submenu-takeover preamble, invoke the closure, move the returned `remove()` body into a
`teardown()` registered on `Pip.remove`/`Pip.removeSubmenu`, and delete the return object.

### 3.3 `teardown()` requirements

`teardown()` MUST undo everything the app created that could outlive it. Maintain a strict
one-to-one teardown for each of these categories:

1. Every `Pip.on(...)` → matching `Pip.removeListener(...)` (or
   `Pip.removeAllListeners("<event>")`).
2. Every `setInterval` → `clearInterval`; every `setTimeout` that may still be pending →
   `clearTimeout`.
3. Every `setWatch` → `clearWatch`.
4. `Pip.audioStop()` if the app played audio.
5. Close any file opened with `E.openFile(...)`.
6. Finally `delete Pip.remove; delete Pip.removeSubmenu;` so the closure can be reclaimed
   and the next page starts from a clean slate. Deleting the hooks also makes a double call
   harmless, so no extra guard is needed.

`teardown()` MUST **never** call `load()`, `E.reboot()`, or `save()`. It should not itself
call `submenuApps()` — the dial-away path navigates on its own; only an explicit in-app
"exit to menu" action calls `teardown()` **then** `submenuApps()`.

---

## 4. Code Generation Rules

Memory and code size are the priority of this repository. Apply every rule; violations are
rejected in review (§10).

### 4.1 Variables & allocation

- Use `const`/`let`; **never `var`**.
- **Minimize declarations.** Every variable is a scarce block. Inline single-use values.
  Hardcode true constants (screen dimensions, grid sizes, colors) rather than naming them.
- Screen size is constant: `const W = 480, H = 320;` (or read once via `g.getWidth()` /
  `g.getHeight()`) — never re-read per frame, never reassign.
- Group related constants into one object (`const C = {...}`) instead of many top-level
  `const`s.
- Do **not** alias the graphics instance (`let c = g`) — reference it directly (§5).
- Do **not** declare an `APP_ID` variable — the Mk V app contract has no id object; the
  on-card filename and `metadata.json` carry the identity (§3, §8).

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

- Drive animation/logic from a single `setInterval(onFrame, 50)` (~20 fps target). Do **not**
  use `requestAnimationFrame` (absent).
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

## 5. Graphics (`g` / buffers / `Pip.blitImage`)

> **Correction (2026-07-12).** There is **no `h` graphics instance on the Mk V** — that is
> the Pip-Boy 3000's global. Do not generate the old `h`/`bC`/`g` resolver: the `h` branch
> never fires, and the `bC` fallback draws into an offscreen buffer that is never shown
> unless you also call `bC.flip()`.

Three rendering paths exist, all verified in shipping apps:

1. **Direct `g`** (simplest; used by pip-boy.com apps such as diceroller). `g` renders
   straight to the 480×320 landscape LCD. Set the color explicitly — `g.theme.fg` is the
   user's UI color (phosphor green by default) and `g.blendColor(g.theme.bg, g.theme.fg, 0.5)`
   gives a dim variant. `g.reset()` applies the theme on current firmware, but don't rely on
   that alone. No flip call; drawing is immediate. There is no hardware scanline overlay on
   this path — fake it with 1-px `clearRect` rows if the aesthetic needs it.
2. **`bC` + `bC.flip()`** (official `text` app). `bH` / `bC` / `bF` are the firmware's
   header / content / footer buffers (≈400 px wide, **buffer-local coordinates**, not
   absolute screen coordinates). Draw into `bC`, then `bC.flip()` blits it **with the
   scanline effect**. Nothing auto-flips: un-flipped drawing is invisible.
3. **Own buffer + `Pip.blitImage(G, x, y)`** (official `asteroid` app; best for animation).
   `Graphics.createArrayBuffer(400, 308, 2, { msb: true, buffer:
   E.toArrayBuffer(E.memoryArea(0x10000000 + 16384, (400*308)>>2)) })`, then
   `Pip.blitImage(G, 40, 7)` per frame. `Pip.blitImage` accepts 2bpp/4bpp images only and
   renders through the firmware palette with the scanline effect. Stay inside the CCM region
   the official app proves free (`0x10000000 + 16384`, ≤ 30 800 bytes).

Shared rules:

- The case shroud hides `x < 38` and `x > 438` of the 480-wide surface; keep meaningful
  content inside `x ∈ [38, 438]` (screen coordinates; translate accordingly for
  buffer-local drawing).
- Chain drawing calls: `g.setColor(c).setFontMonofonto16().setFontAlign(x, y).drawString(t, x, y)`.
- `setFontAlign(x, y)`: `-1` left/top, `0` center, `1` right/bottom.
- Fonts: `Monofonto16/18/23/28/36/96/120` are compiled into the firmware
  (`boards/PIPBOY.py` in espruino/Espruino), plus the Espruino built-in `6x8`
  (scalable: `g.setFont("6x8", 2)`). Both `g.setFont("Monofonto23")` and
  `g.setFontMonofonto23()` forms work.
- Color is monochrome: pick a **single hue** at varying brightness for all screen content —
  never a second hue on-screen. Prefer `g.theme.fg` / `g.theme.bg` over hardcoded hex so the
  user's chosen UI color is respected. Buffer/blit paths render through the firmware
  palette, set via `Pip.setPalette(pal)` (a 4-element array of 16-entry `Uint16Array`s) with
  colors from `g.toColor(r, g, b)`.
- Prefer a single `g.drawImage(bitmap, x, y)` over many `fillRect`/`drawLine` calls for
  sprites; images must be **≤ 4bpp** bitmaps (see §7).

---

## 6. Input & Hardware

### 6.1 The three events

- `Pip.on("knob1", fn)` — left scroll wheel. `fn(dir)` where `dir > 0` = up/CW, `dir < 0` =
  down/CCW, `dir === 0` = press/click. The OS may pass a second arg `true` for a long press:
  `function onKnob1(dir, long) { if (dir === 0 && long) {...} }`.
- `Pip.on("knob2", fn)` — top thumbwheel, same `dir` semantics.
- `Pip.on("torch", fn)` — top torch button. Stock behavior is the flashlight toggle; leave
  it alone unless the app deliberately repurposes it (and then restore expectations on exit —
  the stock toggle is itself a listener, and `removeAllListeners("torch")` kills it for the
  session).
- Detach with `Pip.removeListener("knob1", fn)`. For exclusivity, the official inputs doc's
  pattern is `Pip.removeAllListeners("knob1")` **before** `Pip.on("knob1", fn)` — it also
  clears any handler a badly-torn-down previous app leaked. (`Pip.onExclusive` is not a
  stock API — do not rely on it.)
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

Do not assume a "mode button" event exists. Turning the dial away from an app navigates out
of it: the firmware calls the app's registered `Pip.remove` / `Pip.removeSubmenu` teardown
hooks (§3) and loads the new mode's page. Do not try to intercept the dial as a
general-purpose input.

### 6.3 Buttons via `setWatch`

For buttons without a `Pip.on` event, `setWatch(fn, PIN, { edge: "rising", debounce: 20 })`
is acceptable — this is the exception, not the default, and every `setWatch` must be
`clearWatch`-ed in `teardown()`. Never call a bare `clearWatch()` at init (it clears
OS/system watches). See Appendix A for pin names.

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
  `"NEXT"`, `"COLUMN"`, `"CLICK"`) for use with `Pip.audioStartVar`. `Pip.playSound` is
  **not** a stock API — feature-detect it and fall back to the knob clicks.
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
- **Video format** — MS-RLE, 8-bit paletted, 12 fps. The community guide's proven recipe
  (400 px wide, 408×248 target for UI-tab playback):
  ```sh
  ffmpeg -i in.mp4 -vf "scale=400:-1,format=rgb555le" -r 12 -c:v msrle -pix_fmt pal8 \
    -c:a pcm_s16le -ac 1 -ar 11025 out.avi
  ```
- **Images** — ≤ 4bpp bitmaps only. Convert with the Espruino Image Converter
  (`https://www.espruino.com/Image+Converter`) or the pip-boy.com image converter. Load via
  `eval(require("fs").readFileSync("USER/MYAPP/IMG.JS"))` or inline with `atob(...)` for small
  sprites; stream large images in chunks with `E.openFile`.

---

## 8. Registration & Metadata

Each app carries a **`metadata.json`** describing it to the pip-boy.com registry
(`CodyTolene/pip-boy-3000-mk-v-apps` expects `app.js`, `ChangeLog`, `metadata.json`,
`README.md` per app directory). Fields, per the registry's shipping apps:

```json
{
  "id": "myappname",
  "name": "My App Name",
  "author": "@your-username",
  "version": "1.0.0",
  "description": "One-sentence description.",
  "icon": "assets/icon.png",
  "tags": "app,tool",
  "type": "app",
  "readme": "README.md",
  "storage": [
    { "name": "USER/MYAPPNAME.js", "url": "MyAppName.min.js" }
  ],
  "storageOptional": []
}
```

| Field       | Rules |
|-------------|-------|
| `name`      | Human-readable display name for pip-boy.com. |
| `id`        | Lowercase alphanumeric (+ hyphens). Unique in the registry. Maps to the on-card `USER/<id>.js` (FAT is case-insensitive). |
| `version`   | Semver. |
| `author`    | GitHub username(s), `@`-prefixed, space-separated. |
| `type`      | Exactly `"app"` or `"game"`. |
| `icon`      | PNG path relative to the app directory. |
| `tags`      | Comma-separated keywords shown on pip-boy.com. |
| `storage`   | Array of `{ name, url }`: `name` = on-card path (`USER/<id>.js`, plus any assets under `USER/<ID>/...`), `url` = file in the app directory (ship the `.min.js`). |
| `storageOptional` | Same shape; files the user may skip. |

An **optional** `APPINFO/<id>.json` (`{ "id": "...", "name": "..." }`) can be placed on the
card so the firmware shows a friendly name for a bare `USER/<id>.js`; the APPINFO filename is
irrelevant — only the `id` inside links it to `USER/<id>.js`. Prefer the repository
`metadata.json` as the source of truth and treat `APPINFO` as a device-side convenience.

---

## 9. Conversion Rules (3000 → Mk V)

When converting an app written for the newer Pip-Boy 3000 to the Mk V, apply this mapping.
Preserve behavior; change only what the platform requires.

| Concern | Pip-Boy 3000 (source) | Pip-Boy 3000 Mk V (target) |
|---|---|---|
| Placement | ITEMS > MISC | **INV > APPS** |
| Metadata | `APPINFO/<ID>.info` (required) | repo `metadata.json` (§8); optional `APPINFO/<id>.json` on card |
| App JS location | `APPS/*.JS` | **`USER/<id>.js`** |
| App structure | **non-invoked** closure returning `{id, remove, ...}` — the 3000 loader invokes it | **bare executed script** (§3) — invoke the closure, register teardown on `Pip.remove`/`Pip.removeSubmenu` |
| Exit | OS closes app on navigate-away, calls the returned `remove()` | dial navigate-away fires the `Pip.remove`/`Pip.removeSubmenu` hooks; explicit menu return = teardown + `submenuApps()` |
| Graphics instance | `h` | **no `h`** — `g` direct, `bC` + `bC.flip()`, or own buffer + `Pip.blitImage` (§5) |
| Mode input | STATS/ITEMS/DATA **buttons** | **resistor-ladder dial** via `Pip.measurePin(MODE_SELECTOR)` — do not expect button events |
| Inventory/player APIs | `Player`, `DataFile`, `InvFile`, `player.additem()`, `player.sync()` | **Not available** — rework or remove the feature |
| Display bounds | 320×480 (validate) | 480×320 surface; keep content in `x ∈ [38, 438]` |
| Storage | (3000 card) | 256 MB FAT16; `USER/` apps, `MODULES/`, `USER_BOOT/`, `APPINFO/` |

**Procedure for each converted app:**

1. Confirm the app does not depend on `Player` / `DataFile` / `InvFile`. If it does, redesign
   that feature (SD-card JSON via `require("fs")` is the usual substitute for config/state) or
   drop it, and note the change in the PR.
2. Move code to `USER/<id>.js` and convert the structure per §3.2: submenu-takeover preamble,
   **invoked** closure, returned `remove()` body moved into a `teardown()` registered on
   `Pip.remove`/`Pip.removeSubmenu`, no return object. Verify `teardown()` detaches every
   listener/timer/watch and stops audio (§3.3).
3. Replace 3000 asset paths (`APPS/...`) with `USER/<id>/...`; re-encode media per §7.
4. Replace every `h` reference with a §5 rendering path (usually direct `g` +
   `g.theme.fg`); respect the 38–438 visible bounds.
5. Replace any mode-**button** assumption with dial-aware behavior (§6.2). Map secondary
   actions onto `knob1` / `knob2`; leave `torch` to the stock flashlight unless deliberately
   repurposed.
6. Feature-detect every non-core `Pip.*` call (§6.4). Do not assume `onExclusive`,
   `playSound`, `blitOptions`, or `lastFlip` exist — they are not stock APIs.
7. Rebuild `.min.js` (§12), test open/close repeatedly on device, run the review checklist
   (§10).

Legacy files you encounter in the **3000 shape** (non-invoked closure + return object) do
not run on the Mk V at all — they eval to an unused function and trap the user on the
launch screen. Convert them per §3.2 before anything else.

---

## 10. Review & Audit Rules

When auditing a PR, run every Mandatory check. Flag each failure with its rule ID and a
one-line reason.

### 10.1 Mandatory (hard) checks

| # | Check | How to verify |
|---|-------|---------------|
| R01 | The script **executes at load**: top-level statements run (an invoked closure is fine); it is NOT a bare non-invoked `(function(){...})` expression. | Read source head/tail. |
| R02 | Teardown is registered on `Pip.remove` / `Pip.removeSubmenu`, and the script starts with the guarded submenu-takeover preamble (§3.1). | Find the hook assignments. |
| R03 | Every `Pip.on` has a matching removal in `teardown()`. | Cross-reference each registration. |
| R04 | Every `setInterval`/`setTimeout` handle is cleared in `teardown()`. | Cross-reference each timer. |
| R05 | Every `setWatch` is `clearWatch`-ed in `teardown()`. | Cross-reference each watch. |
| R06 | `teardown()` never calls `load()`, `E.reboot()`, or `save()`; `submenuApps()` is only ever called *after* teardown from an explicit exit action. | grep `teardown()` body. |
| R07 | No `Player` / `DataFile` / `InvFile` / `player.*` usage (3000-only). | grep the source. |
| R08 | No mode-**button** assumption; mode input uses the dial model or is left to the OS. | Inspect input handling vs §6.2. |
| R09 | No unsupported ES features: no `async`/`await`, no `import`/`export`, no template literals. | grep `async`, `` ` ``, `import`. |
| R10 | Uses `Math.randInt(n)`, not `Math.floor(Math.random()*n)`. | grep `Math.random`. |
| R11 | Images are ≤ 4bpp bitmaps; audio 16 kHz mono WAV; video MS-RLE per §7. | Inspect `assets/`. |
| R12 | `metadata.json` `type` is `"app"` or `"game"`; `version` is valid semver; `id` maps to `USER/<id>.js`. | Validate metadata. |
| R13 | `.min.js` exists, is plain minified text (NOT pretokenised), still executes at load, and matches the source's behavior. | Spot-check structure; diff behavior in a harness. |
| R14 | No OS globals deleted/reassigned (beyond the §3.1 hook preamble); no bare `clearWatch()` at init; `removeAllListeners("torch")` only if the app deliberately owns the torch. | grep risky assignments. |
| R15 | Non-core `Pip.*` calls are feature-detected/guarded. | Inspect against §6.4. |
| R16 | `README.md` (controls + description) and `ChangeLog` exist. | Read the files. |
| R17 | No `h` usage and no `h`/`bC`/`g` resolver; rendering follows one §5 path, and every buffer draw has a matching `flip()`/`blitImage`. | grep `h.`, inspect render path. |

### 10.2 Soft checks (recommend, do not block)

| # | Check | Rationale |
|---|-------|-----------|
| S01 | Dirty-flag redraw; minimal pixels per frame. | Latency, battery. |
| S02 | `"ram"` on the frame loop; `"jit"` on tight numeric loops. | Speed. |
| S03 | Heavy asset loading deferred with `setTimeout(0)`; `E.defrag()` before big allocs. | Responsive init, less fragmentation. |
| S04 | Typed arrays for dense numeric data; arrays/objects kept shallow. | Memory + speed. |
| S05 | Single-use values inlined; constants hardcoded; constants grouped. | Fewer blocks. |
| S06 | `g` referenced directly (no alias); `g.theme.fg`/`bg` used instead of hardcoded hex. | Fewer blocks, respects user's UI color. |
| S07 | Opens/closes repeatedly without crashing or leaking (verifies `remove()`). | Robustness. |
| S08 | Content stays within `x ∈ [38, 438]`. | Nothing hidden by the shroud. |

### 10.3 Output template

```markdown
## App Review: `<App Name>` (Mk V)

### Mandatory
- [x] R01 — Bare executed script; closure is invoked
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
| Non-invoked `(function(){...})` returning `{id, remove, ...}` | The 3000 loader contract. Nothing on the Mk V invokes it — the app never runs and traps the user on the launch screen. |
| `load()` / `E.reboot()` / `save()` inside `teardown()` | Corrupts clean exit; the OS must restore prior state. |
| Global `save()` for app state | Snapshots the whole interpreter; use SD-card JSON. |
| Deleting/reassigning OS globals (beyond the §3.1 hook preamble); bare `clearWatch()` at init | Destroys OS state; no app watches exist at init. |
| `let c = g` (aliasing the graphics instance) | Wastes a block; reference `g` directly. |
| Drawing into `bC` (or any buffer) without `flip()`/`blitImage` | Offscreen buffers are never auto-blitted; the screen shows nothing. |
| Pretokenising the shipped `.min.js` | No shipping Mk V app is pretokenised; unverified on device, and a parse failure looks like a silent hang. Ship plain minified text. |
| Storing functions in arrays/objects; nesting > 4 levels | Wastes blocks, hurts performance. |
| Strings > ~256 chars; images > 4bpp or unconverted | Wastes scarce blocks/storage. |
| Relying on an "OS auto-flush" to show buffer drawing | There is none; you own every `flip()`/`blitImage`. |
| Reading large media fully into RAM | Stream from SD instead. |
| Calling undocumented `Pip.*` without a feature-detect guard | Firmware-dependent; must degrade gracefully. |

---

## 12. Build, Minification & Deployment

Produce `<App>.min.js` from the source with **plain terser minification only** (this is what
the pip-boy.com registry's `npm run min` does; do not strip side-effectful top-level calls):

```sh
terser App.js -c negate_iife=false,side_effects=false -m -o App.min.js
```

> **Correction (2026-07-12).** Earlier revisions added an Espruino-CLI `PRETOKENISE=2` pass.
> Do **not** pretokenise: no shipping Mk V app (official or registry) is pretokenised, the
> format is unverified on this firmware's SD-eval path, and a parse failure presents as a
> silent hang on the app launch screen.

Verify the minified build is functionally identical to the source (e.g. run both in a mocked
`Pip`/`g`/`E` harness and diff the draw-call traces) — and remember an off-device harness
says nothing about on-device memory behavior.

**Local dev / test loop:**
- Test uploads with the official app-loader (`https://github.com/thewandcompany/pip-boy`)
  over Web Serial (Chrome), or connect the device in the **Espruino Web IDE** and run code
  live in the left-hand console. **Never** click the center "Send to Espruino" / flash icons —
  you can overwrite the firmware. `espruino --watch` auto-uploads on save for a CLI workflow.
- Always **back up the entire SD card** before changing anything on the device. Reboot to see
  a newly added app under INV > APPS.

**Publishing:** open a PR to `CodyTolene/pip-boy-3000-mk-v-apps` with the app directory
(source, `.min.js`, `metadata.json`, `README.md`, `ChangeLog`, `assets/`) so it becomes
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

**Mk V confirmed** (documented in the RobCo Mk V docs and/or used by official apps — safe to
use without guarding):
`Pip.on("knob1"|"knob2"|"torch", fn)`, `Pip.removeListener`, `Pip.removeAllListeners`,
`Pip.knob1Click(dir)`, `Pip.knob2Click(dir)`, `Pip.typeText(text)` (→ Promise),
`Pip.audioStart(path)`, `Pip.audioStartVar(buf, opts)`, `Pip.audioBuiltin(name)`,
`Pip.audioStop()`, `Pip.videoStart(path, {x,y})`/`Pip.videoStop()`, `Pip.setPalette(pal)`,
`Pip.blitImage(img, x, y, opts)` (2bpp/4bpp), `Pip.isSDCardInserted()`, `Pip.getID()`,
`Pip.measurePin(pin)`, `Pip.offAnimation()`, `Pip.offOrSleep({forceOff, immediate})`,
`Pip.brightness` + `Pip.updateBrightness()`, the `Pip.remove`/`Pip.removeSubmenu` teardown
hooks (§3), `submenuApps()`, `Modules.addCached`/`removeCached`, `require("fs")`,
`E.openFile`, `E.clip`, `E.defrag`, `E.memoryArea`, `Math.randInt`, `g.theme.fg/bg`,
`g.blendColor`.

**Not stock — do not rely on them** (they came from the Pip-Boy 3000 or from bootloader
mods like PipUI+; feature-detect if supporting modded devices): `Pip.onExclusive`,
`Pip.playSound`, `Pip.lastFlip`, `Pip.blitOptions`, `Pip.shadeBox`, `Pip.screenGlitch`,
`Pip.errorBox`, `Pip.log`, the `h` graphics instance, and the `notDefault`/`fullscreen`
return-object flags.

**Graphics (`g`, or a §5 buffer):** `clear([c])`, `clearRect(x1,y1,x2,y2)`, `setColor(c)`,
`setBgColor(c)`, `setFont(name[,scale])`, `setFontAlign(x,y)`, `drawString(t,x,y)`,
`drawRect`/`fillRect`, `drawLine`, `drawCircle`/`fillCircle`, `drawImage(img,x,y[,opts])`,
`wrapString(t,w)`, `stringWidth(t)`, `getWidth()`→480, `getHeight()`→320, `reset()`;
buffer-model: `bH`/`bC`/`bF` + `.flip()` (scanline blit), `Pip.setPalette(pal)`,
`g.toColor(r,g,b)`.

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

## Appendix D: Minimal Template

**Mk V app (required shape for new/converted apps)** — `USER/myapp.js`, appears under
INV > APPS:

```js
// Take over cleanly from the INV > APPS submenu.
if (Pip.removeSubmenu) Pip.removeSubmenu();
delete Pip.removeSubmenu;
if (Pip.remove) Pip.remove();
delete Pip.remove;

(function() {
  let sel = 0, tick;

  function draw() {
    g.reset().clear();
    if (g.theme && g.theme.fg !== undefined) g.setColor(g.theme.fg);
    g.setFont("Monofonto28").setFontAlign(0, 0)
     .drawString("SEL: " + sel, 240, 160);
  }
  function onKnob1(dir) {
    if (dir) { sel = E.clip(sel + dir, 0, 9); Pip.knob1Click(dir); draw(); }
    else exit();                         // click = back to the apps menu
  }
  function onTick() { /* animation/logic; set dirty flags, draw changed regions */ }

  function teardown() {
    clearInterval(tick);
    Pip.removeListener("knob1", onKnob1);
    if (Pip.audioStop) Pip.audioStop();
    delete Pip.remove;
    delete Pip.removeSubmenu;
  }
  function exit() { teardown(); submenuApps(); }

  Pip.remove = teardown;      // fired on mode-dial navigate-away
  Pip.removeSubmenu = teardown;
  Pip.removeAllListeners("knob1"); // exclusivity per the official inputs doc
  Pip.on("knob1", onKnob1);
  tick = setInterval(onTick, 50);
  draw();
})();
```

**The 3000 shape (recognize in incoming code; convert per §3.2 — it does NOT run on the
Mk V):**

```js
(function() {
  // ...
  return { id: "MYAPP", notDefault: true, fullscreen: true, remove: function() {} };
});  // no invocation — the 3000's loader calls it; the Mk V never does
```
