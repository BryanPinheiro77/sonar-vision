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
    """Default unless explicitly configured: audio stays null, as the issue requires."""

    def __init__(self, session_id: str):
        pass

    def select(self, observation, *, capture_age_lower_bound_ms):
        return None


def audio_policy_factory(config, *, clock=None) -> PolicyFactory:
    """Opt-in experimental policy; callers must supply reviewed configuration.

    No implicit thresholds or change to the API's NullPolicy default. Each
    call creates independent state, including devices sharing a session ID.
    """
    from sonar_vision.audio import AudioConfig, AudioPolicy

    if not isinstance(config, AudioConfig):
        raise TypeError("config must be AudioConfig")

    def create(session_id):
        if clock is None:
            return AudioPolicy(session_id, config)
        return AudioPolicy(session_id, config, clock=clock)

    return create
