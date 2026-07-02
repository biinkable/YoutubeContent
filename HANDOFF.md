# YoutubeContent — Project Handoff

**Last updated:** 2026-07-02
**Repo:** https://github.com/biinkable/YoutubeContent (`origin/main`)
**Owner:** Barry (non-developer — agents plan and build; Barry reviews)

This file is the single source of truth for picking the project back up in a
fresh session. Read it top-to-bottom and you'll know what exists, what's next,
and the rules that keep the repo safe.

---

## 1. What we're building

An **agent-orchestrated, end-to-end YouTube video generator**. You give it a
topic idea (seeded from channels you like); it researches, writes, narrates,
illustrates, and stitches a finished video. The visual signature is a
**recurring custom character** that you own — you supply a reference image, and
every frame renders in *that character's own look*.

There is **no custom web UI**. Claude Code sessions *are* the interface — you
drive the pipeline conversationally and review each stage's output before moving
on (human-in-the-loop).

### The six subsystems

| # | Subsystem | Job | Status |
|---|-----------|-----|--------|
| 1 | **Research** | Mine user-provided seed channels for their recent viral videos | ✅ **Built** |
| 2 | **Topic selection** | Spin new video concepts off the seed channels' hooks | ⬜ Not started |
| 3 | **Script writing** | Narrator-style viral-hook explainer scripts | ⬜ Not started |
| 4 | **TTS (audio)** | Script → voiced audio with pacing beats | ⬜ Not started |
| 5 | **Illustration** | Slideshow imagery in the character's style (GPT-image-2) | ✅ **Built** |
| 6 | **Video stitching** | Audio + images → final .mp4 | ⬜ Not started |

> Numbering follows the *pipeline order*. We built **Research** and
> **Illustration** first because they're the two ends with the hardest external
> dependencies (YouTube API, image model) — proving those de-risks the middle.

---

## 2. Architecture decisions (and why)

- **Per-subsystem cycle, never all-at-once.** Each subsystem gets its own
  brainstorm → spec → plan → implement → review loop. Specs live in
  `docs/superpowers/specs/`, plans in `docs/superpowers/plans/` (dated).
- **Subagent-driven development.** A fresh implementer subagent builds each task;
  a reviewer checks each task; an opus review covers the whole branch before
  merge. This loop has already caught **4 real plan defects** (see §6).
- **Mixed runtime on purpose.** Python for research/data/illustration; Node
  (Remotion) reserved for video stitching later.
- **Human-in-the-loop at every stage.** Nothing is fully automatic; you approve
  between stages inside a Claude session.
- **Seed channels are manual.** No discovery or monetization inference — you
  supply the list in `config/seed-channels.yaml`.
- **Dependency-injection seams everywhere.** External calls (OpenAI, YouTube) are
  injected so unit tests mock them; a separate live integration test runs only
  when a real key is present (and is skipped otherwise).
- **Character design (locked in):** image-referenced generation that **preserves
  each character's own look** — *not* the ian-xiaohei hand-drawn house style.
  One recurring character per video. High quality with a preview step for new
  characters. Budget ≈ **$1/video** (~$0.17/image at high quality).
- **Shared plumbing** lives in `scripts/common/` (error taxonomy + retry).
  `pyproject.toml` sets `pythonpath=["."]` — `scripts/` is a namespace package,
  so **there is no `__init__.py`** and there must not be one.

---

## 3. Current state

### Tests
**77 unit tests passing + 2 integration tests** that skip automatically when no
API key is present. All green.

### Subsystem 1 — Research (built & pushed)
Mines seed channels via the **YouTube Data API v3** (free, 10k units/day) plus
`youtube-transcript-api` (1.x).

```
scripts/research/
  channel_resolver.py      # @handle / URL / ID → channel ID
  metrics.py               # views-per-day style viral scoring
  youtube_client.py        # API wrapper (injected)
  transcript_fetcher.py    # uses 1.x .fetch() / .to_raw_data()
  fetch_viral_from_seeds.py# entry point → outputs/<run-id>/picked_videos.json
skills/research/           # the Claude skill that drives it
config/seed-channels.yaml  # YOU add channels here
```

**Before it's usable:** (a) `YOUTUBE_API_KEY` in `.env` (already present),
(b) add channels to `config/seed-channels.yaml`, (c) run the smoke test from a
fresh session ("let's start a new video").

### Subsystem 5 — Illustration (built & pushed)
Character library + GPT-image-2 slideshow generator.

```
scripts/common/errors.py           # ApiError/Transient/QuotaExceeded/RefusedByPolicy + retry_on_transient
scripts/illustration/
  openai_image.py                  # GPT-image-2 client (images.edit), reference cap = 16
  character_library.py             # add/list/load characters; frozen Character dataclass
  generate_slideshow.py            # run() + CLI, cost estimate, preview mode, exit codes
skills/illustration/               # SKILL.md + references/composition.md
config/illustration-defaults.yaml
characters/                        # YOUR character library (per-character reference images + meta)
```

