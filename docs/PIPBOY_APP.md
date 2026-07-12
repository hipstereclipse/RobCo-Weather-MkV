# Pip-Boy App

The on-device app source lives at `pipboy/WEATHER.js` (shipped as the minified
`pipboy/WEATHER.min.js`, installed to `USER/WEATHER.js` on the card). It is an
Espruino app that loads cached JSON from the SD card and renders three weather
views on the Pip-Boy 3000 Mk V screen.

## App Structure

The Mk V firmware runs `USER/*.js` files as plain scripts, top to bottom, the
same way the official Wand Company apps run. `WEATHER.js` therefore:

- starts with the official submenu-takeover preamble (guarded calls to any
  previous `Pip.removeSubmenu` / `Pip.remove`),
- runs inside one invoked closure that draws directly to the `g` graphics
  instance using the device theme color (`g.theme.fg`), and
- registers its teardown (listener removal, audio stop) on `Pip.remove` and
  `Pip.removeSubmenu`, which the firmware calls when the mode dial is turned
  away from the app.

There is no returned `{id, remove}` object — that is the Pip-Boy 3000's app
contract, and nothing on the Mk V invokes it.

## App Metadata

The registry metadata file is:

```text
pipboy/metadata.json
```

It follows the pip-boy.com registry schema
(`CodyTolene/pip-boy-3000-mk-v-apps`) and registers:

- App id: `weather`
- Menu name: `Weather`
- On-card file: `USER/WEATHER.js` (built from `WEATHER.min.js`)
- Icon: `assets/icon.png` (PNG registry icon)
- Required data file: `USER/WEATHER.JSON` (written by the companion)

An optional on-card `APPINFO/weather.json` (`{"id": "weather", "name":
"Weather"}`) gives the firmware a friendly name for `USER/WEATHER.js` under
INV > APPS; the install copies it too.

After copying app files to the SD card, reboot the Pip-Boy so the app list is
rebuilt.

## Data Lookup

The app checks these paths in order:

```text
USER/WEATHER.JSON
WEATHER.JSON
USER/WEATHER.json
```

`USER/WEATHER.JSON` is the normal companion output path. The fallback names are
there to make manual testing easier.

## Controls

| Control | Action |
| --- | --- |
| Scroll wheel rotate | Change selected location in site mode, or selected on-screen item in item mode. |
| Scroll wheel press | Toggle between site mode and item mode. |
| Top thumbwheel (knob 2) rotate | Change view. |
| Mode selector dial | Exit the app (turn to any other mode). |

Turning the Mk V's STATS/INV/DATA/MAP/RADIO dial away from the app exits it:
the firmware calls the app's registered `Pip.remove`/`Pip.removeSubmenu`
teardown and loads the new mode's screen. There are no mode buttons on the
Mk V, the top thumbwheel has no press action, and the torch button keeps its
stock flashlight behavior.

## Views

The app uses three RobCo-style terminal tabs: `ATMOS`, `5-DAY`, and `SOLAR`.
Each tab is rendered as a monochrome phosphor screen with framed terminal
panels, site IDs, scanline masking, and compact instrument readouts.

### ATMOS

The `ATMOS` view shows:

- Location and region.
- Weather icon.
- Current temperature and unit.
- Condition description.
- Today's forecast high/low and rain chance.
- Apparent temperature.
- Wind speed and direction.
- Humidity.
- UV index labeled as `RAD UV` for flavor.
- Observed timestamp.
- Compact solar activity line when space-weather data exists.
- Selectable telemetry rows for apparent temperature, wind, humidity, and UV;
  item mode shows a compact detail strip for the selected row.

If aurora is possible or likely for the selected location, the solar line also
shows the aurora status.

### 5-DAY

The `5-DAY` view shows a 5-day terminal buffer:

- Day label.
- Weather icon.
- High/low temperatures.
- Precipitation probability.
- A selected-day detail strip. Press the scroll wheel to enter item mode, then
  rotate it to inspect individual forecast days without changing city.

The companion currently writes five forecast days.

### SOLAR

The `SOLAR` view shows:

- Latest flare class.
- NOAA R-scale, S-scale, and G-scale.
- Current planetary Kp and the forecast peak Kp.
- NOAA geomagnetic text.
- 3-day Kp forecast graph.
- Per-location aurora threshold line.
- Aurora verdict for the selected location.
- Selectable Kp forecast slots in item mode.

Aurora estimates use geographic latitude and a simple Kp-to-viewing-latitude
table. Treat them as a fun guide, not a scientific guarantee.

## Stale Cache Warning

The companion writes a UTC epoch timestamp into `WEATHER.JSON`. The app uses
that timestamp to calculate cache age.

By default, data older than 12 hours is stale (the threshold in `stale()`).

When stale, the header's left label is replaced with a `! DATA <age> OLD - SYNC`
warning and the footer switches from `UPD` to `!`.

Change the `12` in `stale()` in `WEATHER.js` if you want a different threshold.

## Display Assumptions

The app targets the Pip-Boy 3000 Mk V's fixed landscape drawing surface: 480
by 320 pixels. The case shroud hides the sides of the panel, so only
`x in [38, 438]` (a 400 by 320 window) is visible; every layout coordinate is
hardcoded inside that window. (The official `asteroid` app treats the same
region as visible — it blits a 400-wide buffer at x = 40.)

The header and footer rows are additionally inset horizontally by `CORN`
(56 px) so their text clears the corners of the case opening. If your unit's
opening is tighter and text still clips, increase `CORN` near the top of
`WEATHER.js`.

## Icon

`pipboy/assets/icon.png` is the PNG registry icon generated by:

```bash
python companion/make_icon.py
```

You can regenerate it at a different base grid size or scale:

```bash
python companion/make_icon.py 64 64 3
```

Keep `pipboy/metadata.json` pointed at `assets/icon.png`. (The Mk V has no
holotape `.IMG` menu icons; the old 1-bpp `APPINFO/WEATHER.IMG` was a
Pip-Boy 3000 convention and is gone.)

## Error States

The app can show:

- `NO WEATHER DATA`: no cache file was found.
- `EMPTY DATA FILE`: the cache exists but contains no locations.
- `BAD DATA FORMAT`: the cache could not be parsed as expected JSON.

See [Troubleshooting](TROUBLESHOOTING.md) for fixes.
