"""Tests for metrics helpers."""
from __future__ import annotations

import pytest

from scripts.research.metrics import filter_viral, views_per_day


class TestViewsPerDay:
    def test_basic(self) -> None:
        assert views_per_day(10000, 10) == 1000.0

    def test_zero_days_is_treated_as_one(self) -> None:
        # a freshly-published video shouldn't cause division by zero
        assert views_per_day(5000, 0) == 5000.0

    def test_negative_days_treated_as_one(self) -> None:
        # clock skew safety
        assert views_per_day(5000, -3) == 5000.0

    def test_zero_views(self) -> None:
        assert views_per_day(0, 5) == 0.0


class TestFilterViral:
    def _video(self, vid: str, channel: str, views: int, vps: float) -> dict:
        return {
            "video_id": vid,
            "channel_id": channel,
            "views": views,
            "views_per_day": vps,
        }

    def test_keeps_videos_above_threshold(self) -> None:
        videos = [
            self._video("v1", "chA", 100, 15000),
            self._video("v2", "chA", 200, 5000),
        ]
        result = filter_viral(videos, min_vps=10000, max_per_channel=5)
        assert [v["video_id"] for v in result] == ["v1"]

    def test_fallback_when_no_hits_in_channel(self) -> None:
        # channel has 5 videos, none above threshold. top 20% = 1 video.
        videos = [
            self._video("v1", "chA", 100, 500),
            self._video("v2", "chA", 900, 400),  # top by views
            self._video("v3", "chA", 300, 300),
            self._video("v4", "chA", 500, 200),
            self._video("v5", "chA", 700, 100),
        ]
        result = filter_viral(videos, min_vps=10000, max_per_channel=5)
        assert [v["video_id"] for v in result] == ["v2"]

    def test_fallback_ceils_to_at_least_one(self) -> None:
        # 3 videos * 0.20 = 0.6 -> ceil to 1
        videos = [
            self._video("v1", "chA", 100, 500),
            self._video("v2", "chA", 900, 400),
            self._video("v3", "chA", 300, 300),
        ]
        result = filter_viral(videos, min_vps=10000, max_per_channel=5)
        assert [v["video_id"] for v in result] == ["v2"]

    def test_cap_per_channel(self) -> None:
        videos = [
            self._video("v1", "chA", 100, 30000),
            self._video("v2", "chA", 100, 25000),
            self._video("v3", "chA", 100, 20000),
            self._video("v4", "chA", 100, 15000),
        ]
        result = filter_viral(videos, min_vps=10000, max_per_channel=2)
        # cap keeps top 2 by views_per_day
        assert [v["video_id"] for v in result] == ["v1", "v2"]

    def test_multi_channel_independence(self) -> None:
        videos = [
            self._video("a1", "chA", 100, 30000),  # above threshold
            self._video("b1", "chB", 100, 500),    # below threshold
            self._video("b2", "chB", 900, 400),    # channel B fallback pick
        ]
        result = filter_viral(videos, min_vps=10000, max_per_channel=5)
        vids = sorted(v["video_id"] for v in result)
        assert vids == ["a1", "b2"]

    def test_empty_input(self) -> None:
        assert filter_viral([], min_vps=10000, max_per_channel=5) == []
