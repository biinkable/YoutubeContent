"""Integration test: hits the real YouTube Data API.

Skipped unless YOUTUBE_API_KEY is set in the environment.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.research.fetch_viral_from_seeds import run

_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()

pytestmark = pytest.mark.skipif(
    not _API_KEY, reason="YOUTUBE_API_KEY not set; skipping live integration test"
)


def test_run_against_youtubecreators(tmp_path: Path) -> None:
    """Hit @YouTubeCreators (a stable, official channel) and verify output shape."""
    out = tmp_path / "research.json"
    result = run(
        seeds=["@YouTubeCreators"],
        defaults={
            "recency_days": 365,           # wide window — YouTubeCreators posts rarely
            "min_views_per_day": 1,        # very low so we actually get results
            "max_videos_per_channel": 3,
            "fetch_transcripts": False,    # keep test fast
            "transcript_languages": ["en"],
        },
        api_key=_API_KEY,
        out_path=out,
        now=lambda: datetime.now(timezone.utc),
    )
    # basic shape assertions — we don't assert on exact video content since it changes
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["channels"][0]["resolved_ok"] is True
    assert loaded["channels"][0]["channel_id"].startswith("UC")
    assert len(loaded["videos"]) >= 1
    v = loaded["videos"][0]
    for key in (
        "video_id", "title", "url", "thumbnail_url",
        "published_at", "days_since_publish", "views", "views_per_day",
    ):
        assert key in v, f"missing key: {key}"
