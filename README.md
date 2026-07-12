# RobCo Weather MkV

RobCo Weather MkV is a cached weather and space-weather terminal for the
Bethesda x The Wand Company Pip-Boy 3000 Mk V. It pairs a Python companion app
with an on-device Espruino app so the Pip-Boy can show useful weather data
without needing live network access.

The companion runs on a computer or phone, fetches data from Open-Meteo and
NOAA SWPC, writes `WEATHER.JSON` to the Pip-Boy SD card, and the Pip-Boy app
renders the cached data in a Fallout 3 / New Vegas style interface.

## What It Includes

- Current conditions for any saved location.
- 5-day forecast with high, low, condition, and precipitation chance.
- Space-weather view with solar flare class, R/S/G scales, current Kp, and a
  3-day Kp forecast graph.
- Per-location aurora estimate based on latitude and forecast Kp.
- Stale-cache warning when the synced data is more than 12 hours old.
- Graphical companion app and interactive/scriptable CLI.
- Preview renderer for screenshots and a generator for the app's PNG icon.

## Quick Start

1. Run the companion GUI:

   ```bash
   python companion/pipboy_weather_gui.py
   ```

2. Add or reorder locations and choose `F` or `C`.

3. Press `INSTALL SD + DATA`, then select the SD card root. This copies:

   ```text
   pipboy/WEATHER.min.js           -> USER/WEATHER.js
   pipboy/APPINFO/weather.json     -> APPINFO/weather.json
   ```

   It also downloads Open-Meteo weather and NOAA SWPC space weather, then
   writes `USER/WEATHER.JSON`. If you prefer serial transfer, use
   `USB INSTALL + DATA` to send the app files and fresh cache over USB.

4. Reboot the Pip-Boy. The app appears in `INV > APPS` as `Weather`.

The companion writes the cache to `<SD>/USER/WEATHER.JSON`. If no SD path is
set, it writes `companion/WEATHER.JSON` so you can copy it manually.
The data-only sync actions scan for the Weather app first and offer to install
the latest app files when they are missing.

## Previews

The preview images are generated from `sample/WEATHER.JSON` by
`companion/render_preview.py`:

```bash
python companion/render_preview.py
```

| Current | Forecast | Current + Solar |
| --- | --- | --- |
| ![Current conditions](previews/01_current.png) | ![Forecast](previews/02_forecast.png) | ![Current conditions with solar activity](previews/04_current_solar.png) |

| Space Weather | Stale Cache |
| --- | --- |
| ![Space weather](previews/03_space_weather.png) | ![Stale warning](previews/05_stale_warning.png) |

Companion GUI with the relay control tab, app source controls, shared sync
action bar, and terminal log:

![Companion GUI](previews/06_companion_gui.png)

## Documentation

- [Installation](docs/INSTALLATION.md): SD card layout, first sync, updates,
  uninstalling, and verification.
- [Companion App](docs/COMPANION.md): GUI, CLI, scripted use, configuration,
  locations, and data sources.
- [Pip-Boy App](docs/PIPBOY_APP.md): controls, views, stale-data handling,
  firmware notes, and app metadata.
- [Data Format](docs/DATA_FORMAT.md): `WEATHER.JSON` schema and compatibility
  rules.
- [Development](docs/DEVELOPMENT.md): repository layout, validation commands,
  preview/icon generation, and release checklist.
- [Troubleshooting](docs/TROUBLESHOOTING.md): common install, sync, display,
  and data problems.

## Repository Layout

```text
.
|-- companion/
|   |-- pipboy_weather_gui.py    # Tkinter companion UI
|   |-- pipboy_weather.py        # fetch/write engine and CLI
|   |-- pipboy_serial.py         # USB serial file transfer helper
|   |-- make_icon.py             # regenerates pipboy/assets/icon.png
|   `-- render_preview.py        # renders preview PNGs, requires Pillow
|-- docs/                        # detailed documentation
|-- pipboy/
|   |-- WEATHER.js               # on-device Espruino app (source)
|   |-- WEATHER.min.js           # minified build -> USER/WEATHER.js on card
|   |-- package.json             # app registry metadata
|   |-- ChangeLog                # app version history
|   |-- APPINFO/weather.json     # optional on-card friendly name
|   `-- assets/icon.png          # PNG registry icon
|-- previews/                    # generated screenshots
|-- sample/WEATHER.JSON          # simulator and preview sample cache
`-- AGENTS.md                    # Mk V app conventions for automated tooling
```

## Requirements

- Pip-Boy 3000 Mk V SD card access through USB-C serial transfer or direct
  microSD access.
- Python 3 for the companion.
- Tkinter for the GUI. Most desktop Python installs include it.
- Internet access only on the companion device during sync.
- Optional: Pillow for `companion/render_preview.py`.

No API keys are required. Weather comes from
[Open-Meteo](https://open-meteo.com), and space weather comes from
[NOAA SWPC](https://www.swpc.noaa.gov).

## Safety Notes

Back up the Pip-Boy SD card before installing or replacing files. The project
only needs two app files plus `USER/WEATHER.JSON`, but a full backup makes it
easy to restore the original card state if firmware expectations differ.

The Pip-Boy app reads cached data only. Re-run the companion whenever you want
fresh weather.
