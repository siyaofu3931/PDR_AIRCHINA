# SFO Corridor Pipeline (OSM -> corridors.json)

This is a semi-automatic workflow for building `backend/data/corridors.json` for SFO.

## 1) Pick target floor and local origin

- Start with one floor only, usually `level=1`.
- Pick a local origin point (`origin_lat`, `origin_lon`) near your test start.
- In app tests, use the same map origin so backend XY and map XY are aligned.

## 2) Run extractor

From repo root:

```bash
python backend/tools/build_corridors_from_osm.py \
  --bbox 37.595,-122.405,37.635,-122.365 \
  --level 1 \
  --origin-lat 37.6164 \
  --origin-lon -122.3860 \
  --out backend/data/corridors.json \
  --raw-out backend/data/sfo_osm_raw.json
```

What this script does:
- Queries Overpass for indoor corridor candidates (`indoor=corridor`, `highway=footway|steps` with indoor tags).
- Keeps only ways that match `level`.
- Converts `lat/lon` to local `x/y` meters.
- Drops very short noisy edges and decimates dense points.

## 3) Validate quickly

- Start backend and app.
- Turn on indoor correction.
- If matcher says not ready, check `backend/data/corridors.json` exists and has `edges`.

## 4) Manual cleanup pass (recommended)

Because OSM indoor quality varies, do one manual pass:
- Remove wrong areas (service corridors, irrelevant branches).
- Merge/split edges around key turns.
- Keep main passenger corridors first.

## 5) Iterate with field logs

- Walk 2-3 reference routes.
- Compare raw vs matched trajectory.
- Tweak corridor file and matcher thresholds (`map_match_max_snap_m`, heading penalty, continuity penalty).

---

Notes:
- This is a bootstrap graph for v2.0-a.
- Later versions should add HMM/Viterbi transition scoring and anchor-based distance calibration.
