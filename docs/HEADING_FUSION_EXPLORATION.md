# Heading Fusion: Current Approach vs Error-State Kalman Filter

## 0. Handling different phone orientations (pocket vs hand)

**Problem:** The gyro gives angular velocity in the **device frame** (rotationRate.alpha/beta/gamma around device Z/Y/X). When the phone is upright, rotation around device Z is roughly “yaw” (turn left/right). When the phone is in a pocket (vertical) or held flat, device Z is no longer the world vertical, so **using only rot.alpha** is wrong: we’d be integrating the wrong axis.

**Approach:** We need **yaw rate** = rotation rate around the **world vertical** (gravity axis). In the device frame, the gravity direction is given by **accelerationIncludingGravity**. So:

1. **Gravity in device frame:** `g_unit = normalize(accelerationIncludingGravity)`.
2. **Angular velocity vector** in device frame (W3C: alpha=Z, beta=Y, gamma=X):  
   `omega = (rot.gamma, rot.beta, rot.alpha)` for axes (X, Y, Z).
3. **Yaw rate** (rotation around gravity axis) = component of omega along g_unit:  
   `yaw_rate = omega · g_unit = rot.gamma * g_unit.x + rot.beta * g_unit.y + rot.alpha * g_unit.z`.

Then integrate `yaw_rate * dt` for gyro heading. This works for any phone pose (pocket, hand, tilted). When `accelerationIncludingGravity` is unavailable or too small, fall back to `rot.alpha` (old behavior for upright phone).

**Magnetometer:** Compass (e.alpha / webkitCompassHeading) is usually already in world frame (0 = North) when the API provides it; fusion with the above gyro heading remains valid.

---

# Heading Fusion: Current Approach vs Error-State Kalman Filter

## 1. Current approach (what we have)

- **onMotion**: Integrate gyro yaw rate → `headingGyroDeg += sign * rot.alpha * dt`. Single Euler integration; no explicit gyro bias.
- **onOrientation**: Use mag (e.alpha or webkitCompassHeading) to:
  - Initialize heading when no gyro has been seen yet.
  - Correct gyro drift: `headingGyroDeg += GYRO_DRIFT_CORRECT_GAIN * (mag - gyro)`.
  - Fuse output: `headingFusedDeg = magReliability * headingGyroDeg + (1 - magReliability) * magDeg`.
- **Heuristic**: If mag jumps a lot (> 25°) → trust mag less (magReliability = 0.85 gyro / 0.15 mag); else trust mag more (0.45 gyro / 0.55 mag).

### Is it robust enough?

**Strengths:**
- Works with two different event streams (motion vs orientation) and different rates.
- Mag provides absolute reference; drift correction prevents unbounded gyro drift.
- Simple, small code surface, no matrix math.

**Limitations:**
- **No gyro bias estimate**: Drift is only corrected by pulling toward mag, not by estimating a bias term. In indoor/magnetic disturbance, gyro can drift until next good mag.
- **Fixed gains**: `GYRO_DRIFT_CORRECT_GAIN` and `magReliability` are tuned constants, not derived from sensor uncertainties. We don’t model process or measurement noise.
- **Heuristic mag trust**: Mag jump threshold helps with disturbances but doesn’t represent uncertainty (e.g. we don’t have “variance of mag”).
- **No optimal blending**: Fusion is a fixed weighted average, not a minimum-variance estimate given predicted and measured uncertainties.

So: it’s **practically robust** for many walking scenarios, but it’s **heuristic** and not optimal in a statistical sense.

---

## 2. Error-state Kalman filter (ESKF) in a nutshell

- **Idea**: Keep a “nominal” state (e.g. quaternion for attitude) and a **small error state** (e.g. 3D angle error). Predict nominal state with the IMU; propagate **error state and its covariance** with a linearized model. Use measurements to correct the **error state** via Kalman update; then inject error into nominal state and reset error to zero.
- **Why error state**: For 3D attitude, the full state (quaternion) is not Gaussian and has constraints (unit norm). The error state is a small 3D vector, so we can use a standard linear Kalman update and avoid singularities/non-uniqueness of quaternions.
- **Typical use**: High-end IMU fusion (drones, AR, INS): state = orientation (+ optionally position/velocity), measurements = accel (gravity direction), magnetometer (heading), sometimes vision/GNSS. Process model: gyro integration; measurement model: predicted gravity/mag vs observed.

