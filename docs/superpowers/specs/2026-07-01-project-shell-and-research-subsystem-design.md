# Project Shell + Research Subsystem — Design

**Date:** 2026-07-01
**Status:** Draft, pending user review
**Scope:** First deliverable of the YoutubeContent project. Establishes the project shell (directory layout, skill pattern, config conventions, output conventions) that all six subsystems will drop into, and implements the first subsystem: **Research**. Subsequent subsystems (topic generation, character-fork, script, TTS, image generation, video stitching) will each be brainstormed and specced separately.

---

## 1. Goal

Give the user a working first slice of the YoutubeContent pipeline: from inside a Claude session in the project directory, they can say *"let's start a new video"* and Claude will:

1. Confirm a list of user-supplied seed YouTube channels
2. Fetch each channel's recent viral videos (title, metadata, transcript) via the YouTube Data API
3. Present a per-video summary with a first-pass hook analysis
4. Ask the user to pick 1–3 videos to spin off in the next stage (topic generation, to be built in a later cycle)
5. Save the user's selection to disk for the next stage to consume

The design also establishes the shell that every future subsystem will slot into with no restructuring.

---

## 2. Non-goals

- Automated channel discovery, ranking, or monetization inference (user manually supplies seeds)
- Full pipeline automation — the human-in-the-loop model is deliberate
- Video generation, TTS, image generation — future subsystems, out of scope for this spec
- A custom web/desktop UI — Claude sessions are the review surface
- Multi-user, cloud, or hosted deployment — this is a solo local tool

---

## 3. Architecture

### 3.1 Directory layout

```
YoutubeContent/
├── SKILL.md                          # top-level pipeline orchestrator
├── skills/
│   └── research/
│       ├── SKILL.md                  # how Claude runs + reviews research with user
│       └── references/
│           └── patterns.md           # hook-pattern analysis guidance
├── scripts/
│   └── research/
│       ├── fetch_viral_from_seeds.py # the actual data-fetch script
│       └── requirements.txt          # Python deps
├── config/
│   ├── seed-channels.yaml            # user's list of channel handles/URLs/IDs
│   └── research-defaults.yaml        # recency window, velocity threshold, caps
├── .env                              # YOUTUBE_API_KEY (gitignored)
├── .env.example                      # template committed to git
├── outputs/
│   └── <run-id>/                     # one folder per pipeline run
│       ├── research.json             # research subsystem output
│       └── picked_videos.json        # user selection, handoff to topic-gen
├── docs/
│   └── superpowers/
│       └── specs/                    # design docs (this file lives here)
├── .gitignore
└── README.md
```

### 3.2 Key architectural properties

- **Additive by design.** Each new subsystem is a new `skills/<name>/` + `scripts/<name>/`. No restructuring required as the project grows to include topic-gen, character-fork, script, TTS, image-gen, video-stitch.
- **Runtime-mixed on purpose.** Python for the research subsystem (mature YouTube libraries: `google-api-python-client`, `youtube-transcript-api`). Later subsystems pick their runtime per fit (Node for Remotion, Python for other data steps). Claude glues them via Bash.
- **Every run is a folder.** `outputs/<run-id>/` accumulates artifacts stage by stage — research.json, picked_videos.json, and later script.md, audio.mp3, images/, video.mp4. Easy to inspect, resume, and compare runs. Run ID format: `YYYY-MM-DDTHH-MM-SS` (local time, filesystem-safe).
- **Config is user-editable YAML.** Secrets are in `.env`. No hidden defaults buried in code — every knob lives in `config/`.
- **Skill-based orchestration.** Follows the same pattern as `ian-xiaohei-illustrations`: a top-level `SKILL.md` plus per-subsystem sub-skills that Claude reads on demand. Skill files are prompt engineering, not code.

### 3.3 Runtime choice for research: Python

Chosen because:

- `google-api-python-client` is the most mature YouTube Data API SDK
- `youtube-transcript-api` is the dominant caption-scraping library and has no reliable Node equivalent
- Data-processing ergonomics are better in Python for this shape of work

Node will be used later for Remotion (video stitching). Both runtimes are managed via Claude's Bash tool.

---

## 4. Research subsystem components

### 4.1 Config files

**`config/seed-channels.yaml`** — user-editable list of channels to mine. Supports handles (`@channelname`), full URLs, or raw channel IDs. Comments encouraged.

```yaml
channels:
  - "@examplechannel1"
  - "https://www.youtube.com/@examplechannel2"
  - "UC_channelId_raw"
```

**`config/research-defaults.yaml`** — knobs with sane defaults, all user-overridable per run:

```yaml
recency_days: 60
min_views_per_day: 10000
max_videos_per_channel: 5
fetch_transcripts: true
transcript_languages: ["en"]
```

**`.env`** — secret. `.env.example` is committed for reference:

```
YOUTUBE_API_KEY=your_key_here
```

### 4.2 Script: `scripts/research/fetch_viral_from_seeds.py`

**Args:** `--seeds config/seed-channels.yaml --defaults config/research-defaults.yaml --out outputs/<run-id>/research.json` (with per-flag overrides for each default).

