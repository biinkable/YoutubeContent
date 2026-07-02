# Project Shell + Research Subsystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project shell (dirs, config, skill scaffolding, git) plus a working Research subsystem: a Python CLI that mines user-supplied YouTube seed channels for their recent viral videos and emits a structured JSON, wrapped in a Claude Skill that Claude Code uses to interact with the user.

**Architecture:** Additive skill+scripts layout. Top-level `SKILL.md` orchestrates a growing set of per-subsystem sub-skills under `skills/`. Each subsystem has purpose-built scripts under `scripts/`. Research uses Python 3.11+, `google-api-python-client` for YouTube Data API v3, and `youtube-transcript-api` for captions. Configuration is user-editable YAML under `config/`; secrets are in `.env`. Each pipeline run produces `outputs/<run-id>/<artifact>.json`, easy to inspect and diff.

**Tech Stack:** Python 3.11+, google-api-python-client, youtube-transcript-api, PyYAML, python-dotenv, pytest. Windows 11 host. Bash tool available for git and script invocation.

## Global Constraints

- **Python:** 3.11+ minimum (uses `datetime.UTC`, `str.removeprefix`)
- **Runtime OS:** Windows 11; all file operations use `pathlib.Path` — no hardcoded `/` or `\`
- **Run ID format:** `YYYY-MM-DDTHH-MM-SS` (local time, colons replaced with hyphens for Windows filesystem safety)
- **Config format:** YAML for user-editable settings, `.env` for secrets
- **Output convention:** every stage writes to `outputs/<run-id>/<artifact>.json`
- **Test framework:** `pytest`; unit tests mock external APIs via `unittest.mock` (stdlib, no extra deps)
- **Git commits:** one per task; conventional commit prefixes (`feat:`, `test:`, `chore:`, `docs:`)
- **No secrets in git:** `.env` is gitignored; `.env.example` committed as template
- **YouTube API quota:** design must stay under 100 units per run for a typical 10-channel seed list

---

## File Structure

```
YoutubeContent/
├── .env.example                                        # committed template
├── .gitignore                                          # excludes .env, outputs/*, __pycache__
├── README.md                                           # setup + usage
├── SKILL.md                                            # top-level pipeline skill
├── config/
│   ├── seed-channels.yaml                              # user-editable seed list
│   └── research-defaults.yaml                          # user-editable knobs
├── skills/
│   └── research/
│       ├── SKILL.md                                    # research subsystem skill
│       └── references/
│           └── patterns.md                             # hook-pattern guidance for Claude
├── scripts/
│   └── research/
│       ├── __init__.py
│       ├── requirements.txt                            # pip deps
│       ├── channel_resolver.py                         # normalize @handle / URL / raw ID
│       ├── metrics.py                                  # views_per_day, threshold filter
│       ├── youtube_client.py                           # thin wrapper over Google API client
│       ├── transcript_fetcher.py                       # wrapper over youtube-transcript-api
│       ├── fetch_viral_from_seeds.py                   # CLI entrypoint
│       └── tests/
│           ├── __init__.py
│           ├── conftest.py                             # shared fixtures
│           ├── test_channel_resolver.py
│           ├── test_metrics.py
│           ├── test_youtube_client.py                  # mocked
│           ├── test_transcript_fetcher.py              # mocked
│           ├── test_fetch_viral_from_seeds.py          # mocked end-to-end
│           └── test_integration.py                     # real API, skipped w/o key
├── outputs/
│   └── .gitkeep                                        # so folder exists in git
└── docs/
    └── superpowers/
        ├── specs/2026-07-01-project-shell-and-research-subsystem-design.md   # exists
        └── plans/2026-07-01-project-shell-and-research-subsystem.md          # this file
```

**Module responsibilities:**
- `channel_resolver.py` — pure functions to detect and normalize any channel input format into either a channel ID or a handle (for the API call)
- `metrics.py` — pure functions for `views_per_day` computation and threshold+fallback filtering
- `youtube_client.py` — dependency-injectable wrapper over `googleapiclient.discovery.build(...)` with retry logic; single point of contact with the YouTube Data API
- `transcript_fetcher.py` — wrapper over `youtube_transcript_api` that always returns `(text_or_none, source_string)` — never raises to caller
- `fetch_viral_from_seeds.py` — CLI entrypoint; wires everything together, writes JSON

**Interface contract for downstream stages:** `outputs/<run-id>/research.json` matches the schema in Section 4.3 of the spec.

---

### Task 1: Project scaffolding — dirs, git, gitignore, .env template, README stub

**Files:**
- Create: `D:\Barry\AI Projects\YoutubeContent\.gitignore`
- Create: `D:\Barry\AI Projects\YoutubeContent\.env.example`
- Create: `D:\Barry\AI Projects\YoutubeContent\README.md`
- Create: `D:\Barry\AI Projects\YoutubeContent\outputs\.gitkeep`

**Interfaces:**
- Consumes: nothing
- Produces: a git-initialized project ready to accept further code

- [ ] **Step 1: Initialize git**

```bash
cd '/d/Barry/AI Projects/YoutubeContent'
git init -b main
```

Expected: `Initialized empty Git repository in D:/Barry/AI Projects/YoutubeContent/.git/`

- [ ] **Step 2: Create `.gitignore`**

Contents:

```
# Python
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
*.egg-info/

