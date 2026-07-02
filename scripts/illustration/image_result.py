"""Shared result type returned by every image-generation provider client."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedImage:
    """The raw bytes of one generated image (PNG for OpenAI; PNG/JPEG for kie.ai)."""

    png_bytes: bytes
