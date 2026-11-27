# IceSpotter – winter sidewalk hazard map for Riga

**IceSpotter** finds icy, snowy and wet sidewalks in Riga from camera photos and shows them on a map, so winter maintenance crews know where to go first.

Built at **RobotHack 2026** (Riga, 24–28 November 2026) for the challenge *PCH4 "Spot Winter Sidewalk Hazards"* by Rīgas pašvaldība (Riga City Council).

## How it works
1. **Capture** – a camera on a city vehicle (bus, sidewalk tractor) takes photos with GPS and time.
2. **Classify** – a small neural network (YOLO11n-cls) labels the sidewalk: `clear`, `wet`, `snow`, `ice` or `not_visible`.
3. **Weather** – `weather.py` adds the hourly Open-Meteo forecast for that place to the network's class probabilities: black ice is often invisible on a photo, so freezing rain, refreezing of a wet surface, hoarfrost and snowfall in the next hours move probability towards ice or snow.
4. **Score** – the risk score adds bridges, stairs, bus stops and model confidence.
5. **Dispatch** – a map of Riga with a Top‑10 list of places to send crews first, a "treated" button for contractor control and a CSV report.

## Results (honest)
- 88 ± 3% (v5, 6 classes) accuracy on 582 hand-labelled Riga street photos (4-fold cross-validation); weakest class: wet (67%).
- 96% on ice images from the public Roads dataset.
- v6 (26.11): +100 phone photos (Rēzekne by day, Riga at night) and night-style copies of Riga photos. On new phone photos the model had not seen: 62% (v5: 28%). Ice on Roads test images: 94%.
- New class "blocked" (sidewalk physically blocked: dirt/snow pile, parked car, rubbish): 81% (22/27) - few examples so far.
- Few real Riga ice photos yet – that is the next step for a pilot.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py                         # dispatcher map
python predict.py photo.jpg --lat 56.95 --lon 24.11   # one photo: network + weather
```

## Data and licences
- Street images: [Mapillary](https://www.mapillary.com), CC BY-SA 4.0
- Training data: Roads dataset (Jeswin Wilson, Roboflow Universe), CC BY 4.0
- Weather: Open-Meteo

**Live site:** https://icespotter.github.io

Team IceSpotter · RTU, Riga, Latvia
