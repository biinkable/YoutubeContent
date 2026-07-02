from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.common.errors import ApiError, QuotaExceeded, RefusedByPolicy
from scripts.illustration.image_result import GeneratedImage
from scripts.illustration.kie_image import (
    KieImageClient,
    _classify_message,
    _extract_result_url,
)


class FakeResp:
    def __init__(self, *, status_code=200, json_body=None, content=b""):
        self.status_code = status_code
        self._json = json_body
        self.content = content

    def json(self):
        if self._json is None:
            raise ValueError("no JSON body")
        return self._json


class FakeSession:
    """Consumes queued responses in order. `request` handles POST + GET JSON calls;
    `get` handles the final image download."""

    def __init__(self, request_queue, get_queue=None):
        self._requests = list(request_queue)
        self._gets = list(get_queue or [])
        self.request_calls = []
        self.get_calls = []

    def request(self, method, url, **kwargs):
        self.request_calls.append((method, url, kwargs))
        item = self._requests.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        item = self._gets.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _ref(tmp_path: Path, name="01.webp") -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x89PNG\r\n\x1a\n-ref-bytes")
    return p


def _ok(json_body):
    return FakeResp(json_body=json_body)


def _upload_ok(url):
    return _ok({"code": 200, "msg": "success", "data": {"downloadUrl": url}})


def _create_ok(task_id="task_1"):
    return _ok({"code": 200, "msg": "success", "data": {"taskId": task_id}})


def _record(state, **data):
    return _ok({"code": 200, "msg": "success", "data": {"state": state, **data}})


def _success_record(urls):
    return _record("success", resultJson=json.dumps({"resultUrls": urls}))


def _client(session, **kw):
    return KieImageClient("kie-test", session=session, poll_interval=1.0,
                          poll_timeout=30.0, sleep=lambda _s: None, **kw)


def test_generate_happy_path(tmp_path: Path):
    session = FakeSession(
        request_queue=[
            _upload_ok("https://tmp/ref1.png"),          # upload
            _create_ok("task_abc"),                       # createTask
            _record("generating"),                        # poll 1
            _success_record(["https://out/img.png"]),     # poll 2 -> done
        ],
        get_queue=[FakeResp(content=b"IMAGE-BYTES")],     # download
    )
    out = _client(session).generate(prompt="draw the blob", reference_images=[_ref(tmp_path)])
    assert isinstance(out, GeneratedImage)
    assert out.png_bytes == b"IMAGE-BYTES"

    # createTask payload was correctly shaped
    create = next(c for c in session.request_calls if c[1].endswith("/jobs/createTask"))
    body = create[2]["json"]
    assert body["model"] == "gpt-image-2-image-to-image"
    assert body["input"]["input_urls"] == ["https://tmp/ref1.png"]
    assert body["input"]["aspect_ratio"] == "3:2"   # 1536x1024 default
    assert body["input"]["resolution"] == "2K"      # quality high default
    # auth header present
    assert create[2]["headers"]["Authorization"] == "Bearer kie-test"


def test_size_and_quality_mapping(tmp_path: Path):
    session = FakeSession(
        request_queue=[_upload_ok("u"), _create_ok(), _success_record(["o"])],
        get_queue=[FakeResp(content=b"X")],
    )
    _client(session).generate(
        prompt="x", reference_images=[_ref(tmp_path)], size="1024x1024", quality="medium"
    )
    create = next(c for c in session.request_calls if c[1].endswith("/jobs/createTask"))
    body = create[2]["json"]
    assert body["input"]["aspect_ratio"] == "1:1"
    assert body["input"]["resolution"] == "1K"


def test_reference_images_capped_at_16(tmp_path: Path):
    refs = [_ref(tmp_path, f"{i:02d}.webp") for i in range(17)]
    session = FakeSession(
        request_queue=[_upload_ok(f"https://u/{i}") for i in range(16)]
        + [_create_ok(), _success_record(["o"])],
        get_queue=[FakeResp(content=b"X")],
    )
    _client(session).generate(prompt="x", reference_images=refs)
    upload_calls = [c for c in session.request_calls if c[1].endswith("/file-base64-upload")]
    assert len(upload_calls) == 16
    create = next(c for c in session.request_calls if c[1].endswith("/jobs/createTask"))
    assert len(create[2]["json"]["input"]["input_urls"]) == 16


def test_task_failure_quota_maps_to_quota_exceeded(tmp_path: Path):
    session = FakeSession(
        request_queue=[
            _upload_ok("u"), _create_ok(),
            _record("fail", failCode="402", failMsg="Insufficient credits, please recharge"),
        ],
    )
    with pytest.raises(QuotaExceeded):
        _client(session).generate(prompt="x", reference_images=[_ref(tmp_path)])


def test_task_failure_policy_maps_to_refused(tmp_path: Path):
    session = FakeSession(
        request_queue=[
            _upload_ok("u"), _create_ok(),
            _record("fail", failCode="400", failMsg="Rejected by content moderation policy"),
        ],
    )
    with pytest.raises(RefusedByPolicy):
        _client(session).generate(prompt="x", reference_images=[_ref(tmp_path)])


def test_transient_http_5xx_is_retried(tmp_path: Path):
    session = FakeSession(
        request_queue=[
            FakeResp(status_code=503, json_body={}),   # upload attempt 1 -> transient
            _upload_ok("u"),                            # upload attempt 2 -> ok
            _create_ok(),
            _success_record(["o"]),
        ],
        get_queue=[FakeResp(content=b"OK")],
    )
    with patch("scripts.common.errors.time.sleep"):
        out = _client(session).generate(prompt="x", reference_images=[_ref(tmp_path)])
    assert out.png_bytes == b"OK"


def test_poll_timeout_raises_apierror(tmp_path: Path):
    session = FakeSession(
        request_queue=[_upload_ok("u"), _create_ok()]
        + [_record("generating") for _ in range(5)],
    )
    client = KieImageClient("k", session=session, poll_interval=3.0, poll_timeout=5.0,
                            sleep=lambda _s: None)
    with pytest.raises(ApiError):
        client.generate(prompt="x", reference_images=[_ref(tmp_path)])


def test_upload_without_download_url_raises(tmp_path: Path):
    session = FakeSession(request_queue=[_ok({"code": 200, "data": {}})])
    with pytest.raises(ApiError):
        _client(session).generate(prompt="x", reference_images=[_ref(tmp_path)])


def test_envelope_error_code_quota(tmp_path: Path):
    session = FakeSession(
        request_queue=[_ok({"code": 402, "msg": "insufficient balance"})]
    )
    with pytest.raises(QuotaExceeded):
        _client(session).generate(prompt="x", reference_images=[_ref(tmp_path)])


def test_classify_message():
    assert _classify_message("402", "insufficient credits") == "quota"
    assert _classify_message("", "content policy violation") == "refused"
    assert _classify_message("", "service temporarily unavailable") == "transient"
    assert _classify_message("", "some other error") == "fatal"


def test_extract_result_url_variants():
    assert _extract_result_url({"resultJson": '{"resultUrls": ["a", "b"]}'}) == "a"
    assert _extract_result_url({"resultJson": {"resultUrls": ["x"]}}) == "x"
    with pytest.raises(ApiError):
        _extract_result_url({"resultJson": '{"resultUrls": []}'})
    with pytest.raises(ApiError):
        _extract_result_url({})
