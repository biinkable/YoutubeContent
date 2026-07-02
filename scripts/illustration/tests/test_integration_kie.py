"""Live kie.ai GPT-image-2 test. Skipped unless KIE_API_KEY is set. Spends a small amount."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.illustration.image_result import GeneratedImage
from scripts.illustration.kie_image import KieImageClient

_API_KEY = os.environ.get("KIE_API_KEY", "").strip()

pytestmark = pytest.mark.skipif(
    not _API_KEY, reason="KIE_API_KEY not set; skipping live kie.ai image-generation test"
)


def test_generate_one_real_image(tmp_path: Path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    client = KieImageClient(_API_KEY)
    out = client.generate(
        prompt="A simple round mascot standing, flat cartoon, plain background.",
        reference_images=[ref],
        size="1536x1024",
        quality="medium",
    )
    assert isinstance(out, GeneratedImage)
    assert isinstance(out.png_bytes, bytes) and len(out.png_bytes) > 1000
