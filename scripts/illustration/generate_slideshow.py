"""Generate one 16:9 illustration per beat for a chosen character."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Allow direct invocation (`python scripts/illustration/generate_slideshow.py ...`):
# Python only puts this file's own directory on sys.path, so ensure the repo root
# (which makes `scripts` importable as a namespace package) is present too.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.common.errors import ApiError, QuotaExceeded, RefusedByPolicy
from scripts.illustration.character_library import (
    Character,
    CharacterNotFound,
    list_characters,
    load_character,
)
from scripts.illustration.kie_image import KieImageClient
from scripts.illustration.openai_image import OpenAIImageClient

# Env var holding each provider's API key.
_KEY_ENV: dict[str, str] = {"kie": "KIE_API_KEY", "openai": "OPENAI_API_KEY"}

# Fallback per-image cost estimates (USD), used only as a pre-run guardrail. These
# are the OpenAI numbers; the kie.ai provider overrides them from config
# (cost_per_image), since kie prices by resolution and is much cheaper.
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


def estimate_cost(n: int, quality: str, cost_map: dict[str, float] | None = None) -> float:
    prices = cost_map or COST_PER_IMAGE
    return round(n * prices.get(quality, prices.get("high", COST_PER_IMAGE["high"])), 2)


def run(
    *,
    character: Character,
    beats: list[dict],
    out_dir: Path,
    quality: str = "high",
    size: str = "1536x1024",
    image_client: Any,
    only: set[int] | None = None,
    cost_per_image: dict[str, float] | None = None,
) -> dict:
    prices = cost_per_image or COST_PER_IMAGE
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
        frames.append({"id": bid, "file": fname, "status": "ok", "estimated_cost": prices.get(quality, prices.get("high", 0.0))})

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


def _load_defaults() -> dict:
    cfg = Path(__file__).resolve().parents[2] / "config" / "illustration-defaults.yaml"
    if cfg.is_file():
        return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    return {"provider": "kie", "quality": "high", "size": "1536x1024", "preview_count": 3, "max_images_per_run": 12}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a character slideshow with GPT-image-2.")
    p.add_argument("--character", required=True, help="Character slug in the library")
    p.add_argument("--beats", type=Path, help="Path to a beats YAML file (omit with --preview)")
    p.add_argument("--out", required=True, type=Path, help="Output images dir, e.g. outputs/<run-id>/images")
    p.add_argument("--library", type=Path, default=Path("characters"), help="Character library dir")
    p.add_argument("--provider", choices=["kie", "openai"], help="Image provider (default from config: kie)")
    p.add_argument("--quality", choices=["high", "medium"], help="Override default quality")
    p.add_argument("--preview", action="store_true", help="Use built-in sample scenes")
    p.add_argument("--allow-large", action="store_true", help="Permit runs above max_images_per_run")
    p.add_argument("--only", help="Comma-separated beat ids to (re)generate")
    p.add_argument("--yes", action="store_true", help="Skip interactive confirmation (non-interactive use)")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    defaults = _load_defaults()
    provider = (args.provider or defaults.get("provider", "kie")).lower()
    quality = args.quality or defaults.get("quality", "high")
    size = defaults.get("size", "1536x1024")
    max_images = int(defaults.get("max_images_per_run", 12))
    preview_count = int(defaults.get("preview_count", 3))
    cost_map = defaults.get("cost_per_image") or COST_PER_IMAGE

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")

    env_var = _KEY_ENV.get(provider)
    if env_var is None:
        print(f"ERROR: unknown provider {provider!r}. Choose 'kie' or 'openai'.", file=sys.stderr)
        return 5
    api_key = os.environ.get(env_var, "").strip()
    if not api_key:
        print(f"ERROR: {env_var} not set. Add it to your .env (see .env.example).", file=sys.stderr)
        return 2

    try:
        character = load_character(args.library, args.character)
    except CharacterNotFound as e:
        print(f"ERROR: {e}. Available: {[c['slug'] for c in list_characters(args.library)]}", file=sys.stderr)
        return 5

    if args.preview:
        beats = PREVIEW_SCENES[:preview_count]
    else:
        if not args.beats:
            print("ERROR: --beats is required unless --preview is set.", file=sys.stderr)
            return 5
        try:
            beats = parse_beats(args.beats.read_text(encoding="utf-8"))
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 5

    only = None
    if args.only:
        only = {int(x) for x in args.only.split(",") if x.strip()}

    n = len(beats) if only is None else len(only)
    print(f"Estimated cost: ${estimate_cost(n, quality, cost_map)} for {n} image(s) at {quality} quality via {provider}.")
    if not args.preview and n > max_images and not args.allow_large:
        print(f"ERROR: {n} images exceeds max_images_per_run={max_images}. Re-run with --allow-large to proceed.", file=sys.stderr)
        return 4

    client = KieImageClient(api_key) if provider == "kie" else OpenAIImageClient(api_key)
    try:
        run(character=character, beats=beats, out_dir=args.out, quality=quality, size=size,
            image_client=client, only=only, cost_per_image=cost_map)
    except QuotaExceeded as e:
        print(f"ERROR: {provider} quota/billing exhausted.\n{e}", file=sys.stderr)
        return 3
    except ApiError as e:
        print(f"ERROR: image generation failed via {provider}.\n{e}", file=sys.stderr)
        return 6
    print(f"Wrote images to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
