from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.illustration import generate_slideshow as gs
from scripts.illustration.openai_image import GeneratedImage


def test_script_runs_as_direct_file_invocation(tmp_path):
    """Regression: the skill documents `python scripts/illustration/generate_slideshow.py ...`.
    Python only puts the script's own directory on sys.path, so importing the `scripts`
    namespace package used to fail (ModuleNotFoundError). The module now inserts the repo
    root onto sys.path; verify the documented invocation works with no PYTHONPATH and from
    an unrelated working directory."""
    script = Path(gs.__file__).resolve()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)  # don't let an inherited path mask the bug
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,  # neutral CWD proves the fix is location-independent
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "usage:" in proc.stdout.lower()


def _write_beats(tmp_path: Path, n=2) -> Path:
    lines = ["beats:"]
    for i in range(1, n + 1):
        lines += [f"  - id: {i}", f"    scene: scene {i}"]
    p = tmp_path / "beats.yaml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["prog", *args])


# --- OpenAI provider path (pinned with --provider openai) --------------------


def test_main_missing_key_exits_2(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    beats = _write_beats(tmp_path)
    _argv(monkeypatch, "--provider", "openai", "--character", "foxy", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir))
    assert gs.main() == 2


def test_main_invalid_slug_exits_5(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    beats = _write_beats(tmp_path)
    _argv(monkeypatch, "--provider", "openai", "--character", "ghost", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir))
    assert gs.main() == 5


def test_main_too_many_images_exits_4(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    beats = _write_beats(tmp_path, n=99)
    _argv(monkeypatch, "--provider", "openai", "--character", "foxy", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir), "--yes")
    assert gs.main() == 4  # exceeds max_images_per_run without --allow-large


def test_main_happy_path_exits_0(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    beats = _write_beats(tmp_path, n=2)
    out = tmp_path / "o"
    fake_client = MagicMock()
    fake_client.generate.return_value = GeneratedImage(png_bytes=b"X")
    _argv(monkeypatch, "--provider", "openai", "--character", "foxy", "--beats", str(beats),
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
    _argv(monkeypatch, "--provider", "openai", "--character", "foxy", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir), "--yes")
    with patch("scripts.illustration.generate_slideshow.OpenAIImageClient", return_value=fake_client):
        assert gs.main() == 3


def test_main_preview_uses_builtin_scenes(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    out = tmp_path / "preview"
    fake_client = MagicMock()
    fake_client.generate.return_value = GeneratedImage(png_bytes=b"P")
    _argv(monkeypatch, "--provider", "openai", "--character", "foxy", "--preview",
          "--out", str(out), "--library", str(sample_character_dir), "--yes")
    with patch("scripts.illustration.generate_slideshow.OpenAIImageClient", return_value=fake_client):
        assert gs.main() == 0
    assert fake_client.generate.call_count >= 1


# --- kie.ai provider path (the new default) ---------------------------------


def test_main_kie_missing_key_exits_2(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("KIE_API_KEY", raising=False)
    beats = _write_beats(tmp_path)
    # no --provider -> defaults to kie from config
    _argv(monkeypatch, "--character", "foxy", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir))
    assert gs.main() == 2


def test_main_kie_happy_path_exits_0(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("KIE_API_KEY", "kie-test")
    beats = _write_beats(tmp_path, n=2)
    out = tmp_path / "o"
    fake_client = MagicMock()
    fake_client.generate.return_value = GeneratedImage(png_bytes=b"K")
    _argv(monkeypatch, "--provider", "kie", "--character", "foxy", "--beats", str(beats),
          "--out", str(out), "--library", str(sample_character_dir), "--yes")
    with patch("scripts.illustration.generate_slideshow.KieImageClient", return_value=fake_client):
        assert gs.main() == 0
    assert (out / "01-foxy.png").read_bytes() == b"K"


def test_main_kie_apierror_exits_6(monkeypatch, tmp_path, sample_character_dir):
    from scripts.common.errors import ApiError
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("KIE_API_KEY", "kie-test")
    beats = _write_beats(tmp_path, n=1)
    fake_client = MagicMock()
    fake_client.generate.side_effect = ApiError("task did not finish within 300s")
    _argv(monkeypatch, "--provider", "kie", "--character", "foxy", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir), "--yes")
    with patch("scripts.illustration.generate_slideshow.KieImageClient", return_value=fake_client):
        assert gs.main() == 6


def test_main_unknown_provider_exits_5(monkeypatch, tmp_path, sample_character_dir):
    monkeypatch.setattr("scripts.illustration.generate_slideshow.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(
        "scripts.illustration.generate_slideshow._load_defaults",
        lambda: {"provider": "bogus", "quality": "high", "size": "1536x1024",
                 "preview_count": 3, "max_images_per_run": 12},
    )
    beats = _write_beats(tmp_path)
    _argv(monkeypatch, "--character", "foxy", "--beats", str(beats),
          "--out", str(tmp_path / "o"), "--library", str(sample_character_dir))
    assert gs.main() == 5
