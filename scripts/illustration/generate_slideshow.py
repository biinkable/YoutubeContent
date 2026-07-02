"""Generate one 16:9 illustration per beat for a chosen character."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from scripts.common.errors import RefusedByPolicy
from scripts.illustration.character_library import Character

COST_PER_IMAGE: dict[str, float] = {"high": 0.17, "medium": 0.04}

PREVIEW_SCENES: list[dict] = [
    {"id": 1, "scene": "standing and facing the viewer, full body, neutral pose"},
    {"id": 2, "scene": "in mid-action, gesturing with energy as if explaining something"},
    {"id": 3, "scene": "reacting with clear surprise to something just off-frame"},
]


def parse_beats(text: str) -> list[dict]:
    data = yaml.safe_load(text) or {}
    beats = data.get("beats") or []
    if not beats:
        raise ValueError("no beats found; expected a non-empty 'beats:' list")
    out: list[dict] = []
    for b in beats:
        if "id" not in b or "scene" not in b:
            raise ValueError(f"beat missing 'id' or 'scene': {b!r}")
        out.append({"id": int(b["id"]), "scene": str(b["scene"])})
    return out


def build_prompt(character: Character, scene: str) -> str:
    return (
        "A 16:9 landscape illustration. Keep this exact recurring character consistent "
        f"with the reference image(s): {character.description} "
        f"Scene: {scene}. "
        "The character is the main acting subject of the scene, not a bystander. "
        "One clear idea in the frame. Preserve the character's established art style, "
        "colors, and proportions."
    )


def estimate_cost(n: int, quality: str) -> float:
    return round(n * COST_PER_IMAGE.get(quality, COST_PER_IMAGE["high"]), 2)


def run(
    *,
    character: Character,
    beats: list[dict],
    out_dir: Path,
    quality: str = "high",
    size: str = "1536x1024",
    image_client: Any,
    only: set[int] | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir.parent / "slideshow.json"

    prior: dict[int, dict] = {}
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            prior = {f["id"]: f for f in old.get("frames", [])}
        except Exception:
            prior = {}

    refs = character.reference_images[:16]
    dropped = [str(p) for p in character.reference_images[16:]]

    frames: list[dict] = []
    for beat in beats:
        bid = beat["id"]
        selected = only is None or bid in only
        if not selected:
            frames.append(prior.get(bid, {"id": bid, "file": None, "status": "pending", "estimated_cost": 0.0}))
            continue
        fname = f"{bid:02d}-{character.slug}.png"
        fpath = out_dir / fname
        try:
            img = image_client.generate(
                prompt=build_prompt(character, beat["scene"]),
                reference_images=refs,
                size=size,
                quality=quality,
            )
        except RefusedByPolicy as e:
            frames.append({"id": bid, "file": None, "status": "refused", "reason": str(e), "estimated_cost": 0.0})
            continue
        fpath.write_bytes(img.png_bytes)
        frames.append({"id": bid, "file": fname, "status": "ok", "estimated_cost": COST_PER_IMAGE.get(quality, COST_PER_IMAGE["high"])})

    manifest = {
        "character": character.slug,
        "quality": quality,
        "size": size,
        "beats": beats,
        "frames": frames,
        "total_estimated_cost": round(sum(f.get("estimated_cost", 0.0) for f in frames), 2),
        "dropped_reference_images": dropped,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
