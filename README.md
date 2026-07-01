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