# Secrets
.env

# Per-run outputs — keep the folder but ignore contents
outputs/*
!outputs/.gitkeep

# OS / editor
.DS_Store
Thumbs.db
.vscode/
.idea/
```

- [ ] **Step 3: Create `.env.example`**

Contents:

```
# Copy this file to `.env` and fill in your keys. `.env` is gitignored.
# Get a key at https://console.cloud.google.com/ → enable "YouTube Data API v3" → Credentials → Create API key.
YOUTUBE_API_KEY=
```

- [ ] **Step 4: Create `outputs/.gitkeep`**

Empty file. Just needs to exist so the folder tracks in git.

- [ ] **Step 5: Create `README.md`**

Full content will land in Task 10. For this task, a one-line stub:

```markdown
# YoutubeContent

End-to-end YouTube video generator. See `docs/superpowers/specs/` for design and `docs/superpowers/plans/` for implementation plans.
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example README.md outputs/.gitkeep
git commit -m "chore: initialize project scaffolding"
```

Expected output: `[main (root-commit) ...] chore: initialize project scaffolding`

---

### Task 2: Config files — seed list and defaults

**Files:**
- Create: `config/seed-channels.yaml`
- Create: `config/research-defaults.yaml`

**Interfaces:**
- Consumes: nothing
- Produces: two YAML files loaded by `fetch_viral_from_seeds.py` and referenced by `skills/research/SKILL.md`

- [ ] **Step 1: Create `config/seed-channels.yaml`**

```yaml
# Add YouTube channels to mine for viral hits.
# Supports: @handles, full URLs, or raw channel IDs (starting with UC...).
# Edit this file freely — the research script reads it fresh every run.
channels:
  # - "@examplechannel1"
  # - "https://www.youtube.com/@examplechannel2"
  # - "UC_channelId_raw_starts_with_UC"
```

- [ ] **Step 2: Create `config/research-defaults.yaml`**

```yaml
# Default knobs for the research subsystem. Override per-run via CLI flags.
recency_days: 60             # only consider videos published in the last N days
min_views_per_day: 10000     # virality threshold; fallback = top 20% of channel's recent by views
max_videos_per_channel: 5    # cap so one hit-machine doesn't dominate the output
fetch_transcripts: true      # off = faster, less signal for downstream stages
transcript_languages:        # tried in order; first match wins
  - en
```

- [ ] **Step 3: Commit**

```bash
git add config/
git commit -m "chore: add seed-channels and research-defaults config"
```

---

### Task 3: Python package skeleton + requirements

**Files:**
- Create: `scripts/research/__init__.py` (empty)
- Create: `scripts/research/requirements.txt`
- Create: `scripts/research/tests/__init__.py` (empty)
- Create: `scripts/research/tests/conftest.py`

**Interfaces:**
- Consumes: nothing
- Produces: importable Python package `scripts.research`, dependencies installable via pip

- [ ] **Step 1: Create empty `__init__.py` files**

```bash
touch 'scripts/research/__init__.py' 'scripts/research/tests/__init__.py'
```

Note: on Windows via Git Bash, `touch` works. Alternatively create the files with your editor.

- [ ] **Step 2: Create `scripts/research/requirements.txt`**

```
google-api-python-client>=2.140.0
youtube-transcript-api>=0.6.2
PyYAML>=6.0.2
python-dotenv>=1.0.1
pytest>=8.3.0
```

- [ ] **Step 3: Create `scripts/research/tests/conftest.py`**

```python
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
```

- [ ] **Step 4: Install dependencies**

```bash
cd '/d/Barry/AI Projects/YoutubeContent'
python -m pip install -r scripts/research/requirements.txt
```

Expected: pip installs all packages without errors.

- [ ] **Step 5: Verify pytest discovers zero tests (empty test dir)**

```bash
cd '/d/Barry/AI Projects/YoutubeContent'
python -m pytest scripts/research/tests -v
```

Expected output ending with: `no tests ran in ...s` (this is success — pytest is working, just no tests yet).

- [ ] **Step 6: Commit**

```bash
git add scripts/research/__init__.py scripts/research/requirements.txt scripts/research/tests/__init__.py scripts/research/tests/conftest.py
git commit -m "chore: add python package skeleton and dependencies"
```

---

### Task 4: Channel resolver — normalize @handle / URL / raw ID

**Files:**
- Create: `scripts/research/channel_resolver.py`
- Create: `scripts/research/tests/test_channel_resolver.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `parse_channel_input(raw: str) -> ChannelInput` where `ChannelInput` is a dataclass with fields `kind: Literal["handle", "id", "url_handle", "url_id"]` and `value: str`
  - `normalize_for_api(parsed: ChannelInput) -> tuple[str, str]` returning `(param_name, param_value)` where `param_name` is one of `"id"`, `"forHandle"` — matches YouTube Data API `channels.list` params

- [ ] **Step 1: Write failing tests**

Create `scripts/research/tests/test_channel_resolver.py`:

```python
"""Tests for channel input parsing and normalization."""
from __future__ import annotations

import pytest

from scripts.research.channel_resolver import (
    ChannelInput,
    normalize_for_api,
    parse_channel_input,
)


class TestParseChannelInput:
    def test_bare_handle(self) -> None:
        result = parse_channel_input("@mrbeast")
        assert result == ChannelInput(kind="handle", value="@mrbeast")

    def test_raw_channel_id(self) -> None:
        result = parse_channel_input("UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert result == ChannelInput(kind="id", value="UCX6OQ3DkcsbYNE6H8uQQuVA")

    def test_url_with_handle(self) -> None:
        result = parse_channel_input("https://www.youtube.com/@mrbeast")
        assert result == ChannelInput(kind="url_handle", value="@mrbeast")

    def test_url_with_channel_id(self) -> None:
        result = parse_channel_input("https://www.youtube.com/channel/UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert result == ChannelInput(kind="url_id", value="UCX6OQ3DkcsbYNE6H8uQQuVA")

    def test_url_with_trailing_slash(self) -> None:
        result = parse_channel_input("https://www.youtube.com/@mrbeast/")
        assert result == ChannelInput(kind="url_handle", value="@mrbeast")

    def test_whitespace_is_stripped(self) -> None:
        result = parse_channel_input("  @mrbeast  ")
        assert result == ChannelInput(kind="handle", value="@mrbeast")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_channel_input("")

    def test_gibberish_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_channel_input("not-a-handle-or-url")


class TestNormalizeForApi:
    def test_handle_becomes_forhandle(self) -> None:
        ci = ChannelInput(kind="handle", value="@mrbeast")
        assert normalize_for_api(ci) == ("forHandle", "@mrbeast")

    def test_url_handle_becomes_forhandle(self) -> None:
        ci = ChannelInput(kind="url_handle", value="@mrbeast")
        assert normalize_for_api(ci) == ("forHandle", "@mrbeast")

    def test_id_becomes_id(self) -> None:
        ci = ChannelInput(kind="id", value="UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert normalize_for_api(ci) == ("id", "UCX6OQ3DkcsbYNE6H8uQQuVA")

    def test_url_id_becomes_id(self) -> None:
        ci = ChannelInput(kind="url_id", value="UCX6OQ3DkcsbYNE6H8uQQuVA")
        assert normalize_for_api(ci) == ("id", "UCX6OQ3DkcsbYNE6H8uQQuVA")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd '/d/Barry/AI Projects/YoutubeContent'
python -m pytest scripts/research/tests/test_channel_resolver.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.research.channel_resolver'`

- [ ] **Step 3: Implement `channel_resolver.py`**

Create `scripts/research/channel_resolver.py`:

```python
"""Parse and normalize YouTube channel inputs (handle / URL / raw ID)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ChannelKind = Literal["handle", "id", "url_handle", "url_id"]

_HANDLE_RE = re.compile(r"^@[\w.\-]{1,60}$")
_ID_RE = re.compile(r"^UC[\w\-]{22}$")
_URL_HANDLE_RE = re.compile(r"^https?://(?:www\.)?youtube\.com/(@[\w.\-]{1,60})/?$")
_URL_ID_RE = re.compile(r"^https?://(?:www\.)?youtube\.com/channel/(UC[\w\-]{22})/?$")


@dataclass(frozen=True)
class ChannelInput:
    kind: ChannelKind
    value: str


def parse_channel_input(raw: str) -> ChannelInput:
    """Detect the shape of a channel input string and normalize it.

    Raises ValueError if the input matches no known format.
    """
    if not isinstance(raw, str):
        raise ValueError(f"channel input must be a string, got {type(raw).__name__}")
    s = raw.strip()
    if not s:
        raise ValueError("channel input is empty")

    if m := _URL_HANDLE_RE.match(s):
        return ChannelInput(kind="url_handle", value=m.group(1))
    if m := _URL_ID_RE.match(s):
        return ChannelInput(kind="url_id", value=m.group(1))
    if _HANDLE_RE.match(s):
        return ChannelInput(kind="handle", value=s)
    if _ID_RE.match(s):
        return ChannelInput(kind="id", value=s)

    raise ValueError(
        f"unrecognized channel input: {raw!r}. "
        "expected @handle, UC-prefixed channel id, or a youtube.com URL."
    )


def normalize_for_api(parsed: ChannelInput) -> tuple[str, str]:
    """Return the (param_name, param_value) pair for the YouTube Data API channels.list call."""
    if parsed.kind in ("handle", "url_handle"):
        return ("forHandle", parsed.value)
    return ("id", parsed.value)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest scripts/research/tests/test_channel_resolver.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/research/channel_resolver.py scripts/research/tests/test_channel_resolver.py
git commit -m "feat(research): add channel input parser and API normalizer"
```

---

### Task 5: Metrics — views-per-day computation and threshold filter

**Files:**
- Create: `scripts/research/metrics.py`
- Create: `scripts/research/tests/test_metrics.py`

**Interfaces:**
- Consumes: nothing (pure functions over primitive types)
- Produces:
  - `views_per_day(views: int, days_since_publish: int) -> float`
  - `filter_viral(videos: list[dict], min_vps: float, max_per_channel: int, fallback_top_pct: float = 0.20) -> list[dict]` — returns a subset of `videos` (each dict must have keys `views_per_day: float`, `channel_id: str`, `views: int`); items with `views_per_day >= min_vps` win; if a channel has zero hits above threshold, its top `ceil(len(channel_videos) * fallback_top_pct)` by views are kept; then per-channel results are capped at `max_per_channel` (sorted by views_per_day descending)

- [ ] **Step 1: Write failing tests**

Create `scripts/research/tests/test_metrics.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest scripts/research/tests/test_metrics.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `metrics.py`**

Create `scripts/research/metrics.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest scripts/research/tests/test_metrics.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/research/metrics.py scripts/research/tests/test_metrics.py
git commit -m "feat(research): add views-per-day and viral filter helpers"
```

---

### Task 6: YouTube API client wrapper with retry

**Files:**
- Create: `scripts/research/youtube_client.py`
- Create: `scripts/research/tests/test_youtube_client.py`

**Interfaces:**
- Consumes: `parse_channel_input`, `normalize_for_api` from `channel_resolver`
- Produces:
  - `class YouTubeClient` with constructor `__init__(self, api_key: str, *, service=None)` — `service` param is for testing (inject a mock; if `None`, builds real service via `googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)`)
  - `resolve_channel(self, raw: str) -> ResolvedChannel` — returns dataclass with `input: str`, `channel_id: str`, `uploads_playlist_id: str`
  - `list_recent_uploads(self, uploads_playlist_id: str, since_iso: str) -> list[str]` — returns video IDs published on/after `since_iso` (ISO8601 UTC), walking playlist pages until oldest returned page falls entirely before cutoff
  - `get_video_stats(self, video_ids: list[str]) -> list[dict]` — batches up to 50 IDs per call; returns raw items from `videos.list` response (with `statistics` and `snippet` parts)
  - `class ChannelNotFound(Exception)`, `class QuotaExceeded(Exception)`

- [ ] **Step 1: Write failing tests**

Create `scripts/research/tests/test_youtube_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest scripts/research/tests/test_youtube_client.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `youtube_client.py`**

Create `scripts/research/youtube_client.py`:

```python
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
            page_had_recent = False
            for it in items:
                cd = it["contentDetails"]
                published_at = cd.get("videoPublishedAt")
                if published_at is None:
                    continue  # unpublished / scheduled
                if published_at >= since_iso:
                    video_ids.append(cd["videoId"])
                    page_had_recent = True
            page_token = resp.get("nextPageToken")
            if not page_token or not page_had_recent:
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest scripts/research/tests/test_youtube_client.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/research/youtube_client.py scripts/research/tests/test_youtube_client.py
git commit -m "feat(research): add YouTube Data API client wrapper with retry"
```

---

### Task 7: Transcript fetcher

**Files:**
- Create: `scripts/research/transcript_fetcher.py`
- Create: `scripts/research/tests/test_transcript_fetcher.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `fetch_transcript(video_id: str, languages: list[str], *, api=None) -> tuple[str | None, str]` — `api` param injects a mock in tests (must have `.get_transcript(video_id, languages=...)` returning a list of `{"text": str}` dicts, mirroring `youtube_transcript_api.YouTubeTranscriptApi`); returns `(text, "captions")` on success, `(None, "none")` on any failure (no captions, disabled, etc.); joins transcript segments with a space

- [ ] **Step 1: Write failing tests**

Create `scripts/research/tests/test_transcript_fetcher.py`:

```python
"""Tests for the transcript fetcher wrapper."""
from __future__ import annotations

from unittest.mock import MagicMock

from scripts.research.transcript_fetcher import fetch_transcript


class TestFetchTranscript:
    def test_success_returns_joined_text(self) -> None:
        api = MagicMock()
        api.get_transcript.return_value = [
            {"text": "hello"},
            {"text": "world"},
            {"text": "this is a test"},
        ]
        text, source = fetch_transcript("abc", ["en"], api=api)
        assert text == "hello world this is a test"
        assert source == "captions"
        api.get_transcript.assert_called_once_with("abc", languages=["en"])

    def test_failure_returns_none_none(self) -> None:
        api = MagicMock()
        api.get_transcript.side_effect = Exception("no transcript available")
        text, source = fetch_transcript("abc", ["en"], api=api)
        assert text is None
        assert source == "none"

    def test_empty_transcript_returns_empty_string_captions(self) -> None:
        # if the API returns an empty list, that's technically "captions present, empty"
        api = MagicMock()
        api.get_transcript.return_value = []
        text, source = fetch_transcript("abc", ["en"], api=api)
        assert text == ""
        assert source == "captions"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest scripts/research/tests/test_transcript_fetcher.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `transcript_fetcher.py`**

Create `scripts/research/transcript_fetcher.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest scripts/research/tests/test_transcript_fetcher.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/research/transcript_fetcher.py scripts/research/tests/test_transcript_fetcher.py
git commit -m "feat(research): add graceful transcript fetcher"
```

---

### Task 8: Main script — CLI entrypoint that wires everything

**Files:**
- Create: `scripts/research/fetch_viral_from_seeds.py`
- Create: `scripts/research/tests/test_fetch_viral_from_seeds.py`

**Interfaces:**
- Consumes: `YouTubeClient` (and its exceptions), `fetch_transcript`, `views_per_day`, `filter_viral`
- Produces:
  - Module-level `run(seeds: list[str], defaults: dict, api_key: str, out_path: Path, *, client_factory=None, transcript_fn=None, now=None) -> dict` — pure orchestration; returns the JSON dict that also gets written to disk; `client_factory` / `transcript_fn` / `now` are DI seams for tests
  - CLI entrypoint via `if __name__ == "__main__":` that parses args and calls `run(...)`
  - CLI flags: `--seeds`, `--defaults`, `--out` (all required), plus overrides `--recency-days`, `--min-views-per-day`, `--max-videos-per-channel`, `--no-transcripts`

- [ ] **Step 1: Write failing tests**

Create `scripts/research/tests/test_fetch_viral_from_seeds.py`:

```python
"""End-to-end tests for the research script orchestration (API calls mocked)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from scripts.research.fetch_viral_from_seeds import run
from scripts.research.youtube_client import ChannelNotFound, ResolvedChannel


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest scripts/research/tests/test_fetch_viral_from_seeds.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `fetch_viral_from_seeds.py`**

Create `scripts/research/fetch_viral_from_seeds.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest scripts/research/tests/test_fetch_viral_from_seeds.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite to check nothing regressed**

```bash
python -m pytest scripts/research/tests -v --ignore=scripts/research/tests/test_integration.py
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/research/fetch_viral_from_seeds.py scripts/research/tests/test_fetch_viral_from_seeds.py
git commit -m "feat(research): add CLI entrypoint and end-to-end orchestration"
```

---

### Task 9: Top-level pipeline skill and research subsystem skill

**Files:**
- Create: `SKILL.md`
- Create: `skills/research/SKILL.md`
- Create: `skills/research/references/patterns.md`

**Interfaces:**
- Consumes: everything from tasks 1–8 (Claude reads these skills and invokes the Python script)
- Produces: prompt-engineering artifacts that make Claude behave correctly when the user says "let's start a new video"

- [ ] **Step 1: Create top-level `SKILL.md`**

```markdown
---
name: youtubecontent-pipeline
description: Orchestrate a multi-stage YouTube video generator. Trigger when the user says any of "let's start a new video", "make a YouTube video", "spin off a video from my seeds", "run the video pipeline", "research my channels", or any phrase indicating they want to begin, resume, or manage a video-generation run. This skill is a router — it points at per-stage sub-skills under skills/<stage>/SKILL.md.
---

# YoutubeContent Pipeline

## Pipeline stages

The full pipeline is:

1. **Research** (implemented) — mine user's seed channels for recent viral videos.
2. Topic generation (not yet built)
3. Character-fork illustration skill (not yet built)
4. Script writing (not yet built)
5. TTS (not yet built)
6. Image generation (not yet built)
7. Video stitching (not yet built)

Stages run in order. Each stage's output lands in `outputs/<run-id>/` for the next stage to consume.

## How to use this skill

When the user asks to start a new video (or research their channels, or spin off from viral hits), your first action is:

1. Read `skills/research/SKILL.md` and follow its instructions.
2. When research completes and the user has picked videos, stop and tell them "topic generation isn't built yet — spec + plan for that comes in the next brainstorming cycle."

Do not attempt to invent stages that don't exist. Do not fabricate script/audio/image/video output.

## Run folders

Every pipeline run creates a folder `outputs/<run-id>/` where `<run-id>` is `YYYY-MM-DDTHH-MM-SS` (local time). All artifacts for that run live inside.
```

- [ ] **Step 2: Create `skills/research/SKILL.md`**

```markdown
---
name: youtube-research
description: Mine user-supplied YouTube seed channels for their recent viral videos. Use when the user says "let's start a new video", "find some viral hits to spin off", "research my seed channels", "check my channels for new hits", or any phrase that signals they want to pull fresh material from their tracked channels before generating a topic.
---

# YouTube Research (Stage 1)

## Purpose

Fetch recent viral videos from the user's seed channels, present them with hook analysis, and let the user pick 1–3 to hand off to the next stage.

## Prerequisites — check before running

1. `.env` exists in the project root and contains `YOUTUBE_API_KEY=<something non-empty>`. If missing, tell the user and point them at `.env.example` and the Google Cloud setup steps in `README.md`. Stop.
2. `config/seed-channels.yaml` has at least one non-commented entry under `channels:`. If empty, ask the user for at least one channel handle/URL/ID and offer to add them to the file.

## Steps

### 1. Show the user their current setup

Read `config/seed-channels.yaml` and `config/research-defaults.yaml`. Show the user:
- The list of seed channels (numbered).
- The current defaults (recency window, view threshold, max videos per channel, transcripts on/off).

Ask whether they want to run with these settings or change anything for this run. Common overrides:
- Add/remove a seed channel (edit the YAML).
- Shorten/lengthen recency window.
- Lower the views-per-day threshold (they may want more results).

### 2. Generate a run ID and create the run folder

Format: `YYYY-MM-DDTHH-MM-SS` in local time. Use `date "+%Y-%m-%dT%H-%M-%S"` via Bash (POSIX) or the equivalent in PowerShell. Create `outputs/<run-id>/` with `mkdir -p`.

### 3. Run the research script

Invoke via Bash:

    python scripts/research/fetch_viral_from_seeds.py \
      --seeds config/seed-channels.yaml \
      --defaults config/research-defaults.yaml \
      --out outputs/<run-id>/research.json

Append per-flag overrides only if the user changed something:
- `--recency-days N`
- `--min-views-per-day N`
- `--max-videos-per-channel N`
- `--no-transcripts`

If the script exits non-zero, surface stderr verbatim to the user and stop. Do not proceed to step 4.

### 4. Read the output and analyze

Read `outputs/<run-id>/research.json`. If `videos` is empty:
- Explain what happened using the `errors` array.
- Offer to lower the threshold or widen the recency window and re-run.
- Stop.

Otherwise, read `skills/research/references/patterns.md` and use it to characterize each video's hook.

Present the results as:

1. **Summary table:** one row per video with columns: channel · title · views · views/day · has-transcript.
2. **Per-video analysis (grouped by channel):** for each video, a 2–3 sentence hook analysis referencing the patterns from `patterns.md`. Quote the video title and the first 1–2 sentences of the transcript if available.
3. **Cross-cutting observations:** if you notice patterns across channels (e.g. "3 of the 5 hits are numeric listicles"), call them out.

### 5. Ask the user to pick

Ask which 1–3 videos they want to spin off in the topic-generation stage. Let them respond by number, title, or "the mrbeast one about X." If unclear, ask for clarification.

### 6. Save the selection

Write `outputs/<run-id>/picked_videos.json`:

```json
{
  "run_id": "<same as research.json>",
  "picked_at": "<ISO8601 UTC>",
  "picked": [ /* subset of research.json's videos array */ ]
}
```

### 7. Hand off

Tell the user: "Stage 1 complete. Picked videos saved to `outputs/<run-id>/picked_videos.json`. The topic-generation stage isn't built yet — the spec and plan for it come in the next brainstorming cycle."

## Failure modes

- **Missing API key:** stop at step 0, point at `.env.example`.
- **Quota exceeded (exit code 3):** tell the user, note that the quota resets at midnight Pacific.
- **Handle unresolvable:** it will appear in the `errors` array in the JSON; explain in step 4.
- **All transcripts missing:** proceed anyway; hook analysis works from titles alone (just noisier).
- **No videos pass filter for any channel:** the fallback kicks in automatically (top 20% of each channel by views); if still zero videos, most likely all channels have zero uploads in the recency window — suggest widening it.
```

