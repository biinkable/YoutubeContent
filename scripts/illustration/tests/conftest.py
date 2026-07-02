"""Shared pytest fixtures for illustration subsystem tests."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_character_dir(tmp_path: Path) -> Path:
    """A library dir containing one character 'foxy' with two reference images."""
    lib = tmp_path / "characters"
    ref = lib / "foxy" / "reference"
    ref.mkdir(parents=True)
    (ref / "01.png").write_bytes(b"\x89PNG\r\n\x1a\n-fake-1")
    (ref / "02.png").write_bytes(b"\x89PNG\r\n\x1a\n-fake-2")
    (lib / "foxy" / "character.md").write_text(
        "A round orange fox mascot with a blue scarf, flat 2D cartoon style, cheerful.",
        encoding="utf-8",
    )
    (lib / "foxy" / "meta.yaml").write_text(
        "slug: foxy\ndisplay_name: Foxy\ncreated_at: '2026-07-02T00:00:00Z'\nnotes: ''\n",
        encoding="utf-8",
    )
    return lib
