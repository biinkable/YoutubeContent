"""Thin, dependency-injectable wrapper over the OpenAI GPT-image-2 API."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.common.errors import (
    ApiError,
    QuotaExceeded,
    RefusedByPolicy,
    TransientError,
    retry_on_transient,
)

_MODEL = "gpt-image-2"
_REFERENCE_CAP = 16


@dataclass(frozen=True)
class GeneratedImage:
    png_bytes: bytes


def _classify(exc: Exception) -> str:
    """Classify an SDK exception by duck-typed attributes.

    Returns one of: "quota" | "refused" | "transient" | "fatal".
    """
    code = (getattr(exc, "code", None) or "")
    status = getattr(exc, "status_code", None)
    msg = str(exc).lower()
    if code == "insufficient_quota" or "insufficient_quota" in msg or "billing" in msg:
        return "quota"
    if (
        code in ("content_policy_violation", "moderation_blocked")
        or "content policy" in msg
        or "safety" in msg
    ):
        return "refused"
    if status is None or status == 429 or status >= 500:
        return "transient"
    return "fatal"


class OpenAIImageClient:
    def __init__(self, api_key: str, *, client: Any | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)

    def generate(
        self,
        *,
        prompt: str,
        reference_images: list[Path],
        size: str = "1536x1024",
        quality: str = "high",
    ) -> GeneratedImage:
        refs = reference_images[:_REFERENCE_CAP]

        def _call():
            handles = [open(p, "rb") for p in refs]
            try:
                return self._client.images.edit(
                    model=_MODEL,
                    image=handles,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=1,
                )
            except Exception as e:  # classify and re-raise as our taxonomy
                kind = _classify(e)
                if kind == "quota":
                    raise QuotaExceeded(str(e)) from e
                if kind == "refused":
                    raise RefusedByPolicy(str(e)) from e
                if kind == "transient":
                    raise TransientError(str(e)) from e
                raise
            finally:
                for h in handles:
                    h.close()

        resp = retry_on_transient(_call)
        b64 = getattr(resp.data[0], "b64_json", None)
        if not b64:
            raise ApiError("OpenAI image response contained no b64_json data")
        return GeneratedImage(png_bytes=base64.b64decode(b64))
