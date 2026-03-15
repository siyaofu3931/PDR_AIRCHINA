# Step detection: benchmark vs PDR_AIRCHINA backend

Comparison of the algorithm in **pedestrian_dead_reckoning** (frontend, working) and **PDR_AIRCHINA** backend (step count freezes/resets on deploy).

## 1. Signal source

| Aspect | pedestrian_dead_reckoning (benchmark) | PDR_AIRCHINA backend |
|--------|--------------------------------------|------------------------|
| Input | **Linear acceleration** (`e.acceleration` – gravity already removed by device) | **Raw acceleration** (`acc_including_g`), then gravity removed with low-pass α=0.92 |
| Step signal | **Magnitude** `√(ax²+ay²+az²)` – orientation-invariant (pocket, hand, tilt) | **Vertical component** of linear accel – depends on phone orientation |
| Effect | Same step signal regardless of how the phone is held | Tilt changes the vertical component → weaker/noisier signal, more missed or false steps |

**Conclusion:** Backend should use **magnitude of linear acceleration** (after gravity removal) to match the benchmark and be orientation-invariant.

---

## 2. Filtering

| Aspect | Benchmark | PDR_AIRCHINA backend |
|--------|-----------|------------------------|
| Type | **Band-pass** 0.5–3 Hz (walking band) | **Single low-pass** smoothing (α=0.84) on \|vertical\| |
| Purpose | Removes DC/drift and high-frequency noise | Only smooths the signal |
| dt | Uses actual time between samples, **capped at 0.1 s** to avoid big gaps | No explicit dt in step signal; heading uses dt and **skips if dt > 0.2 s** |

**Conclusion:** Backend should add a **band-pass** (e.g. 0.5–3 Hz) and use **capped dt** between frames so that network jitter doesn’t break the filter.

---

## 3. Adaptive threshold

| Aspect | Benchmark | PDR_AIRCHINA backend |
|--------|-----------|------------------------|
| Window | **Time-based**: last **2 s** of samples | **Sample-based**: last **30** samples |
| Baseline | **Mean** μ of values in window | **Median** of values in window |
| Threshold | T = **μ + k·σ** (k=0.5), floor 0.15 | T = **baseline + k·σ** (k=1.6), min 0.10 |
| Problem when deployed | N/A (continuous stream, 2 s is fixed in time) | On variable frame rate, 30 samples can span 0.3 s or 6 s → threshold can drift; median can sit high after a few steps → **step count freezes** |

**Conclusion:** Backend should use a **time-based window** (e.g. 2 s) and **mean + k·σ** (with floor) like the benchmark, so threshold adapts correctly under bursty or slow frames.

---

## 4. Peak detection & guards

| Aspect | Benchmark | PDR_AIRCHINA backend |
|--------|-----------|------------------------|
| Peak | **Local maximum**: v[i-2] < v[i-1] > v[i] | **Rising then falling**: `rising && (last_sig > step_sig) && (last_sig > threshold)` |
| Prominence | **Yes**: (peak − valley) ≥ 0.35 m/s²; valley = min since last step | **No** |
| Valley between steps | **Yes**: require signal to go **below mean** before next step (anti-shake) | **No** |
| Min period | **350 ms** between steps | **250 ms** (180 ms in warmup) |
| Max interval | No explicit max | **2000 ms** (5000 ms in code); steps outside window rejected |

**Conclusion:** Backend should add **prominence** and **valley-below-mean** checks and use **min period 350 ms** to match the benchmark and reduce false/missed steps when frames are bursty.

---

## 5. Why step count can “reset to 0” (deploy)

- **Session state is in-memory.** On Render (or any restart), the `sessions` dict is cleared.
- On **reconnect**, the frontend reuses the **same** `pdrSessionId` and reconnects the WebSocket.
- Backend does: `if session_id not in sessions: sessions[session_id] = PdrEngine(); ... reset(...)`.
- So after a **process restart**, the reconnecting client gets a **new engine** with **step_count = 0**.
- **Heading** can keep “updating” because it’s recomputed from the last received orientation/gyro; the UI might show the last received heading until new frames arrive.

**Conclusion:** Resets are expected when the backend process restarts (e.g. Render spin-down). To avoid showing 0, the frontend could avoid overwriting step count when it decreases (unless user explicitly resets), or the backend could persist session state (e.g. Redis/DB) if needed.

---

## 6. Why step count “freezes” or “stops increasing”

1. **Bursty/late frames:** Frames arrive in bursts (e.g. 10 at once then 200 ms nothing). Backend runs step detection once per frame; with 30-sample window and median baseline, after a few steps the median can stay high and new peaks no longer exceed threshold.
2. **Orientation:** Vertical-component signal is weaker when the phone is tilted, so peaks may not cross threshold.
3. **No band-pass:** Low-frequency drift can shift the smoothed signal so that “valleys” and “peaks” are misidentified.
4. **No prominence/valley:** Shake or noise can be counted as steps when they shouldn’t be, or real steps can be missed when the threshold or baseline is off.

**Conclusion:** Aligning the backend with the benchmark (magnitude, band-pass, time-based threshold, prominence, valley) should make step count more stable and robust under deploy conditions.

---

## 7. Recommended backend changes (summary)

1. **Step signal:** Use **magnitude** of linear acceleration after gravity removal (not vertical component). ✅
2. **Filter:** Add **band-pass 0.5–3 Hz** and use **capped dt** (e.g. max 0.1 s) between consecutive frames. ✅
3. **Threshold:** Use **time-based** window (e.g. 2 s), **mean + k·σ**, with a floor (e.g. 0.15). ✅
4. **Peak:** Use **local maximum** check, **min prominence** (e.g. 0.35), and **valley below mean** before next step. ✅
5. **Timing:** Use **min period 350 ms** between steps; consider skipping or capping **dt** for filter when dt > 0.2 s (e.g. cap to 0.1 s for band-pass only, still process the frame once). ✅
6. **Optional:** Send **linear acceleration** from the client when available (`e.acceleration`), and use it for step detection so the backend doesn’t rely only on its own gravity removal. ✅

**Implementation status:** All items (1)–(6) are implemented. Backend: `backend/engine.py` (magnitude, band-pass, time-based threshold, prominence, valley, optional `acc_linear`). Frontend: sends `acc_linear` when available and guards against step-count reset on backend restart in `applyBackendPose`.
