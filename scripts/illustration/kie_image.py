"""Dependency-injectable client for kie.ai's GPT-image-2 (async task API).

kie.ai is a cheaper gateway to GPT-image-2. Unlike OpenAI's SDK, it is an
asynchronous REST flow with a different shape, so the extra steps live here
behind the same ``generate()`` interface the OpenAI client exposes:

    1. upload each local reference image (base64)  -> a temporary URL
    2. POST /api/v1/jobs/createTask (image-to-image) -> a taskId
    3. GET  /api/v1/jobs/recordInfo?taskId=...       -> poll until success/fail
    4. download the result URL                       -> image bytes

Docs: https://docs.kie.ai/market/gpt/gpt-image-2-image-to-image
"""
from __future__ import annotations

import base64
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Callable

from scripts.common.errors import (
    ApiError,
    QuotaExceeded,
    RefusedByPolicy,
    TransientError,
    retry_on_transient,
)
from scripts.illustration.image_result import GeneratedImage

__all__ = ["GeneratedImage", "KieImageClient"]

_BASE_URL = "https://api.kie.ai"
_UPLOAD_PATH = "/api/file-base64-upload"
_CREATE_PATH = "/api/v1/jobs/createTask"
_RECORD_PATH = "/api/v1/jobs/recordInfo"
_MODEL = "gpt-image-2-image-to-image"
_REFERENCE_CAP = 16  # kie.ai accepts up to 16 input_urls

_STATE_SUCCESS = "success"
_STATE_FAIL = "fail"

# Our size knob (WxH) -> kie.ai aspect_ratio. Unknown sizes fall back to "auto".
_ASPECT_BY_SIZE: dict[str, str] = {
    "1536x1024": "3:2",
    "1024x1024": "1:1",
    "1024x1536": "2:3",
    "1792x1024": "16:9",
    "1024x1792": "9:16",
}
# Our quality knob -> kie.ai resolution. kie prices by resolution, not "quality".
_RESOLUTION_BY_QUALITY: dict[str, str] = {"high": "2K", "medium": "1K"}


def _classify_message(code: str, msg: str) -> str:
    """Classify a kie.ai error (envelope code/msg or task failCode/failMsg).

    Returns one of: "quota" | "refused" | "transient" | "fatal".
    """
    blob = f"{code or ''} {msg or ''}".lower()
    if any(k in blob for k in ("insufficient", "quota", "billing", "balance",
                               "credit", "payment", "arrears", "recharge", "402")):
        return "quota"
    if any(k in blob for k in ("policy", "moderation", "safety", "nsfw",
                               "prohibited", "sensitive", "violat", "blocked")):
        return "refused"
    if any(k in blob for k in ("timeout", "temporar", "unavailable", "try again",
                               "rate limit", "429", "500", "502", "503", "504",
                               "busy", "overload")):
        return "transient"
    return "fatal"


def _raise_for_kind(kind: str, message: str) -> None:
    if kind == "quota":
        raise QuotaExceeded(message)
    if kind == "refused":
        raise RefusedByPolicy(message)
    if kind == "transient":
        raise TransientError(message)
    raise ApiError(message)


