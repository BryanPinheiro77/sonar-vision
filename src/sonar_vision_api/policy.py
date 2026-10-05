"""Seam for the announcement policy owned by another issue (#5/#31).

The API creates one policy per device session and calls it after the
observation is ready. The shape matches `AudioPolicy(session_id, config)
.select(observation, capture_age_lower_bound_ms=...)` proposed on the
`anuncios-por-audio` branch, so integrating it is a factory change:
`policy_factory=lambda session_id: AudioPolicy(session_id, config)`.
"""

from typing import Callable, Protocol


class SuggestionPolicy(Protocol):
    def select(self, observation: dict, *, capture_age_lower_bound_ms: int) -> dict | None:
        """Return an audio_suggestion dict or None; the API validates it."""


PolicyFactory = Callable[[str], SuggestionPolicy]


class NullPolicy:
    """Default while no policy is merged: audio stays null, as the issue requires."""

    def __init__(self, session_id: str):
        pass

    def select(self, observation, *, capture_age_lower_bound_ms):
        return None