**Behavior:**

1. Resolve each seed entry to a channel ID via `channels.list` (`part=id,contentDetails`). Handles are resolved via the API's `forHandle` param.
2. For each channel, walk its uploads playlist (from `contentDetails.relatedPlaylists.uploads`) via `playlistItems.list` (50 items per page, 1 quota unit per page) back until publish date is older than `recency_days`.
3. Batch-fetch statistics via `videos.list` (`part=statistics,snippet`, up to 50 IDs per call, 1 unit per call).
4. Compute `views_per_day = views / max(1, days_since_publish)`.
5. Filter: keep videos with `views_per_day >= min_views_per_day`. If a channel yields zero hits, fall back to top 20% of that channel's recent-window videos by view count.
6. Cap at `max_videos_per_channel`.
7. For each kept video, fetch transcript via `youtube-transcript-api` if `fetch_transcripts: true`. On failure (video has no captions, disabled, or unsupported language), mark `transcript_source: "none"` and continue.
8. Write JSON to the specified output path.

**Quota expectations per run** (10 seed channels, default params):
- 10 handle-to-ID resolutions: 10 units
- 10 uploads-playlist page fetches: ~10 units
- 1–3 `videos.list` batches: ~3 units
- **Total: ~25 units per run**. Free daily quota is 10,000 units → ~400 runs/day free.

### 4.3 Output schema: `research.json`

```json
{
  "run_id": "2026-07-01T13-45-00",
  "generated_at": "2026-07-01T13:45:00Z",
  "params": {
    "recency_days": 60,
    "min_views_per_day": 10000,
    "max_videos_per_channel": 5,
    "fetch_transcripts": true,
    "transcript_languages": ["en"]
  },
  "channels": [
    { "input": "@x", "channel_id": "UC...", "resolved_ok": true }
  ],
  "videos": [
    {
      "channel_input": "@x",
      "channel_id": "UC...",
      "video_id": "abc123",
      "title": "10 Secrets of the Universe Nobody Has Ever Heard",
      "url": "https://youtube.com/watch?v=abc123",
      "thumbnail_url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
      "published_at": "2026-06-14T09:00:00Z",
      "days_since_publish": 17,
      "views": 421000,
      "views_per_day": 24764,
      "transcript": "welcome back to the channel today we're...",
      "transcript_source": "captions"
    }
  ],
  "errors": [
    { "channel_input": "@bad", "reason": "channel not found" },
    { "video_id": "def456", "reason": "transcripts disabled" }
  ]
}
```

### 4.4 Skill: `skills/research/SKILL.md`

Frontmatter:

```yaml
---
name: youtube-research
description: Mine user-supplied YouTube seed channels for their recent viral videos. Use when the user says "let's start a new video", "find some viral hits to spin off", "research my seed channels", or any phrase that signals they want to pull fresh material from their tracked channels before generating a topic.
---
```

Body instructs Claude to:

1. Read `config/seed-channels.yaml` and confirm the list with the user (offer to add/remove/replace).
2. Read `config/research-defaults.yaml` and confirm params (offer overrides for this run).
3. Generate a run ID (`YYYY-MM-DDTHH-MM-SS`), create `outputs/<run-id>/`.
4. Run the Python script via Bash. Surface any error to the user with the exact command that failed.
5. Read `outputs/<run-id>/research.json`. If it's empty or all errors, explain what went wrong and offer to adjust params.
6. Read `skills/research/references/patterns.md` and use it to analyze hook patterns. Present a summary table (one row per video: channel · title · views/day · has-transcript) followed by a per-video first-pass hook analysis.
7. Ask the user to pick 1–3 videos to hand off to the topic-gen stage (they can also request a re-run with different params).
8. Save the selection as `outputs/<run-id>/picked_videos.json` — a subset of the `videos` array from step 5, plus the run_id.

### 4.5 Reference: `skills/research/references/patterns.md`

Guidance for Claude on how to describe hook patterns across the returned videos. Text guide, not code. Analogous to `style-dna.md` in the Xiaohei repo. Covers:

- Numeric listicle hooks ("10 X you didn't know")
- Curiosity-gap hooks ("what if…", "the reason X")
- Secret-reveal hooks ("nobody told you", "hidden")
- Contrarian claims ("you've been doing X wrong")
- Question-and-answer hooks
- Time-scoped hooks ("in the next 30 seconds")

For each pattern, guidance on identifying it in a title, common transcript intros, and what makes it work.

### 4.6 Top-level `SKILL.md`

Frontmatter names the project skill `youtubecontent-pipeline` with a description explaining it orchestrates a multi-stage video generation pipeline. Body is a short table of contents pointing Claude at `skills/<subsystem>/SKILL.md` for each stage, and a note that stages run in order: research → topic → script → tts → images → video. For this first spec only `skills/research/` exists; the others get added when their subsystems are built.

---

## 5. Data flow

