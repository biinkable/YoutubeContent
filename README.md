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

## Illustration subsystem

### Setup

#### 1. Get an image-provider API key

The illustration subsystem generates with **GPT-image-2**. By default it routes through
**[kie.ai](https://kie.ai/)** — a cheaper gateway to GPT-image-2 — and can fall back to
OpenAI's own API (set `provider: openai` in `config/illustration-defaults.yaml`, or pass
`--provider openai`).

1. **kie.ai (default, cheaper):** create a key at [kie.ai/api-key](https://kie.ai/api-key).
2. **OpenAI (optional fallback, paid):** create a key at [OpenAI Platform](https://platform.openai.com/account/api-keys) — requires active billing.
3. Copy `.env.example` to `.env` if you haven't already (see research setup above).
4. Edit `.env` and add whichever key matches your provider:

        KIE_API_KEY=...your-kie-key-here...
        # or, for the OpenAI provider:
        OPENAI_API_KEY=sk-...your-key-here...

**Warning:** Never commit `.env` to version control. `.env.example` lists the key names for reference but does not contain any real keys.

#### 2. Install illustration dependencies

    pip install -r scripts/illustration/requirements.txt

### Usage

The illustration subsystem generates one 16:9 landscape image per script beat, starring a recurring character styled with GPT-image-2 (reference-based generation).

#### Workflow 1: Add a new character

1. Provide one or more reference images of your character (any angle or pose).
2. Claude writes a short identity description: shape, colors, distinctive features, art style, and demeanor.
3. Claude adds the character to the library and previews sample frames:

        python scripts/illustration/generate_slideshow.py --character <slug> --preview --out outputs/<run-id>/preview --yes

4. Review the preview. If you're happy, keep it; if not, provide feedback and Claude adjusts the description or images.

#### Workflow 2: Generate a video's slideshow

1. Confirm which character to use (Claude lists available characters).
2. Provide a beats file (for now, hand-written YAML; later from the script subsystem). Format:

        beats:
          - id: 1
            scene: "standing and facing the viewer, full body, neutral pose"
          - id: 2
            scene: "in mid-action, gesturing with energy"

3. Claude shows the estimated cost and image count, then runs:

        python scripts/illustration/generate_slideshow.py \
          --character <slug> --beats <path-to-beats.yaml> \
          --out outputs/<run-id>/images --quality high --yes

4. Review the generated images. To regenerate a single frame:

        python scripts/illustration/generate_slideshow.py \
          --character <slug> --beats <path-to-beats.yaml> \
          --out outputs/<run-id>/images --only 3 --yes

5. Claude reports what was generated and any policy-refused frames.

### Cost and image size

Cost depends on the provider. **kie.ai (default)** is markedly cheaper than OpenAI:

| Provider | High (2K) | Medium (1K) |
|----------|-----------|-------------|
| kie.ai (default) | ~$0.05/image | ~$0.03/image |
| OpenAI | ~$0.17/image | ~$0.04/image |

kie.ai bills in credits; the USD figures above are the confirmed per-generation prices for
GPT-image-2 image-to-image (2K = 10 credits, 1K = 6 credits; 4K = 16 credits ≈ $0.08 is also
available but not wired to a quality tier). They drive only the pre-run cost print — adjust
`cost_per_image` in `config/illustration-defaults.yaml` if kie's pricing changes.

Images are generated at 1536×1024 (mapped to kie.ai aspect ratio 3:2).

### Command-line reference

```bash
python scripts/illustration/generate_slideshow.py \
  --character <slug>           # Character slug in the library (required)
  --beats <path>               # Path to beats YAML file (required unless --preview)
  --out <path>                 # Output directory, e.g. outputs/<run-id>/images (required)
  --quality [high|medium]      # Override default quality (optional)
  --preview                    # Use 3 built-in sample scenes instead of beats (optional)
  --only <id1,id2,...>         # Regenerate only these beat IDs (optional)
  --allow-large                # Permit runs above max_images_per_run limit (optional)
  --library <path>             # Character library directory, default: characters (optional)
  --yes                        # Skip interactive confirmation (optional)
```

### Running tests

Test the entire research and illustration subsystems:

    python -m pytest scripts -v

Test only illustration subsystem:

    python -m pytest scripts/illustration -v

---

## Running tests (research subsystem)

    python -m pytest scripts/research/tests -v --ignore=scripts/research/tests/test_integration.py

To include the real-API integration test (needs a live YOUTUBE_API_KEY):

    python -m pytest scripts/research/tests -v
