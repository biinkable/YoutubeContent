"""Pure-function helpers for viral-video scoring and filtering."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable


def views_per_day(views: int, days_since_publish: int) -> float:
    """Compute views/day, treating <1 day as 1 day to avoid divide-by-zero.

    Handles clock skew (negative days) by clamping to 1.
    """
    return float(views) / float(max(1, days_since_publish))


def filter_viral(
    videos: list[dict],
    *,
    min_vps: float,
    max_per_channel: int,
    fallback_top_pct: float = 0.20,
) -> list[dict]:
    """Filter videos to viral hits per channel with a top-N fallback.

    Each input dict must have: video_id, channel_id, views, views_per_day.
    Rules:
      1. Group by channel_id.
      2. For each channel, keep videos with views_per_day >= min_vps.
      3. If a channel has zero above-threshold hits, keep top ceil(N * fallback_top_pct)
         of that channel's videos by view count (at least 1).
      4. Cap each channel's contribution at max_per_channel, keeping the highest
         views_per_day.
    """
    by_channel: dict[str, list[dict]] = defaultdict(list)
    for v in videos:
        by_channel[v["channel_id"]].append(v)

    result: list[dict] = []
    for _channel_id, ch_videos in by_channel.items():
        above = [v for v in ch_videos if v["views_per_day"] >= min_vps]
        if above:
            picked = above
        else:
            keep_n = max(1, math.ceil(len(ch_videos) * fallback_top_pct))
            picked = sorted(ch_videos, key=lambda v: v["views"], reverse=True)[:keep_n]
        picked = sorted(picked, key=lambda v: v["views_per_day"], reverse=True)[:max_per_channel]
        result.extend(picked)
    return result
