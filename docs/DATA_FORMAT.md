# Data Format

The companion writes a compact JSON payload to `WEATHER.JSON`. The Pip-Boy app
only reads this file; it never calls the network.

The current payload version is:

```json
{"v":1}
```

## Top-Level Object

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `v` | number | Yes | Data format version. Current value is `1`. |
| `generated` | string | Yes | Human-readable UTC sync time, `YYYY-MM-DD HH:MM`. |
| `epoch` | number | Yes | UTC epoch seconds used for stale-cache detection. |
| `units` | object | Yes | Temperature and wind units. |
| `locations` | array | Yes | One or more location objects. |
| `space` | object | No | Space-weather data shared by all locations. |

The app requires `locations` to exist and contain at least one item.

## Units

```json
"units": {
  "temp": "F",
  "wind": "mph"
}
```

| Field | Values | Description |
| --- | --- | --- |
| `temp` | `F`, `C` | Temperature unit. |
| `wind` | `mph`, `kmh` | Wind speed unit. |

## Location Object

```json
{
  "name": "GOODSPRINGS",
  "region": "MOJAVE WASTELAND",
  "lat": 35.8341,
  "lon": -115.4319,
  "current": {},
  "daily": [],
  "aurora": {}
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Display name shown in the app header. |
| `region` | string | No | Secondary label below the location name. |
| `lat` | number | Yes | Latitude, rounded by the companion. |
| `lon` | number | Yes | Longitude, rounded by the companion. |
| `current` | object | Yes | Current conditions. |
| `daily` | array | Yes | Daily forecast rows. |
| `aurora` | object | No | Per-location aurora estimate. |

## Current Conditions

```json
"current": {
  "temp": 102,
  "feels": 99,
  "code": 0,
  "desc": "Clear skies",
  "wind": 7,
  "dir": "SW",
  "humidity": 9,
  "uv": 10,
  "is_day": 1,
  "time": "2026-06-27 11:30"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `temp` | number | Current air temperature. |
| `feels` | number | Apparent temperature. |
| `code` | number | Open-Meteo WMO weather code. |
| `desc` | string | Companion-provided short text for the code. |
| `wind` | number | Wind speed in the selected wind unit. |
| `dir` | string | Compass direction such as `N`, `SW`, or `E`. |
| `humidity` | number | Relative humidity percentage. |
| `uv` | number | Daily UV index max for the current day. |
| `is_day` | number | `1` for day, `0` for night. |
| `time` | string | Observation time in local weather-station timezone. |

## Daily Forecast

Each `daily` entry represents one forecast day:

```json
{
  "d": "SAT",
  "date": "2026-06-27",
  "hi": 104,
  "lo": 78,
  "code": 0,
  "desc": "Clear skies",
  "pop": 0
}
```

| Field | Type | Description |
| --- | --- | --- |
| `d` | string | Short weekday label. |
| `date` | string | ISO date. |
| `hi` | number | Forecast high temperature. |
| `lo` | number | Forecast low temperature. |
| `code` | number | Open-Meteo WMO weather code. |
| `desc` | string | Companion-provided short text. |
| `pop` | number | Max precipitation probability percentage. |

The app displays up to five entries.

## Space Weather

`space` is shared by every location:

```json
"space": {
  "kp_now": 2.0,
  "kp_peak": 6.0,
  "r_scale": "R1",
  "r_text": "Minor radio blackout",
  "s_scale": "S0",
  "s_text": "none",
  "g_scale": "G2",
  "g_text": "Moderate storm",
  "flare": "M1.4",
  "flare_time": "2026-06-27 09:12",
  "kpf": [2, 2.3, 3],
  "kpf_ticks": [{"i": 2, "d": "SAT"}],
  "updated": "2026-06-27 11:30"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `kp_now` | number | Latest observed planetary Kp. |
| `kp_peak` | number | Peak predicted Kp in the forecast window. |
| `r_scale` | string | NOAA radio blackout scale, `R0` through `R5`. |
| `r_text` | string | NOAA R-scale description. |
| `s_scale` | string | NOAA radiation storm scale, `S0` through `S5`. |
| `s_text` | string | NOAA S-scale description. |
| `g_scale` | string | NOAA geomagnetic storm scale, `G0` through `G5`. |
| `g_text` | string | NOAA G-scale description. |
| `flare` | string | Latest flare class, such as `C3.2`, `M1.4`, or `X2.1`. |
| `flare_time` | string | Time associated with the latest flare class. |
| `kpf` | array | Predicted Kp values, usually 3-hour cadence for about 3 days. |
| `kpf_ticks` | array | Day-boundary labels for the graph. |
| `updated` | string | UTC time the space-weather block was built. |

If all space-weather fetches fail, the companion omits `space`. The app still
shows current conditions and forecast data.

## Aurora Estimate

Each location can include:

```json
"aurora": {
  "chance": "LIKELY",
  "needed": 1,
  "maxkp": 6.0
}
```

| Field | Values | Description |
| --- | --- | --- |
| `chance` | `LIKELY`, `POSSIBLE`, `UNLIKELY` | Display verdict. |
| `needed` | `0` through `9` | Estimated Kp needed at the location latitude. |
| `maxkp` | number | Forecast Kp peak used for the verdict. |

The estimate uses geographic latitude and a simple Kp threshold table. It is
not a replacement for a geomagnetic forecast.

## Compatibility Rules

When changing the format:

- Keep existing fields when possible.
- Add optional fields instead of renaming required fields.
- Increment `v` for breaking changes.
- Update `sample/WEATHER.JSON`.
- Regenerate previews if screen output changes.
- Keep `epoch` as UTC seconds so stale detection remains timezone-safe.

## Minimal Valid Payload

This is enough for the app to load, though most fields will display as blanks
or fallback values:

```json
{
  "v": 1,
  "generated": "2026-06-27 12:00",
  "epoch": 1782561600,
  "units": {"temp": "F", "wind": "mph"},
  "locations": [
    {
      "name": "TEST",
      "region": "SIMULATOR",
      "lat": 0,
      "lon": 0,
      "current": {"temp": 70, "code": 0, "desc": "Clear skies", "is_day": 1},
      "daily": []
    }
  ]
}
```
