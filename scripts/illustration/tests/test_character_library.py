from __future__ import annotations

from pathlib import Path

import pytest

from scripts.illustration.character_library import (
    Character,
    CharacterNotFound,
    add_character,
    list_characters,
    load_character,
)


def test_load_existing_character(sample_character_dir: Path):
    c = load_character(sample_character_dir, "foxy")
    assert isinstance(c, Character)
    assert c.slug == "foxy"
    assert c.display_name == "Foxy"
    assert "orange fox" in c.description
    assert len(c.reference_images) == 2
    assert c.reference_images[0].name == "01.png"


def test_load_missing_raises(sample_character_dir: Path):
    with pytest.raises(CharacterNotFound):
        load_character(sample_character_dir, "nope")


def test_list_characters(sample_character_dir: Path):
    assert list_characters(sample_character_dir) == [
        {"slug": "foxy", "display_name": "Foxy"}
    ]


def test_list_empty_when_dir_missing(tmp_path: Path):
    assert list_characters(tmp_path / "does-not-exist") == []


def test_add_character_copies_and_writes(tmp_path: Path):
    lib = tmp_path / "characters"
    src1 = tmp_path / "a.png"
    src2 = tmp_path / "b.jpg"
    src1.write_bytes(b"img-a")
    src2.write_bytes(b"img-b")
    c = add_character(
        lib,
        slug="robot",
        display_name="Robot",
        image_paths=[src1, src2],
        description="A boxy tin robot, matte grey, friendly.",
        now_iso="2026-07-02T12:00:00Z",
    )
    assert c.slug == "robot"
    assert (lib / "robot" / "character.md").read_text(encoding="utf-8").startswith("A boxy tin robot")
    assert (lib / "robot" / "reference" / "01.png").read_bytes() == b"img-a"
    assert (lib / "robot" / "reference" / "02.jpg").read_bytes() == b"img-b"
    # round-trips through load
    loaded = load_character(lib, "robot")
    assert loaded.display_name == "Robot"
    assert len(loaded.reference_images) == 2
