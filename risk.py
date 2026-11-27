import math

CLASS_RISK = {"ice": 100, "blocked": 80, "snow": 60, "wet": 30, "clear": 0, "not_visible": None}

RIGA_BRIDGES = {
    "Akmens tilts": (56.9466, 24.0975),
    "Vanšu tilts": (56.9565, 24.0905),
    "Salu tilts": (56.9395, 24.1295),
    "Dzelzceļa tilts": (56.9420, 24.1080),
}

ICE_TEMP = 2.0
LOW_CONF = 0.60


def distance_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def near_bridge(lat, lon, radius=150):
    for name, (blat, blon) in RIGA_BRIDGES.items():
        if distance_m(lat, lon, blat, blon) <= radius:
            return name
    return None


def risk_score(point):
    if point.get("treated"):
        return 0, [("treated", {})]

    base = CLASS_RISK.get(point["cls"])
    if base is None:
        return None, [("not_visible", {})]

    reasons = [("camera", {"cls": point["cls"], "conf": point["conf"]})]
    score = base * point["conf"]

    temp, src = point.get("surface_temp"), "surface"
    if temp is None:
        temp, src = point.get("air_temp"), "air"
    if point["cls"] == "wet" and temp is not None and temp <= ICE_TEMP:
        score = max(score, 90)
        reasons.append(("black_ice", {"t": temp, "src": src}))

    for key, bonus in [("bridge", 15), ("stairs", 15), ("bus_stop", 10), ("shade", 10)]:
        value = point.get(key)
        if value:
            score += bonus
            reasons.append((key, {"name": value if isinstance(value, str) else ""}))

    if point.get("hours_since_check", 0) > 6:
        score += 5
        reasons.append(("stale", {}))

    if point["conf"] < LOW_CONF:
        reasons.append(("low_conf", {}))

    return round(score), reasons


def level(point, score):
    if point.get("treated"):
        return "treated"
    if score is None:
        return "hidden"
    if score >= 80:
        return "high"
    if score >= 40:
        return "medium"
    if score > 0:
        return "low"
    return "clear"


LEVEL_COLOR = {"high": "red", "medium": "orange", "low": "beige", "clear": "green",
               "treated": "darkgreen", "hidden": "gray"}


def top_n(points, n=10):
    scored = [p for p in points if p.get("score") and p["score"] > 0]
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:n]