- [ ] **Step 3: Create `skills/research/references/patterns.md`**

```markdown
# Viral Hook Patterns

Guidance for characterizing the "hook" of a viral YouTube video from its title (and optionally its transcript intro). Use this when analyzing videos returned by the research script in step 4 of the research skill.

Not every video fits one pattern cleanly. Note the closest match plus any secondary flavor. The goal is to give the user useful raw material for topic generation, not to pigeonhole every hit.

## 1. Numeric listicle
- **Shape:** "N [things] you [never/didn't/should]..."
- **Examples:** "10 Secrets of the Universe Nobody's Heard Of", "7 Weird Things That Only Happen at Night"
- **Why it works:** the number promises finite, digestible content; the negative claim ("never heard") triggers curiosity.
- **Transcript tell:** intro often opens with "In this video I'm going to show you N..."

## 2. Curiosity-gap "what if" / "the reason"
- **Shape:** "What if X..." / "The real reason X" / "Why X actually Y"
- **Examples:** "What If the Sun Disappeared for 7 Seconds?", "The Real Reason Rome Actually Fell"
- **Why it works:** creates an information gap between what the viewer expects and what the video will reveal.
- **Transcript tell:** intro reframes something familiar as unfamiliar in the first ~30 seconds.

## 3. Secret reveal / hidden knowledge
- **Shape:** "Nobody told you..." / "The hidden X" / "What they don't want you to know"
- **Examples:** "The Hidden History of the Word 'OK'", "What They Don't Teach You About Sleep"
- **Why it works:** implies insider access to knowledge others lack.
- **Transcript tell:** often opens with a normalized fact being upended.

## 4. Contrarian claim
- **Shape:** "You've been doing X wrong" / "X is a lie" / "Actually, X"
- **Examples:** "You've Been Making Coffee Wrong Your Whole Life", "Everything You Know About Sharks Is Wrong"
- **Why it works:** challenges the viewer's identity/beliefs in a low-stakes way.
- **Transcript tell:** intro asserts the widespread wrong belief, then teases the reveal.

## 5. Question hook
- **Shape:** "Why do X..." / "Have you ever wondered..."
- **Examples:** "Why Do We Yawn?", "Have You Ever Wondered Why Airplane Windows Are Round?"
- **Why it works:** invites the viewer to notice they don't know the answer.
- **Transcript tell:** intro restates the question and promises to answer it.

## 6. Time-scoped stakes
- **Shape:** "In the next X seconds/minutes..." / "By the time you finish this video..."
- **Examples:** "By the End of This Video You'll Never Look at Money the Same Way"
- **Why it works:** creates a payoff commitment the viewer wants to see fulfilled.
- **Transcript tell:** intro often references time explicitly ("stick with me for 8 minutes").

## 7. Superlative / extremes
- **Shape:** "The most/least/first/only X" / "Ever" / "In history"
- **Examples:** "The Most Dangerous Animal You've Never Heard Of", "The First Person to Ever..."
- **Why it works:** the extreme framing raises stakes; ranks something.
- **Transcript tell:** intro often justifies the superlative claim upfront.

## Analysis output format

For each video, write 2–3 sentences covering:
- Which pattern(s) it matches
- Why it likely worked (what specific curiosity/tension it triggers)
- Anything transferable to a new topic (e.g. "the '10 secrets' frame here could be reapplied to any obscure-knowledge topic")
```

