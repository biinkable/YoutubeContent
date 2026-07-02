# Character Illustration Subsystem — Design

**Date:** 2026-07-02
**Status:** Draft, pending user review
**Scope:** The character + illustration subsystem of the YoutubeContent pipeline. Provides a reusable **character library** and generates a video's **slideshow imagery** — one 16:9 image per script beat — using a chosen character, via GPT-image-2 (reference-image generation). Built standalone and testable now; integrates with the (not-yet-built) script and video-stitch subsystems later.

---

## 1. Goal

From inside a Claude session, the user can:

1. **Add a character** to a reusable library by providing one or more images. Claude derives a text identity description and generates 2–3 preview frames so the user can confirm the character holds up before committing.
2. **Select a character** (new or existing) for a given video.
3. **Generate a slideshow**: one 16:9 illustration per scene "beat," each conditioned on the chosen character's reference image(s) so the character stays consistent and its native rendering style carries through.
4. **Review and regenerate** individual frames cheaply.

The final images land in `outputs/<run-id>/images/` ready for the video-stitch subsystem.

---

## 2. Product decisions (locked during brainstorm 2026-07-02)

- **One recurring character per video.** The selected character stars in every frame of that video's slideshow. A cast of multiple characters per video is explicitly out of scope (may be added later).
- **Preserve each character's own look.** Illustrations match the rendering style of the provided image (glossy 3D stays glossy 3D, flat cartoon stays flat cartoon). There is NO forced "house style" — the source image defines both identity and style. This is a deliberate departure from the `ian-xiaohei-illustrations` repo's fixed hand-drawn aesthetic.
- **Image-referenced generation**, not text-only. GPT-image-2 accepts up to 16 reference images at high fidelity and 16:9 output; every frame references the character's canonical image(s), reinforced by a derived text description.
- **High quality + preview.** Default generation quality is "high" (~$0.17/image landscape, ~$1/video). Adding a new character always previews 2–3 sample frames first.
- **Character library is user-built.** Starts empty; grows as the user adds characters. Characters are provided at use-time (like seed channels for research) — no image is needed to build the subsystem.
- **New paid dependency**: `OPENAI_API_KEY` in `.env` (separate from the free `YOUTUBE_API_KEY`).

---

## 3. Non-goals

- A cast of multiple characters in one video (single recurring character only).
- A fixed channel "house style" that redraws characters (each character keeps its own look).
- The script subsystem that produces beats (this subsystem accepts beats as input; the script stage is separate).
- Video assembly / audio sync (video-stitch subsystem).
- Automated character discovery or generation from scratch — the user provides source images.
- Animation or video output — still images only.

---

## 4. Architecture

Mirrors the research subsystem's pattern: Python scripts do the work, a Claude Skill orchestrates the interactive session, artifacts live as files.

```
YoutubeContent/
├── characters/                         # the user's character library
│   └── <slug>/
│       ├── reference/                  # 1+ source images (canonical look)
│       │   ├── 01.png
│       │   └── 02.png                  # optional extra angles/poses
│       ├── character.md                # derived text identity description
│       └── meta.yaml                   # slug, display_name, created_at, notes
├── scripts/
│   └── illustration/
│       ├── __init__.py
│       ├── openai_image.py             # GPT-image-2 API client (DI seam, retry, refusal handling)
│       ├── character_library.py        # add / list / load characters
│       ├── generate_slideshow.py       # CLI entrypoint: character + beats -> images
│       ├── requirements.txt
│       └── tests/
│           ├── __init__.py
│           ├── conftest.py
│           ├── test_openai_image.py
│           ├── test_character_library.py
│           ├── test_generate_slideshow.py
│           └── test_integration.py     # live, skipped without OPENAI_API_KEY
├── skills/
│   └── illustration/
│       ├── SKILL.md                    # how Claude runs add/select/preview/generate/review
│       └── references/
│           └── composition.md          # scene/composition prompting guidance (style-agnostic)
├── config/
│   └── illustration-defaults.yaml      # quality, preview count, size, per-run image cap
├── pyproject.toml                      # NEW: shared pytest config (pythonpath="."), tooling
├── scripts/common/                     # NEW: shared error taxonomy
│   ├── __init__.py
│   └── errors.py                       # ApiError / QuotaExceeded / RefusedByPolicy base classes
└── outputs/<run-id>/
    ├── images/NN-<slug>.png            # generated frames
    └── slideshow.json                  # manifest: character, beats, per-frame status/cost
```

