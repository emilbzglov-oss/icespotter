import base64
import csv
import io
from datetime import datetime
from pathlib import Path

import folium
import requests
import streamlit as st
from PIL import Image, ImageOps
from PIL.ExifTags import GPSTAGS

import importlib
import risk as _risk
importlib.reload(_risk)
from risk import near_bridge, risk_score, top_n
import weather as _wx
importlib.reload(_wx)

BASE = Path(__file__).parent
RIGA = (56.9496, 24.1052)
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}

st.set_page_config(page_title="IceSpotter – winter sidewalk hazard map of Riga", page_icon="🧊", layout="wide")

T = {
    "en": {
        "title": "🧊 IceSpotter — hazardous sidewalks of Riga",
        "subtitle": "Cameras on city vehicles → neural network → map and a list of where to send crews first",
        "settings": "⚙️ Settings", "model": "Model", "photos": "Photo folder",
        "info": "Mapillary coordinates (info.csv)", "roi_folder": "ROI for folder photos",
        "roi_help": "Turn on for wide frames from vehicles. mapillary_roi crops are already cropped.",
        "temp": "🌡️ Temperature", "manual": "Set manually (demo)", "air": "Air, °C",
        "now": "Riga now: {t:+.1f}°C (Open-Meteo)", "no_weather": "Weather unavailable",
        "ir": "Surface IR sensor", "surface": "Surface, °C",
        "show": "Show on map", "no_model": "Model not found: {p}\n\nDownload `IceSpotter/models/best.pt` from Google Drive into `models`.",
        "check": "📷 Check a new photo", "upload": "Sidewalk photo", "roi_up": "ROI (frame from a vehicle)",
        "cls": "Class", "lat": "Latitude", "lon": "Longitude",
        "no_gps": "No GPS in the photo — set coordinates manually (default: Ķīpsala)",
        "add": "➕ Add to map", "empty": "No points yet. Put photos into `data/photos` or upload one above.",
        "top": "🚨 Top 10 — send crews here first", "none": "No hazards right now 🎉",
        "risk": "risk", "treated_btn": "✅ Treated", "factors": "Place factors",
        "stairs_l": "Stairs", "bus_l": "Bus stop", "shade_l": "Shade",
        "reset": "↩️ Reset “treated” (demo)", "report": "📄 Report for contractor control",
        "download": "⬇️ Download report (CSV)",
        "sources": "Street images: Mapillary, CC BY-SA 4.0 · Training data: Roads dataset (Jeswin Wilson, Roboflow Universe), CC BY 4.0",
        "loading": "Classifying photos from data/photos…",
        "levels": {"ice": "🔴 ice", "slush": "🟠 wet snow", "snow": "🔵 snow",
                   "treated": "✅ treated", "none": "no action needed"},
        "off_map": "Not a cleaning job – saved in the system, not shown on the crews' map.",
        "edge": "Snow/ice only at the edge – the walking line is clear, not shown on the map.",
        "classes": {"ice": "ice", "snow": "snow", "wet": "wet", "clear": "dry",
                    "not_visible": "not visible", "blocked": "blocked"},
        "reasons": {
            "treated": "✅ treated by crew",
            "not_visible": "sidewalk not visible — need another frame",
            "camera": "camera: {cls} ({conf:.0%})",
            "black_ice": "wet at {t:+.1f}°C ({src}) → likely ice",
            "bridge": "bridge {name} — freezes first",
            "stairs": "stairs — dangerous if someone falls",
            "bus_stop": "bus stop — many pedestrians",
            "shade": "shade — ice stays longer",
            "stale": "not checked for a long time",
            "low_conf": "⚠️ needs human check",
            "weather_ice": "weather: icing likely ({v:.0%}) → ice risk raised",
            "weather_snow": "weather: fresh snow expected ({v:.0%})",
            "air": "air", "surface": "surface",
        },
        "cols": ["id", "place", "lat", "lon", "photo date", "class", "confidence", "risk",
                 "level", "reasons", "treated at"],
    },
    "lv": {
        "title": "🧊 IceSpotter — bīstamās Rīgas ietves",
        "subtitle": "Kameras uz pilsētas transporta → neironu tīkls → karte un saraksts, kur sūtīt brigādes vispirms",
        "settings": "⚙️ Iestatījumi", "model": "Modelis", "photos": "Foto mape",
        "info": "Mapillary koordinātas (info.csv)", "roi_folder": "ROI mapes fotogrāfijām",
        "roi_help": "Ieslēdz platiem kadriem no transporta. mapillary_roi attēli jau ir apgriezti.",
        "temp": "🌡️ Temperatūra", "manual": "Iestatīt manuāli (demo)", "air": "Gaiss, °C",
        "now": "Rīgā tagad: {t:+.1f}°C (Open-Meteo)", "no_weather": "Laikapstākļi nav pieejami",
        "ir": "Virsmas IR sensors", "surface": "Virsma, °C",
        "show": "Rādīt kartē", "no_model": "Modelis nav atrasts: {p}\n\nLejupielādē `IceSpotter/models/best.pt` no Google Drive mapē `models`.",
        "check": "📷 Pārbaudīt jaunu foto", "upload": "Ietves foto", "roi_up": "ROI (kadrs no transporta)",
        "cls": "Klase", "lat": "Platums", "lon": "Garums",
        "no_gps": "Fotogrāfijā nav GPS — iestati koordinātas manuāli (pēc noklusējuma Ķīpsala)",
        "add": "➕ Pievienot kartei", "empty": "Punktu vēl nav. Ieliec fotogrāfijas mapē `data/photos` vai augšupielādē foto augstāk.",
        "top": "🚨 Top 10 — kur sūtīt brigādes vispirms", "none": "Bīstamu vietu nav 🎉",
        "risk": "risks", "treated_btn": "✅ Apstrādāts", "factors": "Vietas faktori",
        "stairs_l": "Kāpnes", "bus_l": "Pietura", "shade_l": "Ēna",
        "reset": "↩️ Atiestatīt “apstrādāts” (demo)", "report": "📄 Atskaite darbuzņēmēja kontrolei",
        "download": "⬇️ Lejupielādēt atskaiti (CSV)",
        "sources": "Ielu attēli: Mapillary, CC BY-SA 4.0 · Apmācības dati: Roads dataset (Jeswin Wilson, Roboflow Universe), CC BY 4.0",
        "loading": "Klasificēju fotogrāfijas no data/photos…",
        "levels": {"ice": "🔴 ledus", "slush": "🟠 slapjš sniegs", "snow": "🔵 sniegs",
                   "treated": "✅ apstrādāts", "none": "nav jārīkojas"},
        "off_map": "Nav tīrīšanas darbs – saglabāts sistēmā, brigāžu kartē netiek rādīts.",
        "edge": "Sniegs/ledus tikai malā – gājēju josla tīra, kartē netiek rādīts.",
        "classes": {"ice": "ledus", "snow": "sniegs", "wet": "slapjš", "clear": "sauss",
                    "not_visible": "nav redzams", "blocked": "bloķēts"},
        "reasons": {
            "treated": "✅ brigāde apstrādājusi",
            "not_visible": "ietve nav redzama — vajag citu kadru",
            "camera": "kamera: {cls} ({conf:.0%})",
            "black_ice": "slapjš pie {t:+.1f}°C ({src}) → iespējams ledus",
            "bridge": "tilts {name} — sasalst pirmais",
            "stairs": "kāpnes — bīstami kritiena gadījumā",
            "bus_stop": "pietura — daudz gājēju",
            "shade": "ēna — ledus saglabājas ilgāk",
            "stale": "ilgi nav pārbaudīts",
            "low_conf": "⚠️ vajag cilvēka pārbaudi",
            "weather_ice": "laikapstākļi: iespējams apledojums ({v:.0%}) → ledus risks paaugstināts",
            "weather_snow": "laikapstākļi: gaidāms svaigs sniegs ({v:.0%})",
            "air": "gaiss", "surface": "virsma",
        },
        "cols": ["id", "vieta", "lat", "lon", "foto datums", "klase", "ticamība", "risks",
                 "līmenis", "iemesli", "apstrādāts"],
    },
}