- [ ] **Step 4: Commit**

```bash
git add SKILL.md skills/
git commit -m "feat: add top-level pipeline and research subsystem skills"
```

---

### Task 10: Full README with setup instructions

**Files:**
- Modify: `README.md` (replace the one-line stub with the full doc)

**Interfaces:**
- Consumes: everything from tasks 1–9 (documents them for the user)
- Produces: user-facing setup and usage instructions

- [ ] **Step 1: Replace `README.md` with full content**

Overwrite `README.md`:

```markdown
# YoutubeContent

End-to-end YouTube video generator. From inside a Claude Code session, this project mines your chosen YouTube channels for viral hits, spins off new video concepts, writes narrator scripts, generates styled slideshow imagery, produces voiceovers, and stitches everything into a finished .mp4.

**Current status:** Stage 1 (research) is built. Stages 2–7 (topic generation, character-fork illustration, script writing, TTS, image generation, video stitching) are planned but not yet implemented. See `docs/superpowers/specs/` for the roadmap.

---

## One-time setup

### 1. Install Python 3.11+

Verify:

    python --version

If below 3.11, install from python.org or via winget: `winget install Python.Python.3.12`.

### 2. Install dependencies

From the project root:

    python -m pip install -r scripts/research/requirements.txt

### 3. Get a YouTube Data API key

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (name it whatever you like).
3. In the sidebar → "APIs & Services" → "Library" → search for "YouTube Data API v3" → click "Enable".
4. Sidebar → "APIs & Services" → "Credentials" → "Create Credentials" → "API key". Copy the key.
5. Copy `.env.example` to `.env` and paste your key:

        cp .env.example .env
        # then edit .env with your favorite editor

**No billing required.** Free daily quota is 10,000 units; a typical run uses ~25 units.

### 4. Add your seed channels

Edit `config/seed-channels.yaml` and add YouTube channels you want to mine. Supports:
- Handles: `@mrbeast`
- URLs: `https://www.youtube.com/@mrbeast`
- Raw channel IDs: `UCX6OQ3DkcsbYNE6H8uQQuVA`

