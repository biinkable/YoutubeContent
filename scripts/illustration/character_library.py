"""Manage the on-disk character library (add / list / load)."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml


class CharacterNotFound(Exception):
    """Raised when a character slug is not present in the library."""


@dataclass(frozen=True)
class Character:
    slug: str
    display_name: str
    reference_images: list[Path]
    description: str


def _char_dir(library_dir: Path, slug: str) -> Path:
    return library_dir / slug


def add_character(
    library_dir: Path,
    *,
    slug: str,
    display_name: str,
    image_paths: list[Path],
    description: str,
    now_iso: str,
    notes: str = "",
) -> Character:
    cdir = _char_dir(library_dir, slug)
    ref_dir = cdir / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    for idx, src in enumerate(image_paths, start=1):
        dst = ref_dir / f"{idx:02d}{src.suffix.lower()}"
        shutil.copyfile(src, dst)
    (cdir / "character.md").write_text(description, encoding="utf-8")
    (cdir / "meta.yaml").write_text(
        yaml.safe_dump(
            {"slug": slug, "display_name": display_name, "created_at": now_iso, "notes": notes},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return load_character(library_dir, slug)


def list_characters(library_dir: Path) -> list[dict]:
    if not library_dir.is_dir():
        return []
    out: list[dict] = []
    for meta in sorted(library_dir.glob("*/meta.yaml")):
        data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
        out.append({"slug": data.get("slug", meta.parent.name), "display_name": data.get("display_name", meta.parent.name)})
    return out


def load_character(library_dir: Path, slug: str) -> Character:
    cdir = _char_dir(library_dir, slug)
    meta_path = cdir / "meta.yaml"
    desc_path = cdir / "character.md"
    ref_dir = cdir / "reference"
    if not (meta_path.is_file() and desc_path.is_file() and ref_dir.is_dir()):
        raise CharacterNotFound(f"character not found: {slug!r}")
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    refs = sorted(p for p in ref_dir.iterdir() if p.is_file())
    if not refs:
        raise CharacterNotFound(f"character {slug!r} has no reference images")
    return Character(
        slug=meta.get("slug", slug),
        display_name=meta.get("display_name", slug),
        reference_images=refs,
        description=desc_path.read_text(encoding="utf-8").strip(),
    )
