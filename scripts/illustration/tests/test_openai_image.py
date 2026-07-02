from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.common.errors import QuotaExceeded, RefusedByPolicy, TransientError
from scripts.illustration.openai_image import (
    GeneratedImage,
    OpenAIImageClient,
    _classify,
)


class FakeExc(Exception):
    def __init__(self, message="", code=None, status_code=None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def test_classify_quota():
    assert _classify(FakeExc(code="insufficient_quota")) == "quota"
    assert _classify(FakeExc("You exceeded your current billing")) == "quota"


def test_classify_refused():
    assert _classify(FakeExc(code="content_policy_violation")) == "refused"
    assert _classify(FakeExc("request rejected by safety system")) == "refused"


def test_classify_transient():
    assert _classify(FakeExc(status_code=500)) == "transient"
    assert _classify(FakeExc(status_code=429)) == "transient"
    assert _classify(FakeExc(status_code=None)) == "transient"


def test_classify_fatal():
    assert _classify(FakeExc(status_code=400)) == "fatal"


def _fake_response(png_bytes: bytes):
    resp = MagicMock()
    resp.data = [MagicMock(b64_json=base64.b64encode(png_bytes).decode("ascii"))]
    return resp


def _refs(tmp_path: Path) -> list[Path]:
    p = tmp_path / "ref.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n-ref")
    return [p]


def test_generate_returns_png_bytes(tmp_path: Path):
    sdk = MagicMock()
    sdk.images.edit.return_value = _fake_response(b"the-image-bytes")
    client = OpenAIImageClient("key", client=sdk)
    out = client.generate(prompt="draw", reference_images=_refs(tmp_path))
    assert isinstance(out, GeneratedImage)
    assert out.png_bytes == b"the-image-bytes"
    _, kwargs = sdk.images.edit.call_args
    assert kwargs["model"] == "gpt-image-2"
    assert kwargs["prompt"] == "draw"
    assert kwargs["size"] == "1536x1024"
    assert kwargs["quality"] == "high"
    assert kwargs["n"] == 1


def test_generate_maps_quota(tmp_path: Path):
    sdk = MagicMock()
    sdk.images.edit.side_effect = FakeExc(code="insufficient_quota")
    client = OpenAIImageClient("key", client=sdk)
    with pytest.raises(QuotaExceeded):
        client.generate(prompt="x", reference_images=_refs(tmp_path))


def test_generate_maps_refusal(tmp_path: Path):
    sdk = MagicMock()
    sdk.images.edit.side_effect = FakeExc(code="content_policy_violation")
    client = OpenAIImageClient("key", client=sdk)
    with pytest.raises(RefusedByPolicy):
        client.generate(prompt="x", reference_images=_refs(tmp_path))


def test_generate_retries_transient_then_succeeds(tmp_path: Path):
    sdk = MagicMock()
    sdk.images.edit.side_effect = [FakeExc(status_code=503), _fake_response(b"ok")]
    client = OpenAIImageClient("key", client=sdk)
    with patch("scripts.common.errors.time.sleep"):
        out = client.generate(prompt="x", reference_images=_refs(tmp_path))
    assert out.png_bytes == b"ok"
    assert sdk.images.edit.call_count == 2