### 5. (Optional) Tweak defaults

`config/research-defaults.yaml` controls the recency window, virality threshold, and per-channel cap. Defaults are usually fine.

---

## Using the tool

Open a Claude Code session in the project directory (`D:\Barry\AI Projects\YoutubeContent`) and say:

> let's start a new video

Claude will read this project's `SKILL.md`, follow the research subsystem's skill, run the Python script, and walk you through the results.

---

## Project layout

- `SKILL.md` — top-level pipeline skill (router)
- `skills/<stage>/SKILL.md` — per-stage skills (research is built; others coming)
- `scripts/<stage>/` — Python (or Node) code for each stage
- `config/` — user-editable YAML settings
- `outputs/<run-id>/` — one folder per pipeline run, all artifacts inside
- `docs/superpowers/specs/` — approved designs
- `docs/superpowers/plans/` — implementation plans

---

## Running tests

    python -m pytest scripts/research/tests -v --ignore=scripts/research/tests/test_integration.py

To include the real-API integration test (needs a live YOUTUBE_API_KEY):

    python -m pytest scripts/research/tests -v
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add full README with setup and usage"
```

---

### Task 11: Integration test — real YouTube API against a known channel

**Files:**
- Create: `scripts/research/tests/test_integration.py`

**Interfaces:**
- Consumes: the whole subsystem end-to-end
- Produces: an integration test that skips gracefully without a live API key

- [ ] **Step 1: Create the integration test**

Create `scripts/research/tests/test_integration.py`:

```python
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
```

- [ ] **Step 2: Run the test with a real API key to verify it works**

```bash
python -m pytest scripts/research/tests/test_integration.py -v
```

Expected outcome:
- If `YOUTUBE_API_KEY` is set, the test PASSES against the live API (uses ~4 quota units).
- If `YOUTUBE_API_KEY` is not set, the test is SKIPPED.

- [ ] **Step 3: Run the full test suite (including integration)**

```bash
python -m pytest scripts/research/tests -v
```

Expected: all tests PASS (or integration SKIPPED if no key).

- [ ] **Step 4: Commit**

```bash
git add scripts/research/tests/test_integration.py
git commit -m "test(research): add live-API integration test (skipped without key)"
```

---

### Task 12: Smoke test — end-to-end run from a fresh Claude Code session

**Files:**
- None (verification only)

**Interfaces:**
- Consumes: everything built above
- Produces: confidence that the tool works from a user's perspective

This task is verification, not code. It confirms the whole shell works when a fresh Claude Code session drives it. Only mark it complete after you've observed the behavior described below.

- [ ] **Step 1: Prepare the environment**

Ensure `.env` has a valid `YOUTUBE_API_KEY` and `config/seed-channels.yaml` has at least one non-commented channel (e.g. `- "@YouTubeCreators"` for the smoke test).

- [ ] **Step 2: Open a fresh Claude Code session in the project directory**

```bash
cd '/d/Barry/AI Projects/YoutubeContent'
claude
```

- [ ] **Step 3: Trigger the pipeline**

Type into the session:

> let's start a new video

- [ ] **Step 4: Observe expected behavior**

Claude should:
1. Read the top-level `SKILL.md`.
2. Read `skills/research/SKILL.md`.
3. Show the user their seed channels and defaults.
4. Ask whether to proceed or change settings.
5. Once confirmed, generate a run ID, create `outputs/<run-id>/`, and invoke the Python script via Bash.
6. Read the resulting `research.json` and present a summary table + per-video hook analysis.
7. Ask the user to pick 1–3 videos.
8. On pick, save `outputs/<run-id>/picked_videos.json` and tell the user stage 2 isn't built yet.

- [ ] **Step 5: If the smoke test passes, commit no code but note completion**

Nothing to commit for this task. Move on to closing out.

---

## Self-Review Notes

Ran the self-review checklist against the spec:

1. **Spec coverage:**
   - Spec §3 (architecture) → Tasks 1, 2, 3, 9 (dirs, config, package skeleton, skills).
   - Spec §4.1 (config files) → Task 2.
   - Spec §4.2 (main script) → Tasks 6, 7, 8.
   - Spec §4.3 (output schema) → Task 8 tests assert on it.
   - Spec §4.4 (research skill) → Task 9.
   - Spec §4.5 (patterns reference) → Task 9.
   - Spec §4.6 (top-level skill) → Task 9.
   - Spec §5 (data flow) → Task 9 skill instructions + Task 12 smoke test.
   - Spec §6 (error handling) → Task 6 (quota + retry), Task 7 (transcript failure), Task 8 (channel-not-found handling), Task 9 skill (surface errors to user).
   - Spec §7 (testing) → Tasks 4, 5, 6, 7, 8 (unit), Task 11 (integration), Task 12 (manual smoke).
   - Spec §8 (setup steps in README) → Task 10.

2. **Placeholder scan:** No TBD/TODO/"handle edge cases" phrases. Every code block is complete.

3. **Type consistency:** `ResolvedChannel` used identically in tasks 6 and 8; `filter_viral` signature matches between tasks 5 and 8; `fetch_transcript` return type matches between tasks 7 and 8. `_iso_z`/`_run_id` helpers only used internally in task 8.
