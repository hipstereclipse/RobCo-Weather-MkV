# Development

This project is split into a companion side and a Pip-Boy side. The companion
does network work and writes JSON. The Pip-Boy app only reads JSON and draws
the UI.

## Layout

```text
companion/pipboy_weather.py      Fetch engine, CLI, config, JSON writer.
companion/pipboy_weather_gui.py  Tkinter UI over the fetch engine.
companion/render_preview.py      Pillow renderer for preview PNGs.
companion/make_icon.py           Espruino 1-bpp icon generator.
pipboy/APPS/WEATHER.JS           On-device app.
pipboy/APPINFO/WEATHER.info      App metadata.
pipboy/APPINFO/WEATHER.IMG       Generated holotape icon.
sample/WEATHER.JSON              Sample payload for previews and simulator use.
previews/*.png                   Generated screenshots.
docs/*.md                        Project documentation.
```

## Local Validation

Run these checks after changing Python or sample JSON:

```bash
python -m py_compile companion/pipboy_weather.py companion/pipboy_weather_gui.py companion/render_preview.py companion/make_icon.py
python -m json.tool sample/WEATHER.JSON
```

`py_compile` verifies Python syntax without making network calls. `json.tool`
verifies that the sample payload parses correctly.

## Regenerating Previews

Install Pillow if needed:

```bash
python -m pip install pillow
```

Then run:

```bash
python companion/render_preview.py
```

The renderer reads `sample/WEATHER.JSON` by default and writes:

```text
previews/01_current.png
previews/02_forecast.png
previews/03_space_weather.png
previews/04_current_solar.png
previews/05_stale_warning.png
previews/06_companion_gui.png
```

You can render from another payload:

```bash
python companion/render_preview.py path/to/WEATHER.JSON
```

The preview renderer approximates the Espruino layout with Pillow. It is useful
for documentation and visual review, but exact device fonts and metrics can
differ.

## Regenerating the Icon

Run:

```bash
python companion/make_icon.py
```

The default output is:

```text
pipboy/APPINFO/WEATHER.IMG
```

To generate a different size:

```bash
python companion/make_icon.py 64 64
```

The icon format is:

- Byte 0: width.
- Byte 1: height.
- Byte 2: bits per pixel, currently `1`.
- Remaining bytes: packed pixels, most-significant bit first, continuous
  across rows.

## Data Source Endpoints

The companion uses:

- `https://geocoding-api.open-meteo.com/v1/search`
- `https://api.open-meteo.com/v1/forecast`
- `https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json`
- `https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json`
- `https://services.swpc.noaa.gov/products/noaa-scales.json`
- `https://services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json`

Keep the companion tolerant of partial failures. Weather for one failed
location should not prevent other locations from being written, and a failed
space-weather endpoint should not prevent normal weather output.

## Editing the Pip-Boy App

The app is written as a self-contained function expression because that is the
shape expected by the Pip-Boy app loader. Preserve the returned object with:

```javascript
{
  id: "WEATHER",
  notDefault: true,
  fullscreen: true,
  remove: function () { ... }
}
```

Compatibility practices:

- Keep `DATA_PATHS` backwards-compatible unless there is a strong reason to
  remove a fallback.
- Keep `STALE_HOURS` near the top for easy user tuning.
- Keep font and graphics-object fallbacks near the top.
- Avoid assuming a specific timezone on-device. Use `epoch` for cache age.
- Keep screen text short. The display is small, and firmware fonts vary.

## Editing the Companion

The companion intentionally uses the Python standard library for normal fetch
and sync workflows. Avoid adding runtime dependencies unless the feature cannot
be implemented reasonably without one.

When adding new JSON fields:

- Add them in `build_payload` or `fetch_location`.
- Update `sample/WEATHER.JSON`.
- Update [Data Format](DATA_FORMAT.md).
- Update the Pip-Boy app only after the sample payload reflects the new shape.
- Regenerate previews if the UI changes.

## Release Checklist

Before pushing a release-ready update:

- Run Python syntax checks.
- Validate `sample/WEATHER.JSON`.
- Regenerate preview PNGs when UI or sample data changes.
- Regenerate `WEATHER.IMG` if the icon generator changed.
- Test `pipboy_weather.py --fetch` with an SD path or local output.
- Open the GUI at least once if GUI code changed.
- Check documentation links from `README.md`.
- Copy files to the Pip-Boy or simulator and verify all three views load.
