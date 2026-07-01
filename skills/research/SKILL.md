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
