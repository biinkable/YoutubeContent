from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.common.errors import QuotaExceeded, RefusedByPolicy
from scripts.illustration.character_library import load_character
from scripts.illustration.generate_slideshow import (
    COST_PER_IMAGE,
    build_prompt,
    estimate_cost,
    parse_beats,
    run,
)
from scripts.illustration.openai_image import GeneratedImage


def _beats():
    return [{"id": 1, "scene": "sorting ideas into a funnel"}, {"id": 2, "scene": "climbing a ladder"}]


def _client(png=b"IMG"):
    c = MagicMock()
    c.generate.return_value = GeneratedImage(png_bytes=png)
    return c


def test_parse_beats_ok():
    text = "beats:\n  - id: 1\n    scene: hello\n  - id: 2\n    scene: world\n"
    assert parse_beats(text) == [{"id": 1, "scene": "hello"}, {"id": 2, "scene": "world"}]


def test_parse_beats_empty_raises():
    with pytest.raises(ValueError):
        parse_beats("beats: []\n")


def test_estimate_cost():
    assert estimate_cost(7, "high") == round(7 * COST_PER_IMAGE["high"], 2)
    assert estimate_cost(7, "medium") == round(7 * COST_PER_IMAGE["medium"], 2)


def test_build_prompt_includes_description_and_scene(sample_character_dir: Path):
    c = load_character(sample_character_dir, "foxy")
    prompt = build_prompt(c, "climbing a ladder")
    assert "orange fox" in prompt
    assert "climbing a ladder" in prompt
    assert "16:9" in prompt


def test_run_generates_all_frames(sample_character_dir: Path, tmp_path: Path):
    c = load_character(sample_character_dir, "foxy")
    out = tmp_path / "run1" / "images"
    client = _client(b"PNGDATA")
    manifest = run(character=c, beats=_beats(), out_dir=out, quality="high", image_client=client)
    assert client.generate.call_count == 2
    assert (out / "01-foxy.png").read_bytes() == b"PNGDATA"
    assert (out / "02-foxy.png").read_bytes() == b"PNGDATA"
    assert [f["status"] for f in manifest["frames"]] == ["ok", "ok"]
    assert manifest["character"] == "foxy"
    assert manifest["total_estimated_cost"] == round(2 * COST_PER_IMAGE["high"], 2)
    # manifest written next to images dir
    saved = json.loads((out.parent / "slideshow.json").read_text(encoding="utf-8"))
    assert saved == manifest


def test_run_refusal_is_per_frame(sample_character_dir: Path, tmp_path: Path):
    c = load_character(sample_character_dir, "foxy")
    out = tmp_path / "run2" / "images"
    client = MagicMock()
    client.generate.side_effect = [GeneratedImage(png_bytes=b"ok"), RefusedByPolicy("nope")]
    manifest = run(character=c, beats=_beats(), out_dir=out, quality="high", image_client=client)
    assert [f["status"] for f in manifest["frames"]] == ["ok", "refused"]
    assert (out / "01-foxy.png").exists()
    assert not (out / "02-foxy.png").exists()


def test_run_quota_propagates(sample_character_dir: Path, tmp_path: Path):
    c = load_character(sample_character_dir, "foxy")
    out = tmp_path / "run3" / "images"
    client = MagicMock()
    client.generate.side_effect = QuotaExceeded("billing")
    with pytest.raises(QuotaExceeded):
        run(character=c, beats=_beats(), out_dir=out, quality="high", image_client=client)


def test_run_only_regenerates_selected_and_preserves_others(sample_character_dir: Path, tmp_path: Path):
    c = load_character(sample_character_dir, "foxy")
    out = tmp_path / "run4" / "images"
    # first full run
    run(character=c, beats=_beats(), out_dir=out, quality="high", image_client=_client(b"V1"))
    # regenerate only beat 2
    client2 = _client(b"V2")
    manifest = run(character=c, beats=_beats(), out_dir=out, quality="high", image_client=client2, only={2})
    assert client2.generate.call_count == 1
    assert (out / "01-foxy.png").read_bytes() == b"V1"   # preserved
    assert (out / "02-foxy.png").read_bytes() == b"V2"   # regenerated
    assert [f["id"] for f in manifest["frames"]] == [1, 2]
