"""CLI entrypoint: mine seed channels for recent viral videos, write JSON."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import yaml
from dotenv import load_dotenv

from scripts.research.metrics import filter_viral, views_per_day
from scripts.research.transcript_fetcher import fetch_transcript
from scripts.research.youtube_client import (
    ChannelNotFound,
    QuotaExceeded,
    YouTubeClient,
)

ClientFactory = Callable[[str], Any]
TranscriptFn = Callable[[str, list[str]], tuple[str | None, str]]
NowFn = Callable[[], datetime]


def _iso_z(dt: datetime) -> str:
    """Format a UTC datetime as ISO8601 with Z suffix (YouTube API convention)."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H-%M-%S")


def run(
    *,
    seeds: list[str],
    defaults: dict,
    api_key: str,
    out_path: Path,
    client_factory: ClientFactory | None = None,
    transcript_fn: TranscriptFn | None = None,
    now: NowFn | None = None,
) -> dict:
    """Orchestrate a full research run. Returns the JSON dict written to disk."""
    now_fn: NowFn = now or (lambda: datetime.now(timezone.utc))
    now_dt = now_fn()
    since_dt = now_dt - timedelta(days=defaults["recency_days"])
    since_iso = _iso_z(since_dt)

    make_client: ClientFactory = client_factory or (lambda k: YouTubeClient(k))
    client = make_client(api_key)
    transcript = transcript_fn or fetch_transcript

    channels_result: list[dict] = []
    all_video_records: list[dict] = []
    errors: list[dict] = []

    for seed in seeds:
        try:
            resolved = client.resolve_channel(seed)
        except ChannelNotFound as e:
            channels_result.append({"input": seed, "channel_id": None, "resolved_ok": False})
            errors.append({"channel_input": seed, "reason": str(e)})
            continue
        channels_result.append(
            {"input": seed, "channel_id": resolved.channel_id, "resolved_ok": True}
        )
        try:
            video_ids = client.list_recent_uploads(resolved.uploads_playlist_id, since_iso)
        except QuotaExceeded:
            raise
        if not video_ids:
            continue
        try:
            stats = client.get_video_stats(video_ids)
        except QuotaExceeded:
            raise

        for item in stats:
            snippet = item["snippet"]
            statistics = item.get("statistics", {})
            published_at = snippet["publishedAt"]
            published_dt = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            days = (now_dt - published_dt).days
            views = int(statistics.get("viewCount", "0"))
            vps = views_per_day(views, days)
            all_video_records.append(
                {
                    "channel_input": seed,
                    "channel_id": snippet["channelId"],
                    "video_id": item["id"],
                    "title": snippet["title"],
                    "url": f"https://youtube.com/watch?v={item['id']}",
                    "thumbnail_url": snippet["thumbnails"]["high"]["url"],
                    "published_at": published_at,
                    "days_since_publish": days,
                    "views": views,
                    "views_per_day": vps,
                    "transcript": None,
                    "transcript_source": "none",
                }
            )

    kept = filter_viral(
        all_video_records,
        min_vps=defaults["min_views_per_day"],
        max_per_channel=defaults["max_videos_per_channel"],
    )

    if defaults.get("fetch_transcripts"):
        langs = defaults.get("transcript_languages", ["en"])
        for v in kept:
            text, source = transcript(v["video_id"], langs)
            v["transcript"] = text
            v["transcript_source"] = source
            if source == "none":
                errors.append({"video_id": v["video_id"], "reason": "transcript unavailable"})

    output = {
        "run_id": _run_id(now_dt),
        "generated_at": _iso_z(now_dt),
        "params": defaults,
        "channels": channels_result,
        "videos": kept,
        "errors": errors,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    return output


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch recent viral videos from seed YouTube channels.")
    p.add_argument("--seeds", required=True, type=Path, help="Path to seed-channels.yaml")
    p.add_argument("--defaults", required=True, type=Path, help="Path to research-defaults.yaml")
    p.add_argument("--out", required=True, type=Path, help="Output JSON path")
    p.add_argument("--recency-days", type=int, help="Override defaults.recency_days")
    p.add_argument("--min-views-per-day", type=float, help="Override defaults.min_views_per_day")
    p.add_argument("--max-videos-per-channel", type=int, help="Override defaults.max_videos_per_channel")
    p.add_argument("--no-transcripts", action="store_true", help="Skip transcript fetching")
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    # Load .env from project root (parent of scripts/)
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")

    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        print(
            "ERROR: YOUTUBE_API_KEY not set. Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        return 2

    seeds_cfg = yaml.safe_load(args.seeds.read_text(encoding="utf-8")) or {}
    defaults = yaml.safe_load(args.defaults.read_text(encoding="utf-8")) or {}

    seeds = [s for s in (seeds_cfg.get("channels") or []) if s and not str(s).startswith("#")]
    if not seeds:
        print(
            f"ERROR: no channels configured in {args.seeds}. Add at least one entry.",
            file=sys.stderr,
        )
        return 2

    # apply CLI overrides
    if args.recency_days is not None:
        defaults["recency_days"] = args.recency_days
    if args.min_views_per_day is not None:
        defaults["min_views_per_day"] = args.min_views_per_day
    if args.max_videos_per_channel is not None:
        defaults["max_videos_per_channel"] = args.max_videos_per_channel
    if args.no_transcripts:
        defaults["fetch_transcripts"] = False

    try:
        run(seeds=seeds, defaults=defaults, api_key=api_key, out_path=args.out)
    except QuotaExceeded as e:
        print(
            f"ERROR: YouTube Data API quota exhausted. Wait until midnight Pacific or request an increase.\n{e}",
            file=sys.stderr,
        )
        return 3
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