**Relevance here:** We only need **heading (yaw)** for 2D PDR. Full 3D attitude (pitch/roll) is not used in the trajectory. So we have a **1D problem** (yaw + optional gyro bias), not a full 3D attitude problem.

---

## 3. Applying Kalman-style fusion to our case

### Option A: 1D (scalar) Kalman filter for yaw only

- **State**: `x = [heading_deg]` or `x = [heading_deg, gyro_bias_deg_s]`.
- **Predict** (at each gyro sample):  
  `heading += (gyro - bias) * dt`, optionally `bias += 0` or small random walk.  
  Covariance: P grows with process noise (integration error, bias uncertainty).
- **Update** (when mag arrives):  
  Measurement = mag heading. Innovation = mag - predicted_heading (wrapped). Kalman gain K = P / (P + R); update state and P.  
  This gives **optimal linear blending** of prediction and mag from variances (P = predicted variance, R = mag variance).
- **Pros**: Principled, minimal-variance estimate; can add gyro bias as state and estimate it when mag is good. No quaternions.
- **Cons**: Need to tune process noise Q and measurement noise R; handle angle wrapping in innovation (e.g. wrap to [-180, 180]).

This is **not** “error-state” in the full sense—it’s a standard (E)KF on a 1D state. It’s the natural next step if we want something more robust than fixed-gain fusion.

### Option B: Full 3D orientation ESKF

- **State**: Quaternion (nominal) + error state (3D angle) + optionally gyro bias (3D).
- **Predict**: Integrate gyro into quaternion; propagate error-state covariance with linearized dynamics (F, Q).
- **Measurements**:  
  - Accel → gravity direction (pitch/roll).  
  - Mag → heading (yaw), often after projecting into horizontal plane using pitch/roll.
- **Update**: Correct error state with Kalman update; inject into quaternion and renormalize; reset error to zero.
- **Pros**: Theoretically optimal for 3D orientation; can fuse accel + gyro + mag; gyro bias estimable.
- **Cons**: More complex (quaternions, linearization, different rates for accel vs mag). For **2D PDR we only need yaw**; pitch/roll don’t affect our trajectory. So this is **overkill** unless we later need full device attitude (e.g. vertical acceleration in world frame for step detection).

---

## 4. Recommendation (explore first, then decide)

- **Current approach**: Adequate for many use cases; main weaknesses are no gyro bias estimate and non-optimal, heuristic fusion.
- **Error-state Kalman filter**: Full ESKF is designed for **3D attitude** (quaternion + error state). For our app we only use **yaw** for the trajectory, so a **1D Kalman filter** (yaw, optionally yaw + gyro bias) is the right level of complexity.
- **Practical path**:
  1. **Short term**: Keep current fusion; optionally tune gains and mag-jump logic if you see specific failures.
  2. **If you want a principled upgrade**: Implement a **1D EKF for heading** (state = yaw or [yaw, gyro_bias]; predict from gyro; update with mag when available). Use process noise Q and measurement noise R (and optionally adaptive R when mag jumps) instead of fixed magReliability and GYRO_DRIFT_CORRECT_GAIN.
  3. **Full 3D ESKF**: Consider only if you later need full device orientation (e.g. world-frame vertical acceleration, or richer AR features), and are willing to handle quaternions, different sensor rates, and magnetometer in horizontal plane.

So: **Yes, we can use Kalman-style fusion.** For our current “heading only” use case, a **1D EKF (or KF with bias)** is the right target, not a full error-state quaternion ESKF. I can outline or implement the 1D EKF (state model, predict/update, angle wrapping, and how to plug it into onMotion/onOrientation) as a next step if you want to go that direction.
