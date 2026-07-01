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
