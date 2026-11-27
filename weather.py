from __future__ import annotations

import requests

API = "https://api.open-meteo.com/v1/forecast"
FREEZING = {56, 57, 66, 67}
SNOWCODES = {71, 73, 75, 77, 85, 86}
CLASSES = ("blocked", "clear", "ice", "not_visible", "snow", "wet")


def fetch(lat: float = 56.9496, lon: float = 24.1052, timeout: int = 10) -> dict | None:
    try:
        r = requests.get(API, params={
            "latitude": lat, "longitude": lon, "current": "temperature_2m",
            "hourly": "temperature_2m,dew_point_2m,precipitation,snowfall,precipitation_probability,weather_code",
            "past_days": 1, "forecast_days": 2, "timezone": "Europe/Riga"}, timeout=timeout)
        j = r.json()
        h, now = j["hourly"], j["current"]["time"][:13]
        idx = next((i for i, t in enumerate(h["time"]) if t[:13] == now), 0)
        return {"t_now": float(j["current"]["temperature_2m"]), "now_idx": idx,
                "time": h["time"], "t": h["temperature_2m"], "td": h["dew_point_2m"],
                "mm": h["precipitation"], "sn": h["snowfall"], "pp": h["precipitation_probability"],
                "code": h["weather_code"]}
    except Exception:
        return None


def _hour(w: dict, i: int, t_over: float | None) -> dict:
    T = t_over if t_over is not None else w["t"][i]
    Td, mm, sn, code = w["td"][i], w["mm"][i] or 0, w["sn"][i] or 0, w["code"][i]
    pp = (1.0 if mm > 0.1 else 0.0) if w["pp"][i] is None else w["pp"][i] / 100
    p_pre = max(pp, 0.9 if mm >= 0.2 else 0.0)
    snowy = sn > 0 or code in SNOWCODES
    snow = p_pre * (1.0 if T <= -1 else (0.5 if T < 1 and snowy else 0.0))
    slush = p_pre * ((1.0 if snowy else 0.6) if -1 < T < 2 else 0.0)
    past = sum((w["mm"][j] or 0) for j in range(max(0, i - 12), i))
    min_past = min([t_over if t_over is not None else w["t"][j] for j in range(max(0, i - 12), i)] or [99])
    ice = max(
        max(pp, 0.8) if code in FREEZING else 0.0,
        0.7 * p_pre if (T > 0 and min_past <= -2) else 0.0,
        min(0.9, 0.5 + past / 4) if (T <= 0 and past >= 0.3) else 0.0,
        0.35 if (T <= 0 and Td is not None and T - Td <= 1) else 0.0,
        0.6 * p_pre if (T <= 1 and mm > 0 and not snowy) else 0.0,
    )
    return {"ice": ice, "slush": slush, "snow": snow}


def risks(w: dict | None, t_override: float | None = None, hours: int = 24, now_hours: int = 6) -> dict:
    out = {"ice": 0.0, "slush": 0.0, "snow": 0.0, "ice_now": 0.0, "snow_now": 0.0, "t": None}
    if not w:
        return out
    out["t"] = t_override if t_override is not None else w["t_now"]
    i0 = w["now_idx"]
    for i in range(i0, min(i0 + hours, len(w["t"]))):
        r = _hour(w, i, t_override)
        for k in ("ice", "slush", "snow"):
            out[k] = max(out[k], r[k])
        if i < i0 + now_hours:
            out["ice_now"] = max(out["ice_now"], r["ice"])
            out["snow_now"] = max(out["snow_now"], r["snow"], r["slush"])
    return out


def fuse(probs: dict, wr: dict) -> tuple[dict, dict]:
    g = lambda k: float(probs.get(k, 0.0))
    T = wr.get("t")
    iw = 0.0
    ic = g("clear") * wr["ice_now"] * 0.25
    sn = wr["snow_now"] * 0.5
    sc, sw = (g("clear") - ic) * sn, (g("wet") - iw) * sn
    q = {"clear": g("clear") - ic - sc, "ice": g("ice") + iw + ic, "not_visible": g("not_visible"), "blocked": g("blocked"),
         "snow": g("snow") + sc + sw, "wet": g("wet") - iw - sw}
    return q, {"ice_added": iw + ic, "snow_added": sc + sw}


def top(q: dict) -> tuple[str, float]:
    c = max(q, key=q.get)
    return c, q[c]
