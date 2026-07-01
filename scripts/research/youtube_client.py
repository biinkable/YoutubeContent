"""Thin, dependency-injectable wrapper over the YouTube Data API v3."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from scripts.research.channel_resolver import normalize_for_api, parse_channel_input


class ChannelNotFound(Exception):
    """Raised when a channel input resolves to zero channels."""


class QuotaExceeded(Exception):
    """Raised when the YouTube Data API returns a quotaExceeded error."""


@dataclass(frozen=True)
class ResolvedChannel:
    input: str
    channel_id: str
    uploads_playlist_id: str


def _is_quota_error(err: HttpError) -> bool:
    try:
        body = json.loads(err.content.decode("utf-8"))
    except Exception:
        return False
    for e in body.get("error", {}).get("errors", []):
        if e.get("reason") in ("quotaExceeded", "rateLimitExceeded", "userRateLimitExceeded"):
            return True
    return False


def _retry(fn, *, retries: int = 3, base_delay: float = 1.0):
    """Retry a callable with exponential backoff on transient HttpErrors.

    Never retries quota errors — those are terminal for the run.
    """
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except HttpError as e:
            if _is_quota_error(e):
                raise QuotaExceeded(str(e)) from e
            status = getattr(getattr(e, "resp", None), "status", None)
            if attempt >= retries or (status is not None and status < 500 and status != 429):
                raise
            last = e
            time.sleep(base_delay * (3**attempt))
    raise last if last else RuntimeError("unreachable")


class YouTubeClient:
    def __init__(self, api_key: str, *, service: Any | None = None) -> None:
        self._service = service if service is not None else build(
            "youtube", "v3", developerKey=api_key, cache_discovery=False
        )

    def resolve_channel(self, raw: str) -> ResolvedChannel:
        parsed = parse_channel_input(raw)
        param_name, param_value = normalize_for_api(parsed)
        kwargs = {"part": "id,contentDetails", param_name: param_value}
        resp = _retry(lambda: self._service.channels().list(**kwargs).execute())
        items = resp.get("items", [])
        if not items:
            raise ChannelNotFound(f"no channel matched input: {raw!r}")
        item = items[0]
        return ResolvedChannel(
            input=raw,
            channel_id=item["id"],
            uploads_playlist_id=item["contentDetails"]["relatedPlaylists"]["uploads"],
        )

    def list_recent_uploads(self, uploads_playlist_id: str, since_iso: str) -> list[str]:
        video_ids: list[str] = []
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": 50,
            }
            if page_token:
                kwargs["pageToken"] = page_token
            resp = _retry(lambda: self._service.playlistItems().list(**kwargs).execute())
            items = resp.get("items", [])
            page_had_old = False
            for it in items:
                cd = it["contentDetails"]
                published_at = cd.get("videoPublishedAt")
                if published_at is None:
                    continue  # unpublished / scheduled
                if published_at >= since_iso:
                    video_ids.append(cd["videoId"])
                else:
                    page_had_old = True
            page_token = resp.get("nextPageToken")
            if not page_token or page_had_old:
                break
        return video_ids

    def get_video_stats(self, video_ids: list[str]) -> list[dict]:
        results: list[dict] = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            resp = _retry(
                lambda: self._service.videos()
                .list(part="statistics,snippet", id=",".join(batch))
                .execute()
            )
            results.extend(resp.get("items", []))
        return results
