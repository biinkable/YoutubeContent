"""Tests for the YouTube API client wrapper. All API calls mocked."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.research.youtube_client import (
    ChannelNotFound,
    QuotaExceeded,
    ResolvedChannel,
    YouTubeClient,
)


def _mock_service_for_channel(channel_id: str = "UC_test", uploads: str = "UU_test") -> MagicMock:
    """Build a mock googleapiclient service that returns a single channel."""
    svc = MagicMock()
    svc.channels.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": channel_id,
                "contentDetails": {"relatedPlaylists": {"uploads": uploads}},
            }
        ]
    }
    return svc


class TestResolveChannel:
    def test_resolves_handle(self) -> None:
        svc = _mock_service_for_channel()
        client = YouTubeClient("k", service=svc)
        result = client.resolve_channel("@mrbeast")
        assert result == ResolvedChannel(
            input="@mrbeast", channel_id="UC_test", uploads_playlist_id="UU_test"
        )
        # verify API called with forHandle param
        call = svc.channels.return_value.list.call_args
        assert call.kwargs["forHandle"] == "@mrbeast"
        assert "id" in call.kwargs["part"]
        assert "contentDetails" in call.kwargs["part"]

    def test_resolves_raw_id(self) -> None:
        svc = _mock_service_for_channel()
        client = YouTubeClient("k", service=svc)
        client.resolve_channel("UCX6OQ3DkcsbYNE6H8uQQuVA")
        call = svc.channels.return_value.list.call_args
        assert call.kwargs["id"] == "UCX6OQ3DkcsbYNE6H8uQQuVA"

    def test_channel_not_found_raises(self) -> None:
        svc = MagicMock()
        svc.channels.return_value.list.return_value.execute.return_value = {"items": []}
        client = YouTubeClient("k", service=svc)
        with pytest.raises(ChannelNotFound):
            client.resolve_channel("@nonexistent")


class TestListRecentUploads:
    def test_single_page_all_recent(self) -> None:
        svc = MagicMock()
        svc.playlistItems.return_value.list.return_value.execute.return_value = {
            "items": [
                {"contentDetails": {"videoId": "v1", "videoPublishedAt": "2026-06-20T00:00:00Z"}},
                {"contentDetails": {"videoId": "v2", "videoPublishedAt": "2026-06-15T00:00:00Z"}},
            ]
        }
        client = YouTubeClient("k", service=svc)
        result = client.list_recent_uploads("UU_test", "2026-06-01T00:00:00Z")
        assert result == ["v1", "v2"]

    def test_stops_walking_after_page_of_old_videos(self) -> None:
        svc = MagicMock()
        # first page has one recent, one old; second page would be all old but shouldn't be requested
        page1 = {
            "items": [
                {"contentDetails": {"videoId": "v1", "videoPublishedAt": "2026-06-20T00:00:00Z"}},
                {"contentDetails": {"videoId": "v2", "videoPublishedAt": "2026-05-15T00:00:00Z"}},
            ],
            "nextPageToken": "PAGE2",
        }
        svc.playlistItems.return_value.list.return_value.execute.return_value = page1
        client = YouTubeClient("k", service=svc)
        result = client.list_recent_uploads("UU_test", "2026-06-01T00:00:00Z")
        assert result == ["v1"]

    def test_walks_multiple_pages_when_all_recent(self) -> None:
        svc = MagicMock()
        page1 = {
            "items": [
                {"contentDetails": {"videoId": "v1", "videoPublishedAt": "2026-06-20T00:00:00Z"}},
            ],
            "nextPageToken": "PAGE2",
        }
        page2 = {
            "items": [
                {"contentDetails": {"videoId": "v2", "videoPublishedAt": "2026-06-10T00:00:00Z"}},
            ]
        }
        svc.playlistItems.return_value.list.return_value.execute.side_effect = [page1, page2]
        client = YouTubeClient("k", service=svc)
        result = client.list_recent_uploads("UU_test", "2026-06-01T00:00:00Z")
        assert result == ["v1", "v2"]


class TestGetVideoStats:
    def test_batches_up_to_50(self, sample_video_stats: dict) -> None:
        svc = MagicMock()
        svc.videos.return_value.list.return_value.execute.return_value = sample_video_stats
        client = YouTubeClient("k", service=svc)
        result = client.get_video_stats(["abc123"])
        assert len(result) == 1
        assert result[0]["id"] == "abc123"
        call = svc.videos.return_value.list.call_args
        assert call.kwargs["id"] == "abc123"

    def test_splits_large_batches(self) -> None:
        svc = MagicMock()
        # 75 IDs -> 2 calls (50 + 25)
        svc.videos.return_value.list.return_value.execute.side_effect = [
            {"items": [{"id": f"v{i}"} for i in range(50)]},
            {"items": [{"id": f"v{i}"} for i in range(50, 75)]},
        ]
        client = YouTubeClient("k", service=svc)
        result = client.get_video_stats([f"v{i}" for i in range(75)])
        assert len(result) == 75
        assert svc.videos.return_value.list.return_value.execute.call_count == 2


class TestQuotaError:
    def test_quota_exceeded_maps_to_specific_exception(self) -> None:
        from googleapiclient.errors import HttpError

        svc = MagicMock()
        # simulate a 403 quotaExceeded HttpError
        resp = MagicMock(status=403, reason="Forbidden")
        err = HttpError(
            resp=resp,
            content=b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}',
        )
        svc.channels.return_value.list.return_value.execute.side_effect = err
        client = YouTubeClient("k", service=svc)
        with pytest.raises(QuotaExceeded):
            client.resolve_channel("@x")
