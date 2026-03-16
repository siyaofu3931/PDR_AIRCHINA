import math
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))


def wrap_deg(d: float) -> float:
    d = d % 360.0
    return d + 360.0 if d < 0 else d


def wrap_rad(r: float) -> float:
    while r <= -math.pi:
        r += 2 * math.pi
    while r > math.pi:
        r -= 2 * math.pi
    return r


@dataclass
class PdrConfig:
    # Step detection (aligned with pedestrian_dead_reckoning benchmark)
    min_period_ms: float = 350.0
    max_period_ms: float = 2000.0
    adaptive_window_ms: float = 2000.0
    adaptive_k: float = 0.5
    bandpass_low_hz: float = 0.5
    bandpass_high_hz: float = 3.0
    default_threshold: float = 0.5
    min_samples_for_threshold: int = 20
    min_prominence: float = 0.35
    thr_floor: float = 0.15
    valley_below_mu: bool = True
    valley_timeout_ms: float = 1500.0  # force allow next step if no step for this long
    gap_reset_dt_ms: float = 150.0  # reset band-pass state when gap exceeds this
    # Gravity / signal
    gravity_alpha: float = 0.92
    gravity_init_samples: int = 5  # init gravity from first N samples (mean of acc_g)
    k_weinberg: float = 0.5
    gyro_alpha_sign: float = -1.0
    map_match_max_snap_m: float = 7.0
    map_match_smooth_alpha: float = 0.35
    corridor_relpath: str = "data/corridors.json"


@dataclass
class PdrState:
    step_count: int = 0
    distance_m: float = 0.0
    heading_fused_deg: float = 0.0
    heading_gyro_rad: float = 0.0
    heading_mag_deg: Optional[float] = None
    mag_source_weight: float = 0.0
    mag_trust: float = 0.0
    x: float = 0.0
    y: float = 0.0
    step_length_m: float = 0.7
    last_motion_ms: Optional[float] = None
    last_step_time_ms: float = 0.0
    step_intervals: list = field(default_factory=list)
    gravity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    lin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    step_sig: float = 0.0
    recording_start_ms: float = 0.0
    turn_mode: bool = False
    turn_mode_until_ms: float = 0.0
    matched_x: float = 0.0
    matched_y: float = 0.0
    matched_confidence: float = 0.0
    current_edge_id: Optional[str] = None
    map_match_enabled: bool = False
    map_match_ready: bool = False
    # Benchmark-style step detection (band-pass + time-based threshold + prominence)
    last_step_detect_ms: Optional[float] = None
    bp_hp_prev: float = 0.0
    bp_lp_prev: float = 0.0
    last_mag_raw: Optional[float] = None
    mag_buffer: list = field(default_factory=list)  # [(t_ms, v), ...]
    mag_prev2: Optional[float] = None
    mag_prev1: Optional[float] = None
    min_since_last_step: float = 1e9
    had_valley_since_last_step: bool = True
    gravity_initialized: bool = False
    gravity_init_buf: list = field(default_factory=list)  # [(gx,gy,gz), ...] for init


@dataclass
class CorridorEdge:
    edge_id: str
    points: List[Tuple[float, float]]