### Cross-subsystem groundwork (added now, benefits all future stages)

- **`pyproject.toml`** with `[tool.pytest.ini_options] pythonpath = ["."]` so tests import `scripts.*` regardless of invocation directory (the research subsystem relied on running pytest from the root; this makes it robust). Also a home for lint/format config.
- **`scripts/common/errors.py`** — a shared error taxonomy (`ApiError`, `QuotaExceeded`, `RefusedByPolicy`, `TransientError`) so the OpenAI client and the existing YouTube client can share the retry/quota distinction. The research subsystem's `youtube_client` exceptions are NOT rewritten in this spec (out of scope), but new code uses the shared base.

---

## 5. Character library

### 5.1 Storage

- One folder per character: `characters/<slug>/`.
- `reference/` holds 1+ images. More angles/poses → better consistency. All are passed to GPT-image-2 as reference inputs (capped at the API's 16).
- `character.md` — a short text identity description Claude writes by looking at the image(s): shape, colors, distinctive features, overall style descriptor (e.g. "flat 2D cartoon," "glossy 3D render"), and personality/demeanor. Rides in every generation prompt as a consistency backstop.
- `meta.yaml` — `slug`, `display_name`, `created_at` (absolute date), optional `notes`.

### 5.2 Adding a character (interactive skill flow)

1. User provides image(s) — attached in-session or a file path. Claude copies them into `characters/<slug>/reference/`.
2. Claude examines the image(s) with vision and writes `character.md` (no code — Claude has vision).
3. Claude writes `meta.yaml`.
4. **Preview**: Claude runs the slideshow generator in preview mode — 2–3 fixed, character-revealing test scenes (e.g. "standing facing viewer," "in action mid-gesture," "reacting with surprise") — and shows the user.
5. User approves (character stays in the library) or asks to adjust `character.md` / swap images / discard.

### 5.3 Listing / selecting

- List = enumerate `characters/*/meta.yaml` and present display names.
- Select = the chosen `<slug>` is passed to the generator.

---

## 6. Generation

### 6.1 Input contract (standalone-testable now)

`generate_slideshow.py` takes:
- `--character <slug>` — which character to use
- `--beats <path>` — a beats file (see 6.2)
- `--out outputs/<run-id>/images/` — output dir
- `--quality high|medium` (default from config)
- `--preview` — preview mode (uses built-in sample scenes instead of a beats file, generates the configured preview count)

The beats file is the interface the future script subsystem will emit. Defined as a simple YAML/JSON list so it's writable by hand for testing today:

```yaml
beats:
  - id: 1
    scene: "The character peers into a giant funnel labeled with question marks, sorting falling ideas."
  - id: 2
    scene: "The character carries an oversized glowing lightbulb up a ladder."
```

### 6.2 Per-beat generation

For each beat, call GPT-image-2 with:
- **Reference images**: the character's canonical `reference/*` images (all of them, up to the API cap).
- **Prompt**, assembled from:
  - The character identity from `character.md` (reinforces the reference).
  - The beat's `scene` text.
  - Fixed format rules: 16:9 landscape; one clear idea per frame; the character is the acting subject of the scene (not a bystander/decoration); keep the character's established look.
- **Size**: 1536×1024 (16:9). **Quality**: per the quality setting.

**Consistency mechanism**: every frame references the SAME canonical image set, so drift is minimized and the character's native style is preserved. (Chaining a prior generated frame as an extra reference is a possible future enhancement; not required for v1 — canonical-reference-per-frame is the baseline.)

### 6.3 Output

- Images saved as `outputs/<run-id>/images/NN-<slug>.png`, zero-padded, in beat order.
- `outputs/<run-id>/slideshow.json` manifest: character slug, the beats used, per-frame filename + status (`ok` / `refused` / `error`) + estimated cost, and total estimated cost.

### 6.4 Review & regenerate

- Claude presents the generated set to the user.
- The user can request regeneration of any single beat (one API call, cheap) — the CLI supports `--only <beat_id>` to regenerate specific frames into the same run folder without redoing the rest.

### 6.5 Cost guardrail

- Before a full (non-preview) run, the skill confirms the beat count and shows the estimated cost (count × per-image estimate for the chosen quality).
- `config/illustration-defaults.yaml` includes `max_images_per_run` (default e.g. 12); exceeding it requires explicit user confirmation. This is logged, not silently truncated.

---

## 7. Error handling

- **Missing `OPENAI_API_KEY`** → CLI exits with code 2 and a clear message pointing at `.env.example`; skill surfaces it and links setup steps.
- **Quota / billing exhausted** (OpenAI 429 insufficient_quota) → exit 3, mapped to shared `QuotaExceeded`; skill explains and stops.
- **Content-policy refusal** (GPT-image-2 refuses a prompt) → that frame's status is `refused` in the manifest with the refusal reason; the run continues to other beats. Skill surfaces refused frames and offers to reword the beat and regenerate just that one.
- **Transient errors** (5xx, network, rate-limit 429 rate) → retry up to 3× with exponential backoff (shared with the common error module's policy).
- **Invalid character slug** (not in library) → CLI exits with a clear message listing available slugs.
- **Empty/oversized reference set** → if a character has 0 reference images, error clearly; if >16, use the first 16 and log which were dropped.
- **Partial run** → a per-frame failure never aborts the whole run; the manifest records each frame's status so the user sees exactly what succeeded.

---

## 8. Testing

- **Unit tests** (mocked OpenAI client, no network, no spend):
  - `openai_image.py`: prompt assembly, reference-image attachment, retry-on-transient, quota mapping, refusal handling, size/quality params.
  - `character_library.py`: add (copies images, writes meta), list, load, missing-slug error, >16 reference cap.
  - `generate_slideshow.py`: beats parsing, per-beat orchestration, manifest content, `--only` regeneration, `--preview` mode, cost estimation, exit codes (missing key → 2, quota → 3).
- **Integration test** (`test_integration.py`): a real GPT-image-2 call; `pytest.mark.skipif(not OPENAI_API_KEY)`. Generates one small image against a tiny built-in reference and asserts a valid image file is written. Skips (not fails) with no key, so the default suite is free and offline.
- **Live validation at smoke-test time**: the user sets `OPENAI_API_KEY` in `.env`, adds a real character, and runs a preview — confirming a real character holds up. (This is the manual acceptance step, analogous to the research subsystem's smoke test.)
- No tests for the skill/reference Markdown (they are prompts).

---

## 9. Setup additions (documented in README)

1. Get an **OpenAI API key** (paid) → add `OPENAI_API_KEY=` to `.env` (add the line to `.env.example` too).
2. `pip install -r scripts/illustration/requirements.txt` (adds the `openai` SDK).
3. To use: open a Claude session and either "add a new character" (provide image) or "use character X," then generate.

---

## 10. Integration with the wider pipeline

- **Upstream (later): script subsystem** produces the beats file this stage consumes. Until then, beats are hand-written or pasted for testing.
- **Downstream (later): video-stitch subsystem** consumes `outputs/<run-id>/images/` + the audio to build the final video, using the image order (and later, timing) to sequence the slideshow.
- The top-level pipeline `SKILL.md` gains an "illustration" stage entry pointing at `skills/illustration/SKILL.md`, positioned after script and before video. This spec adds the stage; it does not wire an automatic hand-off from a script stage that doesn't exist yet.

---

## 11. Open questions / deferred

- **Frame-chaining for extra consistency** (passing an approved frame as an additional reference on subsequent frames): deferred; canonical-reference-per-frame is the v1 baseline. Revisit if real output drifts too much.
- **Background/scene style consistency across frames within a video**: relying on GPT-image-2 coherence + the character reference for v1. If backgrounds vary distractingly, a future enhancement could add a per-video "setting" descriptor to the prompt. Deferred.
- **Reusing `scripts/common/errors.py` in the existing `youtube_client`**: left as-is for now to avoid touching a tested module out of scope; new code adopts the shared taxonomy.
- **Batch API (50% cheaper, up to 24h latency)**: not used — interactive review needs synchronous results. Noted for a possible future bulk mode.