**CLI exit codes:** `0` ok · `2` missing key · `3` quota · `4` over
max-images-per-run without `--allow-large` · `5` bad slug / empty beats.
**Cost:** high `$0.17`/image, medium `$0.04`/image.

**Before it's usable:** run the manual smoke test (§5) — every test mocks the
OpenAI call, so the *real* GPT-image-2 API surface is the one thing not yet
exercised. That's where any API mismatch would surface.

---

## 4. Security rules (NON-NEGOTIABLE)

Barry once pasted real keys into the **tracked** `.env.example` (caught before
any commit; never pushed). These rules exist because of that.

1. **Real keys live in `.env` only** — it's gitignored. NEVER in `.env.example`,
   README, docs, code, or any tracked file.
2. **Never `git add .` / `git add -A`** in this repo. Stage specific paths:
   `git add scripts/foo.py`.
3. **Sweep every push** for secrets before it leaves:
   ```bash
   git log -p origin/main..HEAD | grep -E "sk-proj-[A-Za-z0-9_-]{20,}|AIzaSy[A-Za-z0-9_-]{20,}"
   ```
   Confirm `.env` never appears among committed files.
4. **Keep the build free.** The harness loads `.env` into the shell env, so any
   pytest that could hit the live OpenAI/YouTube path must run with the keys
   stripped:
   ```bash
   env -u OPENAI_API_KEY -u YOUTUBE_API_KEY pytest
   ```
5. **ROTATE THE EXPOSED KEYS.** Both keys have appeared in session logs /
   briefly in a tracked file. Regenerate them (OpenAI especially — it's paid)
   and swap the new values into `.env`. Everything keeps working; only the
   secret value changes.

---

## 5. Smoke tests (the last mile for each built subsystem)

### Illustration (Ill Task 10)
In a fresh Claude Code session in this repo:
1. Confirm `OPENAI_API_KEY` is in `.env` (it is).
2. Say *"add a new character"* and provide an image.
3. Claude describes it, runs a **preview** (2–3 frames), and shows them.
4. Confirm the character looks consistent across frames. ✅ = illustration works
   end-to-end against the real API.

### Research
1. Confirm `YOUTUBE_API_KEY` in `.env`.
2. Add a few channels to `config/seed-channels.yaml`.
3. Say *"let's start a new video"* and let it fetch viral candidates.

---

## 6. History worth keeping (defects the review loop caught)

- **Pagination infinite-loop** in research uploads listing → fixed to stop at
  first pre-cutoff video.
- **Obsolete `youtube-transcript-api` API** (`get_transcript`) → adapted to 1.x
  `.fetch()` / `.to_raw_data()`, live-verified, pinned `>=1.0.0`.
- **Missing test coverage** for retry/quota/CLI paths → added.
- **Illustration reference-image cap (>16)** untested → test added (commit
  `6a33612`).

### Deferred minors (non-blocking follow-ups)
- Research: case-insensitive URL regex in `channel_resolver`; config-key
  validation at load.
- Illustration: `_classify` uses broad substring matching; empty-beats exit-5
  path untested; `--only` doesn't report cumulative cost.

---

## 7. What's next

Pick the next subsystem and run a fresh **brainstorm → spec → plan → build**
cycle. Recommended order:

1. **Topic selection (subsystem 2)** — natural next step; reads
   `outputs/<run-id>/picked_videos.json` from research. Small, self-contained.
2. **Script writing (subsystem 3)** — turns a picked topic into a narrator
   script.
3. **TTS (subsystem 4)** — **Voicebox** (https://voicebox.sh/) is the leading
   candidate: local, free, open-source, ships an MCP server so Claude Code can
   invoke it directly (no custom scripts), supports voice cloning from a
   10–30s sample, runs on your GPU. Needs its own brainstorm to confirm.
4. **Video stitching (subsystem 6)** — Remotion (Node). Last, because it
   depends on everything upstream.

**Do not** design multiple subsystems at once. One cycle at a time.

---

## 8. Key paths cheat-sheet

```
.env                  # real keys (gitignored) — never commit
.env.example          # empty template (tracked)
config/               # seed-channels.yaml, illustration-defaults.yaml
scripts/common/       # shared errors + retry
scripts/research/     # subsystem 1
scripts/illustration/ # subsystem 5
skills/               # Claude skills that drive each subsystem
characters/           # your character library
docs/superpowers/     # specs/ and plans/ (dated, per subsystem)
outputs/              # per-run artifacts (gitignored except .gitkeep)
pyproject.toml        # pytest pythonpath=["."]
```