def reason_text(L, code, params):
    tpl = L["reasons"][code]
    p = dict(params)
    if "cls" in p:
        p["cls"] = L["classes"].get(p["cls"], p["cls"])
    if "src" in p:
        p["src"] = L["reasons"][p["src"]]
    return tpl.format(**p).replace("  ", " ")


@st.cache_resource
def load_model(path):
    from ultralytics import YOLO
    return YOLO(path)


def mid_crop(img):
    w, h = img.size
    return img.crop((w // 3, 0, 2 * w // 3, h))


def roi_crop(img):
    w, h = img.size
    return img.crop((int(w * 0.25), int(h * 0.65), int(w * 0.75), int(h * 0.98)))


def _predict(model, images, chunk=16):
    out = []
    for i in range(0, len(images), chunk):
        for r in model.predict(images[i:i + chunk], imgsz=224, verbose=False, batch=chunk):
            pr = r.probs.data.tolist()
            out.append((r.names[r.probs.top1], float(r.probs.top1conf),
                        {r.names[j]: float(pr[j]) for j in range(len(pr))}))
    return out


ICE_CONF = 0.70


def classify(model, images):
    v8_path = BASE / "models" / "icespotter_v8.pt"
    if v8_path.exists():
        return _predict(load_model(str(v8_path)), images)
    v7_path = BASE / "models" / "icespotter_v7.pt"
    if v7_path.exists():
        return _predict(load_model(str(v7_path)), images)
    v6_path = BASE / "models" / "icespotter_v6.pt"
    if v6_path.exists():
        return _predict(load_model(str(v6_path)), images)
    v5_path = BASE / "models" / "icespotter_v5.pt"
    if v5_path.exists():
        return _predict(load_model(str(v5_path)), images)
    v4_path = BASE / "models" / "icespotter_v4.pt"
    if v4_path.exists():
        return _predict(load_model(str(v4_path)), images)
    riga_path = BASE / "models" / "riga.pt"
    if not riga_path.exists():
        return _predict(model, images)
    main = _predict(load_model(str(riga_path)), images)
    base = _predict(model, images)
    out = []
    for (c, p, pp), (bc, bp, _) in zip(main, base):
        if bc == "ice" and bp >= ICE_CONF and c != "not_visible":
            out.append(("ice", bp, {"ice": bp}))
        else:
            out.append((c, p, pp))
    return out


def exif_gps(img):
    try:
        gps = img.getexif().get_ifd(34853)
        if not gps:
            return None
        g = {GPSTAGS.get(k, k): v for k, v in gps.items()}
        deg = lambda d: float(d[0]) + float(d[1]) / 60 + float(d[2]) / 3600
        lat = deg(g["GPSLatitude"]) * (-1 if g.get("GPSLatitudeRef") == "S" else 1)
        lon = deg(g["GPSLongitude"]) * (-1 if g.get("GPSLongitudeRef") == "W" else 1)
        return lat, lon
    except Exception:
        return None


def read_info(path):
    info = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                info[row["id"]] = (float(row["lat"]), float(row["lon"]), row.get("date", ""))
    return info


def thumb_b64(img, size=220):
    im = img.copy()
    im.thumbnail((size, size))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode()


@st.cache_data(ttl=600)
def riga_weather():
    return _wx.fetch(*RIGA)


@st.cache_data(ttl=600)
def riga_temperature():
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": RIGA[0], "longitude": RIGA[1], "current": "temperature_2m"},
                         timeout=8)
        return float(r.json()["current"]["temperature_2m"])
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_folder_points(model_path, model_mtime, riga_mtime, photos_dir, info_path, use_roi):
    model = load_model(model_path)
    info = read_info(Path(info_path))
    files = sorted(p for p in Path(photos_dir).rglob("*") if p.suffix.lower() in IMG_EXT)
    points, imgs = [], []
    for f in files:
        raw = Image.open(f)
        img = ImageOps.exif_transpose(raw).convert("RGB")
        key = f.stem.removeprefix("mly_")
        if key in info:
            lat, lon, date = info[key]
        else:
            gps = exif_gps(raw)
            if not gps:
                continue
            (lat, lon), date = gps, ""
        crop = roi_crop(img) if use_roi else img
        crop.thumbnail((320, 320))
        imgs.append(crop)
        points.append({"id": f.stem, "lat": lat, "lon": lon, "date": date, "thumb": thumb_b64(crop)})
    full = classify(model, imgs) if imgs else []
    mid = classify(model, [mid_crop(i) for i in imgs]) if imgs else []
    for p, (cls, conf, probs), (_, _, probs_mid) in zip(points, full, mid):
        p["cls"], p["conf"], p["probs"], p["probs_mid"] = cls, conf, probs, probs_mid
    return points


for k, v in {"treated": {}, "flags": {}, "uploaded": []}.items():
    st.session_state.setdefault(k, v)

with st.sidebar:
    lang = st.radio("Language / Valoda", ["en", "lv"], horizontal=True,
                    format_func=lambda x: {"en": "🇬🇧 English", "lv": "🇱🇻 Latviešu"}[x])
    L = T[lang]
    st.header(L["settings"])
    model_path = st.text_input(L["model"], str(BASE / "models" / "best.pt"))
    photos_dir = st.text_input(L["photos"], str(BASE / "data" / "photos"))
    info_path = st.text_input(L["info"], str(BASE / "data" / "info.csv"))
    folder_roi = st.checkbox(L["roi_folder"], value=False, help=L["roi_help"])

    st.divider()
    st.subheader(L["temp"])
    api_temp = riga_temperature()
    use_manual = st.checkbox(L["manual"], value=api_temp is None)
    air_temp = st.slider(L["air"], -15.0, 10.0, api_temp if api_temp is not None else 0.0, 0.5) \
        if use_manual else api_temp
    st.caption(L["now"].format(t=api_temp) if api_temp is not None else L["no_weather"])
    wx_risk = _wx.risks(riga_weather(), air_temp if use_manual else None)
    use_ir = st.checkbox(L["ir"])
    surface_temp = st.number_input(L["surface"], -20.0, 20.0, 0.0, 0.5) if use_ir else None

    st.divider()
    all_levels = ["ice", "slush", "snow", "treated"]
    show_levels = st.multiselect(L["show"], all_levels, default=all_levels,
                                 format_func=lambda x: L["levels"][x])

HAZARD = ("ice", "snow")
LEVEL_COLOR = {"ice": "red", "slush": "orange", "snow": "blue", "treated": "darkgreen", "none": "gray"}


def top_of(probs):
    t = max(probs, key=probs.get)
    if t in ("blocked", "not_visible"):
        return t
    q, _ = _wx.fuse(probs, wx_risk)
    return max(q, key=q.get)


def hazard_kind(p):
    if not p.get("probs"):
        return p["cls"] if p["cls"] in HAZARD else "none"
    probs = p["probs"]
    if max(probs, key=probs.get) in ("blocked", "not_visible"):
        return "none"
    q, _ = _wx.fuse(probs, wx_risk)
    if q.get("ice", 0) + q.get("snow", 0) < 0.5:
        return "none"
    if p.get("probs_mid"):
        m, _ = _wx.fuse(p["probs_mid"], wx_risk)
        if m.get("ice", 0) + m.get("snow", 0) < 0.3:
            return "none"
    if q.get("ice", 0) >= q.get("snow", 0):
        return "ice"
    return "slush" if air_temp is not None and -1 < air_temp < 2 else "snow"


if not Path(model_path).exists():
    st.error(L["no_model"].format(p=model_path))
    st.stop()
model = load_model(model_path)

st.title(L["title"])
st.caption(L["subtitle"])

with st.expander(L["check"], expanded=False):
    c1, c2 = st.columns([2, 1])
    up = c1.file_uploader(L["upload"], type=["jpg", "jpeg", "png", "webp"])
    up_roi = c2.checkbox(L["roi_up"], value=False)
    if up is not None:
        raw = Image.open(up)
        img = ImageOps.exif_transpose(raw).convert("RGB")
        crop = roi_crop(img) if up_roi else img
        (cls, conf, probs), = classify(model, [crop])
        if cls not in ("not_visible", "blocked"):
            fused, _ = _wx.fuse(probs, wx_risk)
            cls, conf = _wx.top({k: v for k, v in fused.items() if k != "not_visible"})
        gps = exif_gps(raw)
        c1.image(crop, width=320)
        c2.metric(L["cls"], L["classes"].get(cls, cls), f"{conf:.0%}")
        (_, _, probs_mid), = classify(model, [mid_crop(crop)])
        on_map = hazard_kind({"cls": cls, "probs": probs, "probs_mid": probs_mid}) != "none"
        if not on_map:
            c2.info(L["edge"] if cls in HAZARD else L["off_map"])
        lat = c2.number_input(L["lat"], value=gps[0] if gps else 56.9531, format="%.6f")
        lon = c2.number_input(L["lon"], value=gps[1] if gps else 24.0797, format="%.6f")
        if not gps:
            c2.caption(L["no_gps"])
        if c2.button(L["add"]):
            st.session_state.uploaded.append({
                "id": f"upload_{len(st.session_state.uploaded)}_{up.name}", "lat": lat, "lon": lon,
                "date": datetime.now().strftime("%Y-%m-%d"), "thumb": thumb_b64(crop), "cls": cls, "conf": conf, "probs": probs,
                "probs_mid": probs_mid})
            st.rerun()

_zip = Path(photos_dir).parent / "photos.zip"
if _zip.exists() and not any(Path(photos_dir).rglob("*.jpg")):
    import zipfile
    with zipfile.ZipFile(_zip) as z:
        z.extractall(Path(photos_dir))

if Path(photos_dir).exists():
    with st.spinner(L["loading"]):
        _riga = BASE / "models" / "icespotter_v8.pt"
        if not _riga.exists():
            _riga = BASE / "models" / "icespotter_v7.pt"
        if not _riga.exists():
            _riga = BASE / "models" / "icespotter_v6.pt"
        if not _riga.exists():
            _riga = BASE / "models" / "icespotter_v5.pt"
        if not _riga.exists():
            _riga = BASE / "models" / "icespotter_v4.pt"
        if not _riga.exists():
            _riga = BASE / "models" / "riga.pt"
        folder_points = load_folder_points(model_path, Path(model_path).stat().st_mtime,
                                           _riga.stat().st_mtime if _riga.exists() else 0,
                                           photos_dir, info_path, folder_roi)
else:
    folder_points = []

points = []
for p in folder_points + st.session_state.uploaded:
    flags = st.session_state.flags.get(p["id"], {})
    bridge = near_bridge(p["lat"], p["lon"])
    q = {**p, "air_temp": air_temp, "surface_temp": surface_temp,
         "bridge": bridge, "stairs": flags.get("stairs", False),
         "bus_stop": flags.get("bus_stop", False), "shade": flags.get("shade", False),
         "hours_since_check": 0, "treated": p["id"] in st.session_state.treated}
    q["name"] = bridge or f"{p['lat']:.4f}, {p['lon']:.4f}"
    wx_reasons = []
    if p.get("probs") and p["cls"] not in ("not_visible", "blocked"):
        fused, info = _wx.fuse(p["probs"], wx_risk)
        q["cls"], q["conf"] = _wx.top({k: v for k, v in fused.items() if k != "not_visible"})
        if info["ice_added"] > 0.05:
            wx_reasons.append(("weather_ice", {"v": wx_risk["ice_now"]}))
        if info["snow_added"] > 0.05:
            wx_reasons.append(("weather_snow", {"v": wx_risk["snow_now"]}))
    q["score"], q["reasons"] = risk_score(q)
    if wx_reasons and q["score"] is not None and not q["treated"]:
        q["score"] = max(q["score"], round(100 * fused["ice"] + 60 * fused["snow"] + 30 * fused["wet"]))
    q["reasons"] = q["reasons"] + wx_reasons
    kind = hazard_kind(p)
    q["level"] = "none" if kind == "none" else ("treated" if q["treated"] else kind)
    q["why"] = [reason_text(L, c, prm) for c, prm in q["reasons"]]
    points.append(q)

if not points:
    st.info(L["empty"])

counts = {lv: sum(p["level"] == lv for p in points) for lv in all_levels}
for col, lv in zip(st.columns(len(all_levels)), all_levels):
    col.metric(L["levels"][lv], counts[lv])

left, right = st.columns([3, 2])

with left:
    shown = [p for p in points if p["level"] in show_levels]
    base = shown or points
    center = (sum(p["lat"] for p in base) / len(base), sum(p["lon"] for p in base) / len(base)) if base else RIGA
    m = folium.Map(location=center, zoom_start=14, tiles="OpenStreetMap")
    for p in shown:
        popup = (f"<b>{L['levels'][p['level']]}</b> · {L['risk']} {p['score'] if p['score'] is not None else '–'}<br>"
                 f"{'<br>'.join(p['why'])}<br>"
                 f"<img src='data:image/jpeg;base64,{p['thumb']}' width='200'>")
        folium.CircleMarker([p["lat"], p["lon"]], radius=8 if p["level"] == "ice" else 6,
                            color=LEVEL_COLOR[p["level"]], fill=True, fill_opacity=0.85,
                            popup=folium.Popup(popup, max_width=240)).add_to(m)
    html = m.get_root().render()
    if hasattr(st, "iframe"):
        st.iframe(html, height=600)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=600)