class CorridorMatcher:
    def __init__(self, corridor_file: Path, max_snap_m: float, smooth_alpha: float):
        self.max_snap_m = max_snap_m
        self.smooth_alpha = clamp(smooth_alpha, 0.0, 1.0)
        self.edges: List[CorridorEdge] = []
        self._load(corridor_file)

    @property
    def ready(self) -> bool:
        return len(self.edges) > 0

    def _load(self, corridor_file: Path) -> None:
        if not corridor_file.exists():
            return
        try:
            payload = json.loads(corridor_file.read_text(encoding="utf-8"))
            edges = payload.get("edges") or []
            for idx, e in enumerate(edges):
                pts_raw = e.get("points") or []
                pts: List[Tuple[float, float]] = []
                for p in pts_raw:
                    if isinstance(p, list) and len(p) >= 2:
                        x = float(p[0])
                        y = float(p[1])
                        if math.isfinite(x) and math.isfinite(y):
                            pts.append((x, y))
                if len(pts) >= 2:
                    edge_id = str(e.get("id") or f"edge_{idx}")
                    self.edges.append(CorridorEdge(edge_id=edge_id, points=pts))
        except Exception:
            self.edges = []

    def _project_point_to_segment(
        self, px: float, py: float, ax: float, ay: float, bx: float, by: float
    ) -> Tuple[float, float, float]:
        vx = bx - ax
        vy = by - ay
        vv = vx * vx + vy * vy
        if vv <= 1e-9:
            dx = px - ax
            dy = py - ay
            return ax, ay, math.sqrt(dx * dx + dy * dy)
        t = ((px - ax) * vx + (py - ay) * vy) / vv
        t = clamp(t, 0.0, 1.0)
        qx = ax + t * vx
        qy = ay + t * vy
        dx = px - qx
        dy = py - qy
        return qx, qy, math.sqrt(dx * dx + dy * dy)

    def snap(
        self, x: float, y: float, heading_deg: float, prev_edge_id: Optional[str]
    ) -> Tuple[float, float, float, Optional[str]]:
        if not self.ready:
            return x, y, 0.0, None

        best = None
        for edge in self.edges:
            pts = edge.points
            for i in range(1, len(pts)):
                ax, ay = pts[i - 1]
                bx, by = pts[i]
                qx, qy, dist = self._project_point_to_segment(x, y, ax, ay, bx, by)
                heading_seg = wrap_deg(math.degrees(math.atan2(bx - ax, by - ay)))
                heading_err = abs(wrap_deg(heading_deg - heading_seg))
                heading_err = min(heading_err, 360.0 - heading_err)
                score = dist + 0.02 * heading_err
                if prev_edge_id is not None and edge.edge_id != prev_edge_id:
                    score += 0.8
                if best is None or score < best[0]:
                    best = (score, dist, qx, qy, edge.edge_id)

        if best is None:
            return x, y, 0.0, None

        _, dist, qx, qy, edge_id = best
        if dist > self.max_snap_m:
            return x, y, 0.0, None
        confidence = clamp(1.0 - dist / max(self.max_snap_m, 1e-6), 0.0, 1.0)
        return qx, qy, confidence, edge_id


