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

        api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=languages)
        segments = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else fetched
        text = " ".join(seg["text"] for seg in segments)
    except Exception:
        return (None, "none")
    return (text, "captions")
