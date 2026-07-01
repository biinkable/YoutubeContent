"""Fetch YouTube captions with graceful failure. Never raises to the caller."""
from __future__ import annotations

from typing import Any


def fetch_transcript(
    video_id: str,
    languages: list[str],
    *,
    api: Any | None = None,
) -> tuple[str | None, str]:
    """Return (joined_text, source) where source is "captions" or "none".

    Any exception from the underlying API (no captions, disabled, blocked, etc.)
    is caught and reported as (None, "none").
    """
    if api is None:
        # imported lazily so tests don't need the package installed for pure-logic paths
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi
    try:
        segments = api.get_transcript(video_id, languages=languages)
    except Exception:
        return (None, "none")
    text = " ".join(seg["text"] for seg in segments)
    return (text, "captions")
