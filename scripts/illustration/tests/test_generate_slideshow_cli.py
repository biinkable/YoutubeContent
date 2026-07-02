from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.illustration import generate_slideshow as gs
from scripts.illustration.openai_image import GeneratedImage


def _write_beats(tmp_path: Path, n=2) -> Path:
    lines = ["beats:"]
    for i in range(1, n + 1):
        lines += [f"  - id: {i}", f"    scene: scene {i}"]
    p = tmp_path / "beats.yaml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["prog", *args])


def test_main_missing_key_exits_2(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    beats = _write_beats(tmp_path)
    _argv(monkeypatch, "--character", "foxy", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir))
    assert gs.main() == 2


def test_main_invalid_slug_exits_5(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    beats = _write_beats(tmp_path)
    _argv(monkeypatch, "--character", "ghost", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir))
    assert gs.main() == 5


def test_main_too_many_images_exits_4(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    beats = _write_beats(tmp_path, n=99)
    _argv(monkeypatch, "--character", "foxy", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir), "--yes")
    assert gs.main() == 4  # exceeds max_images_per_run without --allow-large


def test_main_happy_path_exits_0(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    beats = _write_beats(tmp_path, n=2)
    out = tmp_path / "o"
    fake_client = MagicMock()
    fake_client.generate.return_value = GeneratedImage(png_bytes=b"X")
    _argv(monkeypatch, "--character", "foxy", "--beats", str(beats),
          "--out", str(out), "--library", str(sample_character_dir), "--yes")
    with patch("scripts.illustration.generate_slideshow.OpenAIImageClient", return_value=fake_client):
        assert gs.main() == 0
    assert (out / "01-foxy.png").exists()


def test_main_quota_exits_3(monkeypatch, tmp_path, sample_character_dir):
    from scripts.common.errors import QuotaExceeded
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    beats = _write_beats(tmp_path, n=2)
    fake_client = MagicMock()
    fake_client.generate.side_effect = QuotaExceeded("billing")
    _argv(monkeypatch, "--character", "foxy", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir), "--yes")
    with patch("scripts.illustration.generate_slideshow.OpenAIImageClient", return_value=fake_client):
        assert gs.main() == 3


def test_main_preview_uses_builtin_scenes(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    out = tmp_path / "preview"
    fake_client = MagicMock()
    fake_client.generate.return_value = GeneratedImage(png_bytes=b"P")
    _argv(monkeypatch, "--character", "foxy", "--preview",
          "--out", str(out), "--library", str(sample_character_dir), "--yes")
    with patch("scripts.illustration.generate_slideshow.OpenAIImageClient", return_value=fake_client):
        assert gs.main() == 0
    # preview_count defaults to 3 in config, but with no config file present defaults to len(PREVIEW_SCENES)
    assert fake_client.generate.call_count >= 1
