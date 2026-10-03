"""Reference model of local audio priority, interruption and validity (#25).

Executable specification for docs/protocol/audio-local.md, not firmware.
All times are local monotonic milliseconds. The model only decides what to
say; vibration (#9) is never an input or output here and never waits for it.

Priorities: P0 local urgency > P1 local availability notice > P2 visual suggestion.
"""

from dataclasses import dataclass
import math
from numbers import Real
from typing import Callable

from .catalog import InstalledCatalog

URGENT_ID = "local.urgent"
AVAILABILITY_IDS = {"unavailable": "local.visual_unavailable", "restored": "local.visual_restored"}


@dataclass(frozen=True)
class Profile:
    """Approved experimental profile of contract 0.1; values are not safety limits."""
    validity_ms: int = 1000
    max_orientation_change_deg: float = 15.0
    availability_cooldown_ms: int = 10000


@dataclass(frozen=True)
class Suggestion:
    """Already-parsed audio_suggestion of contract 0.1 (schema checks happen before)."""
    message_id: str
    session_id: str
    frame_id: str
    captured_at_ms: int
    valid_for_ms: int
    text: str
    directional: bool


@dataclass
class _Playing:
    kind: str  # urgent | availability | visual
    phrase_id: str
    suggestion: Suggestion | None = None


# orientation(captured_at_ms) -> relative 3D rotation in degrees since that capture,
# a finite number in [0, 180], or None when invalid/stale/not comparable (#9 provides
# samples). Any other value (NaN, infinity, negative, >180) is treated as invalid.
Orientation = Callable[[int], float | None]


class Arbiter:
    def __init__(self, catalog: InstalledCatalog | None, session_id: str,
                 captures: dict[str, int], orientation: Orientation, profile: Profile = Profile()):
        self.catalog, self.session_id, self.profile = catalog, session_id, profile
        self.captures = captures  # local capture records: frame_id -> captured_at_ms
        self.orientation = orientation
        self.log: list[tuple] = []
        self.current: _Playing | None = None
        self.pending: Suggestion | None = None
        self.urgent = False
        self.urgency_released_at: int | None = None
        self.availability_state: str | None = None
        self.announced_availability: str | None = None
        self.last_availability_start: int | None = None
        self.last_admitted_capture = -1
        self.consumed: dict[str, Suggestion] = {}

    # ----- outputs -------------------------------------------------------
    def _emit(self, *event):
        self.log.append(event)

    def _start(self, kind, phrase_id, suggestion=None):
        self.current = _Playing(kind, phrase_id, suggestion)
        self._emit("start", phrase_id)

    def _interrupt(self, reason):
        self._emit("interrupt", self.current.phrase_id, reason)
        self.current = None

    def _discard(self, suggestion, reason):
        self._emit("discard", suggestion.message_id, reason)

    # ----- inputs --------------------------------------------------------
    def urgency(self, now: int, active: bool) -> None:
        """Local urgency episode from #9 (its thresholds/hysteresis are not chosen here)."""
        if active and not self.urgent:
            self.urgent = True
            if self.current is not None and self.current.kind != "urgent":
                self._interrupt("urgent")
            if self.pending is not None:
                self._discard(self.pending, "urgent")
                self.pending = None
            # One generic short warning per episode; never names class or direction.
            if self.current is None:
                if self.catalog is not None and self.catalog.playable(URGENT_ID):
                    self._start("urgent", URGENT_ID)
                else:
                    self._emit("diagnostic", "essential_audio_unavailable")
        elif not active and self.urgent:
            self.urgent = False
            self.urgency_released_at = now
            self._next(now)

    def availability(self, now: int, state: str) -> None:
        """Stabilized local transition (3000 ms / 3 results, from contract 0.1)."""
        if state not in AVAILABILITY_IDS:
            raise ValueError("state must be unavailable or restored")
        self.availability_state = state
        self._next(now)

    def suggestion(self, now: int, item: Suggestion) -> None:
        reason = self._admission(now, item)
        if reason is not None:
            self._discard(item, reason)
            return
        self.consumed[item.message_id] = item
        self.last_admitted_capture = item.captured_at_ms
        if self.pending is not None:
            self._discard(self.pending, "replaced")
        self.pending = item
        self._emit("accepted", item.message_id)
        self._next(now)

    def tick(self, now: int) -> None:
        """Re-check the current directional speech while it plays (no network wait)."""
        playing = self.current
        if playing is not None and playing.kind == "visual":
            reason = self._still_valid(now, playing.suggestion)
            if reason is not None:
                self._interrupt(reason)
        self._next(now)

    def finished(self, now: int) -> None:
        if self.current is not None:
            self._emit("finished", self.current.phrase_id)
            self.current = None
        self._next(now)

    # ----- rules ---------------------------------------------------------
    def _admission(self, now, item: Suggestion) -> str | None:
        if item.session_id != self.session_id:
            return "session_mismatch"
        previous = self.consumed.get(item.message_id)
        if previous is not None:
            return "duplicate" if previous == item else "conflict"
        if self.captures.get(item.frame_id) != item.captured_at_ms:
            return "capture_mismatch"
        reason = self._still_valid(now, item)
        if reason is not None:
            return reason
        if self.urgent:
            return "urgent_active"
        # Only captures made strictly AFTER the release; the release instant itself is excluded.
        if self.urgency_released_at is not None and item.captured_at_ms <= self.urgency_released_at:
            return "captured_before_urgency_release"
        if item.captured_at_ms < self.last_admitted_capture:
            return "stale_capture"
        if self.catalog is None:
            return "catalog_unavailable"
        entry = self.catalog.resolve_text(item.text)
        if entry is None:
            return "phrase_not_in_catalog"
        if entry.path is None:
            return "audio_missing"
        return None

    def _still_valid(self, now, item: Suggestion) -> str | None:
        age = now - item.captured_at_ms
        if age < 0 or age >= min(item.valid_for_ms, self.profile.validity_ms):
            return "expired"
        if item.directional:
            change = self.orientation(item.captured_at_ms)
            # Smallest 3D rotation between two orientations lies in [0, 180] degrees.
            # None, NaN, infinities, booleans, negatives or >180 are not a valid measurement.
            if (change is None or isinstance(change, bool) or not isinstance(change, Real)
                    or not math.isfinite(change) or not 0 <= change <= 180):
                return "orientation_invalid"
            if change > self.profile.max_orientation_change_deg:
                return "orientation_changed"
        return None

    def _next(self, now) -> None:
        if self.current is not None or self.urgent:
            return
        state = self.availability_state
        if state is not None and state != self.announced_availability:
            last = self.last_availability_start
            if last is None or now - last >= self.profile.availability_cooldown_ms:
                # Speaks the state at start time; old transitions are not replayed.
                self.last_availability_start, self.announced_availability = now, state
                phrase = AVAILABILITY_IDS[state]
                if self.catalog is not None and self.catalog.playable(phrase):
                    self._start("availability", phrase)
                    return
                self._emit("diagnostic", "essential_audio_unavailable")
        if self.pending is not None:
            item, self.pending = self.pending, None
            reason = self._still_valid(now, item)
            if reason is not None:
                self._discard(item, reason)
                return
            self._start("visual", self.catalog.resolve_text(item.text).id, item)
