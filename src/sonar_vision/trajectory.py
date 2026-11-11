"""Time-based apparent box motion. No distance, TTC or camera compensation."""

from collections import deque
from dataclasses import asdict, dataclass, replace
import math


@dataclass(frozen=True)
class TrajectoryConfig:
    # Experimental lab parameters, not safety thresholds.
    window_seconds: float = 1.0
    min_span_seconds: float = 0.4
    min_samples: int = 5
    max_samples: int = 120
    max_gap_seconds: float = 0.5
    lateral_threshold: float = 0.08
    log_area_threshold: float = 0.15
    max_center_residual: float = 0.025
    max_log_area_residual: float = 0.12
    confirmation_seconds: float = 0.4

    def __post_init__(self):
        for key, value in asdict(self).items():
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0):
                raise ValueError(f"{key} must be finite and positive")
        if type(self.min_samples) is not int or type(self.max_samples) is not int:
            raise ValueError("sample counts must be integers")
        if not 2 <= self.min_samples <= self.max_samples:
            raise ValueError("require 2 <= min_samples <= max_samples")
        if self.min_span_seconds > self.window_seconds:
            raise ValueError("min_span_seconds must fit inside window")


@dataclass(frozen=True)
class Motion:
    movement: str = "unknown"
    reason: str = "insufficient_history"
    raw_movement: str = "unknown"
    lateral_direction: str | None = None  # image motion, NOT direction to the object
    center_velocity_x: float | None = None  # image widths/second
    center_velocity_y: float | None = None  # image heights/second
    log_area_rate: float | None = None  # ln(normalized area)/second
    span_seconds: float = 0.0
    samples: int = 0
    confirmation_elapsed_seconds: float = 0.0


def fit(times, values):
    """Least-squares slope and RMS residual; timestamps must have positive span."""
    mean_t, mean_v = sum(times)/len(times), sum(values)/len(values)
    variance = sum((t-mean_t)**2 for t in times)
    slope = sum((t-mean_t)*(v-mean_v) for t, v in zip(times, values)) / variance
    residual = math.sqrt(sum((v-mean_v-slope*(t-mean_t))**2
                             for t, v in zip(times, values)) / len(times))
    return slope, residual


class TrajectoryEstimator:
    def __init__(self, config=None):
        self.config = config or TrajectoryConfig()
        self.samples = deque(maxlen=self.config.max_samples)
        self.identity = None
        self._candidate = None
        self._candidate_since = None

    def reset(self):
        self.samples.clear()
        self.identity = None
        self._candidate = self._candidate_since = None

    def update(self, detection, captured_at_ms, camera_motion="unknown"):
        if camera_motion not in ("fixed", "moving", "unknown"):
            raise ValueError("invalid camera_motion")
        if type(captured_at_ms) is not int or not 0 <= captured_at_ms <= 2**53-1:
            raise ValueError("invalid captured_at_ms")
        if detection.track_id is None:
            self.reset()
            return Motion(reason="no_track")
        if camera_motion != "fixed":
            self.reset()
            return Motion(reason="camera_not_fixed")
        identity = (detection.track_id, detection.class_name)
        if identity != self.identity:
            self.reset()
            self.identity = identity
        if self.samples:
            delta_ms = captured_at_ms-self.samples[-1][0]
            if delta_ms <= 0:
                self.reset()
                return Motion(reason="nonincreasing_capture_time")
            if delta_ms > self.config.max_gap_seconds*1000:
                self.reset()
                self.identity = identity
        x1, y1, x2, y2 = detection.box
        self.samples.append((captured_at_ms, (x1+x2)/2, (y1+y2)/2,
                             math.log((x2-x1)*(y2-y1))))
        while captured_at_ms-self.samples[0][0] > self.config.window_seconds*1000:
            self.samples.popleft()
        result = self._estimate()
        raw = result.movement
        result = replace(result, raw_movement=raw)
        if raw not in ("approaching", "receding", "crossing"):
            self._candidate = self._candidate_since = None
            return result
        candidate = (raw, result.lateral_direction)
        if candidate != self._candidate:
            self._candidate, self._candidate_since = candidate, captured_at_ms
        elapsed = (captured_at_ms-self._candidate_since)/1000
        result = replace(result, confirmation_elapsed_seconds=elapsed)
        if elapsed + 1e-9 < self.config.confirmation_seconds:
            return replace(result, movement="unknown", reason="confirming_motion")
        return result

    def _estimate(self):
        span = (self.samples[-1][0]-self.samples[0][0])/1000
        result = Motion(span_seconds=span, samples=len(self.samples))
        if (len(self.samples) < self.config.min_samples
                or span + 1e-9 < self.config.min_span_seconds):
            return result
        times = [(s[0]-self.samples[0][0])/1000 for s in self.samples]
        (vx, rx), (vy, ry), (growth, ra) = [
            fit(times, [s[column] for s in self.samples]) for column in (1, 2, 3)]
        result = replace(result, center_velocity_x=vx, center_velocity_y=vy, log_area_rate=growth)
        if max(rx, ry) > self.config.max_center_residual or ra > self.config.max_log_area_residual:
            return replace(result, reason="unstable_boxes")
        lateral = abs(vx) >= self.config.lateral_threshold
        scaling = abs(growth) >= self.config.log_area_threshold
        if lateral and scaling:
            return replace(result, reason="mixed_scale_and_lateral")
        if abs(vy) >= self.config.lateral_threshold:
            return replace(result, reason="vertical_motion")
        if scaling:
            return replace(result, movement="approaching" if growth > 0 else "receding",
                           reason="apparent_scale_change")
        if lateral:
            return replace(result, movement="crossing", reason="apparent_lateral_motion",
                           lateral_direction="left_to_right" if vx > 0 else "right_to_left")
        return replace(result, movement="stable", reason="below_motion_thresholds")
