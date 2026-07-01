"""Shared pytest fixtures for research subsystem tests."""
from __future__ import annotations

import pytest


@pytest.fixture
def sample_video_stats() -> dict:
    """Minimal YouTube videos.list response for one video."""
    return {
        "items": [
            {
                "id": "abc123",
                "snippet": {
                    "channelId": "UC_test",
                    "title": "10 Secrets of Test",
                    "publishedAt": "2026-06-14T09:00:00Z",
                    "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg"}},
                },
                "statistics": {"viewCount": "421000"},
            }
        ]
    }