class PdrEngine:
    def __init__(self, config: Optional[PdrConfig] = None):
        self.cfg = config or PdrConfig()
        self.state = PdrState()
        corridor_file = Path(__file__).resolve().parents[1] / self.cfg.corridor_relpath
        self.matcher = CorridorMatcher(
            corridor_file=corridor_file,
            max_snap_m=self.cfg.map_match_max_snap_m,
            smooth_alpha=self.cfg.map_match_smooth_alpha,
        )

    def reset(self, t_ms: float) -> None:
        self.state = PdrState(recording_start_ms=t_ms)
        self.state.map_match_ready = self.matcher.ready

    def _update_heading_mag(self, orientation: Dict) -> None:
        webkit = orientation.get("webkitCompassHeading")
        alpha = orientation.get("alpha")
        absolute = orientation.get("absolute")
        if isinstance(webkit, (int, float)) and math.isfinite(webkit):
            self.state.heading_mag_deg = float(webkit)
            self.state.mag_source_weight = 1.0
        elif absolute is True and isinstance(alpha, (int, float)) and math.isfinite(alpha):
            self.state.heading_mag_deg = 360 - float(alpha)
            self.state.mag_source_weight = 0.85
        elif isinstance(alpha, (int, float)) and math.isfinite(alpha):
            self.state.heading_mag_deg = 360 - float(alpha)
            self.state.mag_source_weight = 0.45

    def _update_turn_mode(self, yaw_rate_deg_s: float, t_ms: float) -> None:
        abs_rate = abs(yaw_rate_deg_s)
        if abs_rate >= 55.0:
            self.state.turn_mode = True
            self.state.turn_mode_until_ms = t_ms + 450.0
        elif self.state.turn_mode and abs_rate <= 30.0 and t_ms > self.state.turn_mode_until_ms:
            self.state.turn_mode = False

    def _update_heading(self, rot: Dict, t_ms: float) -> None:
        alpha = rot.get("alpha")
        if not isinstance(alpha, (int, float)) or not math.isfinite(alpha):
            return
        if self.state.last_motion_ms is None:
            self.state.last_motion_ms = t_ms
            if self.state.heading_mag_deg is not None:
                self.state.heading_gyro_rad = math.radians(wrap_deg(self.state.heading_mag_deg))
                self.state.heading_fused_deg = wrap_deg(self.state.heading_mag_deg)
            return
        dt = (t_ms - self.state.last_motion_ms) / 1000.0
        self.state.last_motion_ms = t_ms
        if dt <= 0.0 or dt > 0.2:
            return
        yaw_rate = self.cfg.gyro_alpha_sign * float(alpha)
        self._update_turn_mode(yaw_rate, t_ms)
        self.state.heading_gyro_rad = wrap_rad(self.state.heading_gyro_rad + math.radians(yaw_rate * dt))
        if self.state.heading_mag_deg is not None:
            mag_rad = math.radians(wrap_deg(self.state.heading_mag_deg))
            innov = wrap_rad(mag_rad - self.state.heading_gyro_rad)
            trust_raw = (1.0 - abs(innov) / math.radians(120.0)) * self.state.mag_source_weight
            self.state.mag_trust = clamp(
                trust_raw, 0.2 * self.state.mag_source_weight, self.state.mag_source_weight
            )
            base_gain = 0.14 if self.state.mag_source_weight >= 0.95 else 0.10
            turn_boost = 1.9 if self.state.turn_mode else 1.0
            self.state.heading_gyro_rad = wrap_rad(self.state.heading_gyro_rad + base_gain * turn_boost * innov)
        self.state.heading_fused_deg = wrap_deg(math.degrees(self.state.heading_gyro_rad))

    def _step_detect(self, frame: Dict, t_ms: float) -> bool:
        """Step detection aligned with pedestrian_dead_reckoning benchmark: orientation-invariant
        magnitude, band-pass 0.5-3 Hz, time-based adaptive threshold (mean + k*sigma), prominence + valley.
        Uses acc_linear when provided by client (device gravity removal); else acc_including_g with backend gravity removal.
        """
        acc_g = frame.get("acc_including_g") or {}
        ax = float(acc_g.get("x", 0.0))
        ay = float(acc_g.get("y", 0.0))
        az = float(acc_g.get("z", 0.0))
        gx, gy, gz = self.state.gravity
        if not self.state.gravity_initialized:
            self.state.gravity_init_buf.append((ax, ay, az))
            if len(self.state.gravity_init_buf) >= self.cfg.gravity_init_samples:
                n = len(self.state.gravity_init_buf)
                gx = sum(p[0] for p in self.state.gravity_init_buf) / n
                gy = sum(p[1] for p in self.state.gravity_init_buf) / n
                gz = sum(p[2] for p in self.state.gravity_init_buf) / n
                self.state.gravity = (gx, gy, gz)
                self.state.gravity_initialized = True
                self.state.gravity_init_buf.clear()
            else:
                lx, ly, lz = 0.0, 0.0, 0.0
        if self.state.gravity_initialized:
            a = self.cfg.gravity_alpha
            gx, gy, gz = self.state.gravity
            gx = a * gx + (1 - a) * ax
            gy = a * gy + (1 - a) * ay
            gz = a * gz + (1 - a) * az
            self.state.gravity = (gx, gy, gz)
            lx, ly, lz = ax - gx, ay - gy, az - gz
            self.state.lin = (lx, ly, lz)
        else:
            lx, ly, lz = 0.0, 0.0, 0.0

        # 1) Orientation-invariant magnitude: prefer linear acc from device when available (ALGORITHM_COMPARISON §6)
        acc_linear = frame.get("acc_linear")
        if acc_linear and isinstance(acc_linear, dict):
            lax = acc_linear.get("x"), acc_linear.get("y"), acc_linear.get("z")
            if all(isinstance(v, (int, float)) and math.isfinite(v) for v in lax):
                mag = math.sqrt(
                    float(lax[0]) ** 2 + float(lax[1]) ** 2 + float(lax[2]) ** 2
                )
            else:
                mag = math.sqrt(lx * lx + ly * ly + lz * lz)
        else:
            mag = math.sqrt(lx * lx + ly * ly + lz * lz)

        # 2) Time step for filter (cap to avoid big gaps from network jitter)
        raw_dt_ms = (
            (t_ms - self.state.last_step_detect_ms)
            if self.state.last_step_detect_ms is not None
            else 0.0
        )
        if raw_dt_ms > self.cfg.gap_reset_dt_ms:
            self.state.bp_hp_prev = 0.0
            self.state.bp_lp_prev = 0.0
            self.state.last_mag_raw = None
            self.state.had_valley_since_last_step = True
        if self.state.last_step_detect_ms is not None:
            dt_sec = min(raw_dt_ms / 1000.0, 0.1)
        else:
            dt_sec = 0.02
        self.state.last_step_detect_ms = t_ms

        # 3) Band-pass: high-pass at bandpass_low_hz, then low-pass at bandpass_high_hz
        tau_hp = 1.0 / (2.0 * math.pi * self.cfg.bandpass_low_hz)
        tau_lp = 1.0 / (2.0 * math.pi * self.cfg.bandpass_high_hz)
        alpha_hp = tau_hp / (tau_hp + dt_sec)
        alpha_lp = math.exp(-dt_sec / tau_lp)
        last_raw = self.state.last_mag_raw if self.state.last_mag_raw is not None else mag
        hp_out = alpha_hp * (self.state.bp_hp_prev + mag - last_raw)
        lp_out = alpha_lp * self.state.bp_lp_prev + (1.0 - alpha_lp) * hp_out
        self.state.bp_hp_prev = hp_out
        self.state.bp_lp_prev = lp_out
        self.state.last_mag_raw = mag
        self.state.step_sig = lp_out

        # 4) Time-based rolling buffer for adaptive threshold
        self.state.mag_buffer.append((t_ms, lp_out))
        cutoff = t_ms - self.cfg.adaptive_window_ms
        while self.state.mag_buffer and self.state.mag_buffer[0][0] < cutoff:
            self.state.mag_buffer.pop(0)

        self.state.min_since_last_step = min(self.state.min_since_last_step, lp_out)

        # 5) Adaptive threshold T = mu + k*sigma
        threshold = self.cfg.default_threshold
        mu = 0.0
        if len(self.state.mag_buffer) >= self.cfg.min_samples_for_threshold:
            vals = [e[1] for e in self.state.mag_buffer]
            mu = sum(vals) / len(vals)
            variance = sum((v - mu) ** 2 for v in vals) / len(vals)
            sigma = math.sqrt(max(0.0, variance))
            threshold = max(mu + self.cfg.adaptive_k * sigma, self.cfg.thr_floor)
        if self.cfg.valley_below_mu and len(self.state.mag_buffer) >= self.cfg.min_samples_for_threshold and lp_out < mu:
            self.state.had_valley_since_last_step = True
        if (
            self.cfg.valley_timeout_ms > 0
            and self.state.last_step_time_ms > 0
            and (t_ms - self.state.last_step_time_ms) >= self.cfg.valley_timeout_ms
        ):
            self.state.had_valley_since_last_step = True

        # 6) Peak check: mag_prev1 is local maximum, passes prominence and valley guard
        stepped = False
        if self.state.mag_prev2 is not None:
            is_local_max = self.state.mag_prev2 < self.state.mag_prev1 and self.state.mag_prev1 > lp_out
            above_threshold = self.state.mag_prev1 > threshold
            min_period_ok = (t_ms - self.state.last_step_time_ms) >= self.cfg.min_period_ms
            a_max = self.state.mag_prev1
            a_min = self.state.min_since_last_step
            prominence = a_max - a_min
            min_prominence_ok = prominence >= self.cfg.min_prominence
            is_first = self.state.last_step_time_ms == 0.0
            dt_step = t_ms - self.state.last_step_time_ms
            max_interval_ms = max(5000.0, self.cfg.max_period_ms)
            valid_interval = is_first or (self.cfg.min_period_ms <= dt_step <= max_interval_ms)

            if (
                is_local_max
                and above_threshold
                and min_period_ok
                and min_prominence_ok
                and self.state.had_valley_since_last_step
                and valid_interval
            ):
                step_len = self.cfg.k_weinberg * math.pow(max(0.01, prominence), 0.25)
                self.state.step_length_m = clamp(step_len, 0.35, 1.2)
                if not is_first:
                    self.state.step_intervals.append(dt_step)
                    if len(self.state.step_intervals) > 8:
                        self.state.step_intervals.pop(0)
                self.state.last_step_time_ms = t_ms
                self.state.min_since_last_step = 1e9
                self.state.had_valley_since_last_step = False
                stepped = True

        # 7) Shift history for next sample
        self.state.mag_prev2 = self.state.mag_prev1
        self.state.mag_prev1 = lp_out
        return stepped

    def process_frame(self, frame: Dict) -> Dict:
        t_ms = float(frame.get("t_ms") or 0.0)
        if t_ms <= 0:
            t_ms = 0.0
        self.state.map_match_enabled = bool(frame.get("map_match_enabled"))
        orientation = frame.get("orientation") or {}
        self._update_heading_mag(orientation)
        self._update_heading(frame.get("rotation_rate") or {}, t_ms)
        stepped = self._step_detect(frame, t_ms)
        if stepped:
            h = math.radians(self.state.heading_fused_deg)
            self.state.x += self.state.step_length_m * math.sin(h)
            self.state.y += self.state.step_length_m * math.cos(h)
            self.state.distance_m += self.state.step_length_m
            self.state.step_count += 1

        self.state.map_match_ready = self.matcher.ready
        if self.state.map_match_enabled and self.matcher.ready:
            sx, sy, conf, edge_id = self.matcher.snap(
                x=self.state.x,
                y=self.state.y,
                heading_deg=self.state.heading_fused_deg,
                prev_edge_id=self.state.current_edge_id,
            )
            if self.state.matched_confidence <= 1e-6:
                self.state.matched_x = sx
                self.state.matched_y = sy
            else:
                a = self.cfg.map_match_smooth_alpha
                self.state.matched_x = (1.0 - a) * self.state.matched_x + a * sx
                self.state.matched_y = (1.0 - a) * self.state.matched_y + a * sy
            self.state.matched_confidence = conf
            self.state.current_edge_id = edge_id
        else:
            self.state.matched_x = self.state.x
            self.state.matched_y = self.state.y
            self.state.matched_confidence = 0.0
            self.state.current_edge_id = None

        display_x = self.state.x
        display_y = self.state.y
        if self.state.map_match_enabled and self.state.matched_confidence > 0.0:
            display_x = self.state.matched_x
            display_y = self.state.matched_y

        return {
            "type": "pose_update",
            "t_ms": t_ms,
            "step_count": self.state.step_count,
            "distance_m": self.state.distance_m,
            "heading_deg": self.state.heading_fused_deg,
            "position": {"x": display_x, "y": display_y},
            "raw_position": {"x": self.state.x, "y": self.state.y},
            "matched_position": {"x": self.state.matched_x, "y": self.state.matched_y},
            "map_match_enabled": self.state.map_match_enabled,
            "map_match_ready": self.state.map_match_ready,
            "map_match_confidence": self.state.matched_confidence,
            "map_match_edge_id": self.state.current_edge_id,
            "turn_mode": self.state.turn_mode,
            "step_signal": self.state.step_sig,
            "step_length_m": self.state.step_length_m,
            "stepped": stepped,
        }
