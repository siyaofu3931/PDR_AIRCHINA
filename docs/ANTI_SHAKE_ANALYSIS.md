# Anti-shake step detection (data-driven)

## Analysis of shaking log (`pdr-sensor-log-2026-03-02T02-41-08.json`)

- **Duration**: ~20 s of shaking → **21 steps** counted (should be 0).
- **stepHistory** during shaking:
  - `a_max`: 10.3–19.4 m/s² (often 17–19)
  - `a_min`: 0.75–11.0 m/s² (often 9–10)
  - `(a_max - a_min)`: **~7–10 m/s²**
  - `periodMs`: 500–2884 ms (many at 533–567 ms)

## Normal walking (typical ranges)

- Magnitude at rest ~9.8 m/s²; step “bump” adds ~0.5–2 m/s².
- **a_max**: ~10–12 m/s²  
- **a_min**: ~9–9.8 m/s²  
- **(a_max - a_min)**: **~1–3 m/s²**  
- Peak is relatively broad (sustained above threshold 50–150 ms).

## Changes made (robustness)

1. **Step validity (reject non-walk)**
   - Only count a step if:
     - `(a_max - a_min) <= 4.0` m/s² (or 0.4 in g) → rejects large swings (shaking 7–10).
     - `a_max <= 13.0` m/s² (or 1.35 in g) → rejects very high peaks (shaking 17–19).
   - Unit-agnostic: use `magnitudeBaseline > 5` to assume m/s², else g.

2. **Peak sustain**
   - Require magnitude to stay above `baseline + 0.5×minPeakHeight` for at least **55 ms** before the peak.
   - Walking has a rounded, sustained rise; shaking tends to produce narrow spikes.

3. **Deeper valley**
   - `valleyRatio` increased from 0.015 to **0.04** (must drop 4% below baseline to count as valley).
   - Reduces false “valleys” during high-frequency shake.

4. **Reset on reject**
   - When a candidate step is rejected, reset `stepCycleAmax` / `stepCycleAmin` to current magnitude so the next cycle does not reuse the same violent swing.

## Tuning (in `stepConfig`)

- `maxDeltaForWalk` / `maxPeakForWalk`: loosen to allow running (e.g. 5.0 / 14.0) if needed.
- `minPeakSustainMs`: increase (e.g. 70 ms) if shaking still passes; decrease if slow walk is missed.

---

## Heading drift on 90° turn (separate fix)

**Symptom**: Trajectory drifts when you turn 90° (e.g. corner).

**Cause**: (1) When gyro and mag disagreed we trusted gyro 98% → after the turn we followed drifting gyro. (2) No correction of gyro toward magnetometer, so integration error accumulated.

**Fix in code**:
- **Drift correction**: Every orientation update, pull gyro toward mag: `headingGyroDeg += GYRO_DRIFT_CORRECT_GAIN * angularDiff(mag - gyro)`. So after a turn, mag is correct and we converge to it.
- **Trust mag more**: Default fusion 45% gyro / 55% mag (`FUSION_ALPHA_STABLE = 0.45`). Only switch to gyro-heavy (`FUSION_ALPHA_DISTURBED = 0.85`) when we see a **sudden mag jump** (|Δmag| > 25° in one sample), not when gyro and mag disagree (normal during a turn).
- **MAG_JUMP_THRESHOLD_DEG**: Detects magnetic interference; only then we rely more on gyro temporarily.