1. User opens a Claude session in `D:\Barry\AI Projects\YoutubeContent` and says *"let's start a new video"* (or similar).
2. Claude reads top-level `SKILL.md`, sees research is stage 1, reads `skills/research/SKILL.md`.
3. Claude confirms seed list + params with user (via chat).
4. Claude generates a run ID and creates `outputs/<run-id>/`.
5. Claude runs `python scripts/research/fetch_viral_from_seeds.py --seeds config/seed-channels.yaml --defaults config/research-defaults.yaml --out outputs/<run-id>/research.json` in Bash. Overrides passed as flags if user changed params.
6. Script writes `research.json`.
7. Claude reads the JSON, uses `references/patterns.md` to analyze hooks, presents a summary + analysis in chat.
8. User picks 1–3 videos.
9. Claude writes `outputs/<run-id>/picked_videos.json`.
10. End of stage. (Next stage, topic-gen, is out of scope for this spec.)

---

## 6. Error handling

- **Missing YouTube API key.** Script exits with a clear message pointing at `.env.example`; Claude surfaces this and links the user to the Google Cloud setup steps in the README.
- **Quota exhausted (HTTP 403 with `quotaExceeded`).** Script exits with a message showing units consumed this run; Claude surfaces it and suggests waiting until quota reset (midnight Pacific) or requesting a quota increase.
- **Transient API failures (5xx, network).** Retry up to 3 times with exponential backoff (1s, 3s, 9s).
- **Handle unresolvable.** Log to `errors[]` in output, continue with remaining channels.
- **No videos matching threshold in a channel.** Fall back to top-20% by view count within recency window (per §4.2). If still zero, log to `errors[]` and continue.
- **Transcript unavailable** (no captions, disabled, unsupported language). Log to `errors[]`; keep the video with `transcript: null`, `transcript_source: "none"`. Downstream stages can still work from title + metadata.
- **Empty final output** (zero channels resolved, zero videos found). Script still writes a valid JSON with empty `videos` array + populated `errors`. Skill instructs Claude to explain the situation and offer to adjust params.

---

## 7. Testing

- **Unit tests** (`scripts/research/tests/`) for pure-logic pieces: velocity computation, threshold filter, handle detection, run-ID formatting. Use `pytest`.
- **Integration test.** Runs the script against a known stable channel (e.g. `@YouTubeCreators`) with a real API key from an env var; asserts the output JSON parses, has `videos`, and each video has required fields. Skipped in CI if no key present.
- **Manual smoke test.** After first setup, user runs the skill inside a Claude session against their real seed list; verifies Claude presents a useful summary.
- No tests for the skill/reference Markdown files (they are prompts, not code).

---

## 8. Setup steps (to be documented in README)

1. Install Python 3.11+ (existing on Windows or via winget)
2. `pip install -r scripts/research/requirements.txt`
3. Create a Google Cloud project → enable YouTube Data API v3 → create an API key → paste into `.env` (copy from `.env.example`)
4. Edit `config/seed-channels.yaml` with your channel list
5. Optional: tweak `config/research-defaults.yaml`
6. Open a Claude session in the project directory and say *"let's start a new video"*

Estimated one-time setup: 10 minutes.

---

## 9. Out-of-scope items (roadmap for future specs)

Each of these is its own brainstorm → spec → plan → build cycle. Order is flexible except that character-fork must precede image-gen, and TTS+image-gen must precede video-stitch.

1. **Topic generation** — reads `picked_videos.json`, generates spun-off video concepts, user picks one. May integrate [viral-youtube-optimizer-ai](https://github.com/Pratham-Prog861/viral-youtube-optimizer-ai) for title optimization.
2. **Character-fork skill** — separately-valuable deliverable. Fork of [ian-xiaohei-illustrations](https://github.com/helloianneo/ian-xiaohei-illustrations) with the user's own custom character. Requires its own product-level brainstorm to define the character (shape, personality, action library) before touching files.
3. **Script writing** — narrator-style script from a picked topic, with pacing beats marked (for TTS→image sync later).
4. **TTS** — script → audio. Default choice: [Voicebox](https://voicebox.sh/) local desktop app + its bundled MCP server. Requires the user to have Voicebox running when the stage executes. Voice cloning setup is a one-time step.
5. **Image generation** — takes script + pacing beats, generates one styled illustration per beat via GPT-image API using the character-fork skill's prompts. Cost caps to be discussed in that spec.
6. **Video stitching** — Remotion (Node/React) assembles audio + timed images into a final .mp4.
7. **End-to-end polish** — smoothness pass across all stages, error recovery, resumability.

---

## 10. Open questions to revisit

- Whether to add per-video thumbnail *analysis* (image → vision model → thumbnail-hook description) in the research stage or defer to topic-gen. Defer for now — adds cost and complexity, and title+transcript is enough signal for the first slice.
- Whether the skill should default to caching research results within a time window (e.g. reuse `research.json` if generated in the last 24h) or always fetch fresh. Defer to actual usage — start with always-fresh, add caching if it becomes annoying.
- Whether to include multi-language transcript fallback (auto-translate if English caption missing). Defer — user's target format is English, most seed channels will be English.
