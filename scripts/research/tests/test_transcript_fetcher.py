"""Tests for the transcript fetcher wrapper."""
from __future__ import annotations

from unittest.mock import MagicMock

from scripts.research.transcript_fetcher import fetch_transcript


class TestFetchTranscript:
    def test_success_returns_joined_text(self) -> None:
        api = MagicMock()
        api.get_transcript.return_value = [
            {"text": "hello"},
            {"text": "world"},
            {"text": "this is a test"},
        ]
        text, source = fetch_transcript("abc", ["en"], api=api)
        assert text == "hello world this is a test"
        assert source == "captions"
        api.get_transcript.assert_called_once_with("abc", languages=["en"])

    def test_failure_returns_none_none(self) -> None:
        api = MagicMock()
        api.get_transcript.side_effect = Exception("no transcript available")
        text, source = fetch_transcript("abc", ["en"], api=api)
        assert text is None
        assert source == "none"

    def test_empty_transcript_returns_empty_string_captions(self) -> None:
        # if the API returns an empty list, that's technically "captions present, empty"
        api = MagicMock()
        api.get_transcript.return_value = []
        text, source = fetch_transcript("abc", ["en"], api=api)
        assert text == ""
        assert source == "captions"
