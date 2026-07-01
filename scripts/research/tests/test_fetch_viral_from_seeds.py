"""End-to-end tests for the research script orchestration (API calls mocked)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.research.fetch_viral_from_seeds import main, run
from scripts.research.youtube_client import ChannelNotFound, QuotaExceeded, ResolvedChannel


def _make_client(resolved: list[ResolvedChannel] | Exception, uploads: list[str], stats: list[dict]) -> MagicMock:
    client = MagicMock()
    if isinstance(resolved, Exception):
        client.resolve_channel.side_effect = resolved
    else:
        client.resolve_channel.side_effect = resolved
    client.list_recent_uploads.return_value = uploads
    client.get_video_stats.return_value = stats
    return client


class TestRun:
    def test_writes_valid_json_with_expected_fields(self, tmp_path: Path) -> None:
        client = _make_client(
            resolved=[ResolvedChannel(input="@x", channel_id="UC_x", uploads_playlist_id="UU_x")],
            uploads=["v1"],
            stats=[
                {
                    "id": "v1",
                    "snippet": {
                        "channelId": "UC_x",
                        "title": "10 Secrets",
                        "publishedAt": "2026-06-14T00:00:00Z",
                        "thumbnails": {"high": {"url": "https://img/v1.jpg"}},
                    },
                    "statistics": {"viewCount": "421000"},
                }
            ],
        )
        out = tmp_path / "research.json"
        result = run(
            seeds=["@x"],
            defaults={
                "recency_days": 60,
                "min_views_per_day": 10000,
                "max_videos_per_channel": 5,
                "fetch_transcripts": True,
                "transcript_languages": ["en"],
            },
            api_key="dummy",
            out_path=out,
            client_factory=lambda k: client,
            transcript_fn=lambda vid, langs: ("hello world", "captions"),
            now=lambda: datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded == result
        assert loaded["params"]["recency_days"] == 60
        assert len(loaded["videos"]) == 1
        v = loaded["videos"][0]
        assert v["video_id"] == "v1"
        assert v["title"] == "10 Secrets"
        assert v["views"] == 421000
        # published 2026-06-14, now 2026-07-01 → 17 days
        assert v["days_since_publish"] == 17
        assert v["views_per_day"] == 421000 / 17
        assert v["transcript"] == "hello world"
        assert v["transcript_source"] == "captions"

    def test_channel_not_found_logged_in_errors(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.resolve_channel.side_effect = ChannelNotFound("no such channel")
        client.list_recent_uploads.return_value = []
        client.get_video_stats.return_value = []
        out = tmp_path / "research.json"
        run(
            seeds=["@bad"],
            defaults={
                "recency_days": 60,
                "min_views_per_day": 10000,
                "max_videos_per_channel": 5,
                "fetch_transcripts": False,
                "transcript_languages": ["en"],
            },
            api_key="dummy",
            out_path=out,
            client_factory=lambda k: client,
            transcript_fn=lambda vid, langs: (None, "none"),
            now=lambda: datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["videos"] == []
        assert loaded["errors"] == [{"channel_input": "@bad", "reason": "no such channel"}]
        assert loaded["channels"] == [{"input": "@bad", "channel_id": None, "resolved_ok": False}]

    def test_transcript_disabled_skips_fetch(self, tmp_path: Path) -> None:
        client = _make_client(
            resolved=[ResolvedChannel(input="@x", channel_id="UC_x", uploads_playlist_id="UU_x")],
            uploads=["v1"],
            stats=[
                {
                    "id": "v1",
                    "snippet": {
                        "channelId": "UC_x",
                        "title": "T",
                        "publishedAt": "2026-06-14T00:00:00Z",
                        "thumbnails": {"high": {"url": "https://img/v1.jpg"}},
                    },
                    "statistics": {"viewCount": "421000"},
                }
            ],
        )
        transcript_calls = []

        def fake_transcript(vid: str, langs: list[str]) -> tuple[str | None, str]:
            transcript_calls.append(vid)
            return ("x", "captions")

        out = tmp_path / "research.json"
        run(
            seeds=["@x"],
            defaults={
                "recency_days": 60,
                "min_views_per_day": 10000,
                "max_videos_per_channel": 5,
                "fetch_transcripts": False,
                "transcript_languages": ["en"],
            },
            api_key="dummy",
            out_path=out,
            client_factory=lambda k: client,
            transcript_fn=fake_transcript,
            now=lambda: datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert transcript_calls == []
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["videos"][0]["transcript"] is None
        assert loaded["videos"][0]["transcript_source"] == "none"

    def test_creates_output_directory_if_missing(self, tmp_path: Path) -> None:
        client = _make_client(
            resolved=[ResolvedChannel(input="@x", channel_id="UC_x", uploads_playlist_id="UU_x")],
            uploads=[],
            stats=[],
        )
        out = tmp_path / "deeply" / "nested" / "run-id" / "research.json"
        run(
            seeds=["@x"],
            defaults={
                "recency_days": 60,
                "min_views_per_day": 10000,
                "max_videos_per_channel": 5,
                "fetch_transcripts": False,
                "transcript_languages": ["en"],
            },
            api_key="dummy",
            out_path=out,
            client_factory=lambda k: client,
            transcript_fn=lambda v, l: (None, "none"),
            now=lambda: datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert out.exists()

    def test_quota_exceeded_propagates(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.resolve_channel.side_effect = [
            ResolvedChannel(input="@x", channel_id="UC_x", uploads_playlist_id="UU_x")
        ]
        client.list_recent_uploads.side_effect = QuotaExceeded("quota")
        out = tmp_path / "research.json"
        with pytest.raises(QuotaExceeded):
            run(
                seeds=["@x"],
                defaults={
                    "recency_days": 60,
                    "min_views_per_day": 10000,
                    "max_videos_per_channel": 5,
                    "fetch_transcripts": False,
                    "transcript_languages": ["en"],
                },
                api_key="dummy",
                out_path=out,
                client_factory=lambda k: client,
                transcript_fn=lambda v, l: (None, "none"),
                now=lambda: datetime(2026, 7, 1, tzinfo=timezone.utc),
            )


class TestMain:
    def _write_seeds(self, tmp_path: Path, *, active: bool) -> Path:
        seeds_path = tmp_path / "seed-channels.yaml"
        if active:
            seeds_path.write_text('channels:\n  - "@x"\n', encoding="utf-8")
        else:
            seeds_path.write_text(
                'channels:\n  # - "@examplechannel1"\n  # - "@examplechannel2"\n',
                encoding="utf-8",
            )
        return seeds_path

    def _write_defaults(self, tmp_path: Path) -> Path:
        defaults_path = tmp_path / "research-defaults.yaml"
        defaults_path.write_text(
            "recency_days: 60\n"
            "min_views_per_day: 10000\n"
            "max_videos_per_channel: 5\n"
            "fetch_transcripts: false\n"
            "transcript_languages:\n"
            "  - en\n",
            encoding="utf-8",
        )
        return defaults_path

    def test_main_exits_2_when_api_key_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seeds_path = self._write_seeds(tmp_path, active=True)
        defaults_path = self._write_defaults(tmp_path)
        out_path = tmp_path / "research.json"

        monkeypatch.setattr(
            "scripts.research.fetch_viral_from_seeds.load_dotenv", lambda *a, **k: None
        )
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "prog",
                "--seeds",
                str(seeds_path),
                "--defaults",
                str(defaults_path),
                "--out",
                str(out_path),
            ],
        )

        assert main() == 2

    def test_main_exits_2_when_no_channels_configured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seeds_path = self._write_seeds(tmp_path, active=False)
        defaults_path = self._write_defaults(tmp_path)
        out_path = tmp_path / "research.json"

        monkeypatch.setattr(
            "scripts.research.fetch_viral_from_seeds.load_dotenv", lambda *a, **k: None
        )
        monkeypatch.setenv("YOUTUBE_API_KEY", "dummy")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "prog",
                "--seeds",
                str(seeds_path),
                "--defaults",
                str(defaults_path),
                "--out",
                str(out_path),
            ],
        )

        assert main() == 2

    def test_main_exits_3_on_quota_exceeded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seeds_path = self._write_seeds(tmp_path, active=True)
        defaults_path = self._write_defaults(tmp_path)
        out_path = tmp_path / "research.json"

        monkeypatch.setattr(
            "scripts.research.fetch_viral_from_seeds.load_dotenv", lambda *a, **k: None
        )
        monkeypatch.setenv("YOUTUBE_API_KEY", "dummy")

        def _raise_quota(**kwargs):
            raise QuotaExceeded("quota")

        monkeypatch.setattr("scripts.research.fetch_viral_from_seeds.run", _raise_quota)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "prog",
                "--seeds",
                str(seeds_path),
                "--defaults",
                str(defaults_path),
                "--out",
                str(out_path),
            ],
        )

        assert main() == 3
