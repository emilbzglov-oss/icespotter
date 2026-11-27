import argparse
from PIL import Image, ImageOps
from ultralytics import YOLO
import weather

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("--lat", type=float, default=56.9496)
ap.add_argument("--lon", type=float, default=24.1052); ap.add_argument("--roi", action="store_true")
ap.add_argument("--temp", type=float, default=None, help="override air temperature, °C (what-if)")
a = ap.parse_args()

img = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")
if a.roi:
    w, h = img.size
    img = img.crop((int(w * .25), int(h * .65), int(w * .75), int(h * .98)))
img.thumbnail((320, 320))
r = YOLO("models/icespotter_v8.pt").predict(img, imgsz=224, verbose=False)[0]
probs = {r.names[i]: float(p) for i, p in enumerate(r.probs.data.tolist())}
wr = weather.risks(weather.fetch(a.lat, a.lon), a.temp)
fused, info = weather.fuse(probs, wr) if max(probs, key=probs.get) not in ("not_visible", "blocked") else (probs, {})

print("photo only :", {k: f"{v:.0%}" for k, v in sorted(probs.items(), key=lambda x: -x[1])})
print(f"weather    : t={wr['t']} °C, next 6 h -> ice {wr['ice_now']:.0%}, snow/slush {wr['snow_now']:.0%}")
print("photo+wx   :", {k: f"{v:.0%}" for k, v in sorted(fused.items(), key=lambda x: -x[1])})
print("result     :", *weather.top(fused))