with right:
    st.subheader(L["top"])
    top = top_n([p for p in points if p["level"] in ("ice", "slush", "snow")], 10)
    if not top:
        st.success(L["none"])
    for i, p in enumerate(top, 1):
        with st.container(border=True):
            a, b = st.columns([1, 3])
            a.image(base64.b64decode(p["thumb"]), width=110)
            b.markdown(f"**{i}. {p['name']}** — {L['risk']} **{p['score']}**")
            b.caption(" · ".join(p["why"]))
            c1, c2 = b.columns(2)
            if c1.button(L["treated_btn"], key=f"done_{p['id']}"):
                st.session_state.treated[p["id"]] = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.rerun()
            with c2.popover(L["factors"]):
                f = st.session_state.flags.setdefault(p["id"], {})
                for key, lab in [("stairs", L["stairs_l"]), ("bus_stop", L["bus_l"]), ("shade", L["shade_l"])]:
                    f[key] = st.checkbox(lab, value=f.get(key, False), key=f"{key}_{p['id']}")
    if st.session_state.treated and st.button(L["reset"]):
        st.session_state.treated = {}
        st.rerun()

st.subheader(L["report"])
cols = L["cols"]
rows = [dict(zip(cols, [
    p["id"], p["name"], round(p["lat"], 6), round(p["lon"], 6), p["date"],
    L["classes"].get(p["cls"], p["cls"]), round(p["conf"], 2), p["score"], L["levels"][p["level"]],
    "; ".join(p["why"]), st.session_state.treated.get(p["id"], ""),
])) for p in sorted(points, key=lambda x: -(x["score"] or 0))]
st.dataframe(rows, height=260)
buf = io.StringIO()
if rows:
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
st.download_button(L["download"], buf.getvalue().encode("utf-8-sig"),
                   file_name=f"icespotter_report_{datetime.now():%Y%m%d_%H%M}.csv", mime="text/csv")
st.caption(L["sources"])