class KieImageClient:
    """Generate images via kie.ai's GPT-image-2 image-to-image endpoint.

    ``session`` is any object exposing requests-style ``request(...)`` and
    ``get(...)`` returning objects with ``.status_code``, ``.json()`` and
    ``.content``; inject a fake in tests. ``sleep`` is injected so the poll
    loop doesn't actually wait under test.
    """

    def __init__(
        self,
        api_key: str,
        *,
        session: Any | None = None,
        base_url: str = _BASE_URL,
        poll_interval: float = 3.0,
        poll_timeout: float = 300.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        self._sleep = sleep
        if session is not None:
            self._session = session
        else:
            import requests

            self._session = requests.Session()

    # -- HTTP helpers -----------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def _call_json(self, method: str, path: str, *, json_body: Any | None = None,
                   params: dict | None = None) -> dict:
        """Call a kie.ai JSON endpoint, retrying transient failures.

        Raises the mapped taxonomy error on an HTTP or envelope-level failure.
        Task-level failures (``data.state == "fail"``) are NOT handled here —
        they come back as a normal 200 envelope and are inspected by the poller.
        """
        url = self._base_url + path

        def _do() -> dict:
            try:
                resp = self._session.request(
                    method, url, headers=self._auth_headers(),
                    json=json_body, params=params, timeout=60,
                )
            except Exception as e:  # network/socket failure -> retryable
                raise TransientError(f"network error calling {path}: {e}") from e
            status = int(getattr(resp, "status_code", 200))
            if status == 429 or status >= 500:
                raise TransientError(f"{path} returned HTTP {status}")
            try:
                body = resp.json()
            except Exception as e:
                raise ApiError(f"{path} returned a non-JSON body (HTTP {status})") from e
            code = body.get("code")
            if status >= 400 or (code is not None and str(code) != "200"):
                _raise_for_kind(
                    _classify_message(str(code), str(body.get("msg", ""))),
                    f"{path} failed (HTTP {status}, code={code}): {body.get('msg')}",
                )
            return body

        return retry_on_transient(_do)

    # -- pipeline steps ---------------------------------------------------

    def _upload(self, path: Path) -> str:
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        payload = {
            "base64Data": f"data:{mime};base64,{b64}",
            "uploadPath": "images/youtubecontent",
            "fileName": path.name,
        }
        body = self._call_json("POST", _UPLOAD_PATH, json_body=payload)
        url = (body.get("data") or {}).get("downloadUrl")
        if not url:
            raise ApiError(f"upload of {path.name} returned no downloadUrl")
        return url

    def _create_task(self, *, prompt: str, input_urls: list[str], aspect_ratio: str,
                     resolution: str) -> str:
        payload = {
            "model": _MODEL,
            "input": {
                "prompt": prompt,
                "input_urls": input_urls,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
            },
        }
        body = self._call_json("POST", _CREATE_PATH, json_body=payload)
        task_id = (body.get("data") or {}).get("taskId")
        if not task_id:
            raise ApiError("createTask returned no taskId")
        return task_id

    def _poll(self, task_id: str) -> str:
        """Poll until the task succeeds (return the result URL) or fails/times out."""
        elapsed = 0.0
        while True:
            data = self._call_json("GET", _RECORD_PATH, params={"taskId": task_id}).get("data") or {}
            state = str(data.get("state", "")).lower()
            if state == _STATE_SUCCESS:
                return _extract_result_url(data)
            if state == _STATE_FAIL:
                _raise_for_kind(
                    _classify_message(str(data.get("failCode", "")), str(data.get("failMsg", ""))),
                    f"task {task_id} failed: {data.get('failCode')} {data.get('failMsg')}",
                )
            if elapsed >= self._poll_timeout:
                raise ApiError(
                    f"task {task_id} did not finish within {self._poll_timeout:.0f}s "
                    f"(last state: {state or 'unknown'})"
                )
            self._sleep(self._poll_interval)
            elapsed += self._poll_interval

    def _download(self, url: str) -> bytes:
        def _do() -> bytes:
            try:
                resp = self._session.get(url, timeout=120)
            except Exception as e:
                raise TransientError(f"downloading result failed: {e}") from e
            status = int(getattr(resp, "status_code", 200))
            if status == 429 or status >= 500:
                raise TransientError(f"result download returned HTTP {status}")
            if status >= 400:
                raise ApiError(f"result download returned HTTP {status}")
            content = getattr(resp, "content", b"")
            if not content:
                raise ApiError("result download returned empty content")
            return content

        return retry_on_transient(_do)

    # -- public interface (mirrors OpenAIImageClient) ---------------------

    def generate(
        self,
        *,
        prompt: str,
        reference_images: list[Path],
        size: str = "1536x1024",
        quality: str = "high",
    ) -> GeneratedImage:
        refs = reference_images[:_REFERENCE_CAP]
        input_urls = [self._upload(p) for p in refs]
        task_id = self._create_task(
            prompt=prompt,
            input_urls=input_urls,
            aspect_ratio=_ASPECT_BY_SIZE.get(size, "auto"),
            resolution=_RESOLUTION_BY_QUALITY.get(quality, "1K"),
        )
        result_url = self._poll(task_id)
        return GeneratedImage(png_bytes=self._download(result_url))


def _extract_result_url(data: dict) -> str:
    raw = data.get("resultJson")
    if not raw:
        raise ApiError("successful task carried no resultJson")
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        raise ApiError(f"could not parse resultJson: {e}") from e
    urls = (parsed or {}).get("resultUrls") or []
    if not urls:
        raise ApiError("resultJson carried no resultUrls")
    return urls[0]
