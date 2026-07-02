# Character Illustration Subsystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable character library and a GPT-image-2 slideshow generator that produces one 16:9 illustration per script beat, keeping a chosen character consistent across frames.

**Architecture:** Mirrors the already-built research subsystem. Python modules under `scripts/illustration/` do the work (an OpenAI image client, a character library, a slideshow generator with `run()`/`main()`); a Claude Skill under `skills/illustration/` drives the interactive add/select/preview/generate/review flow. A new shared `scripts/common/errors.py` provides a retry/error taxonomy reused by the new client. Artifacts live as files under `characters/` and `outputs/<run-id>/`.

**Tech Stack:** Python 3.11+ (host has 3.14.5), `openai` SDK, PyYAML, python-dotenv, pytest. GPT-image-2 image model via the OpenAI Images API. Tests mock the OpenAI SDK; one live integration test skips without `OPENAI_API_KEY`.

## Global Constraints

- Python 3.11+; every module starts with `from __future__ import annotations`.
- Use `pathlib.Path` for all filesystem paths.
- Run pytest as `python -m pytest ...` from the project root. After Task 1 adds `pyproject.toml` with `pythonpath = ["."]`, imports of `scripts.*` resolve regardless of cwd. Do NOT create `scripts/__init__.py` (namespace package).
- TDD required for all code tasks: write the failing test, run it to see it fail, implement, run to green, commit.
- All OpenAI API calls are dependency-injected and MOCKED in unit tests — no network, no spend, output pristine (no warnings).
- Image output is 16:9 landscape, size string `"1536x1024"`. Quality is `"high"` (default) or `"medium"`.
- Cost estimate constants (USD/image): `{"high": 0.17, "medium": 0.04}`.
- Exit codes for the CLI: `0` success; `2` missing `OPENAI_API_KEY`; `3` quota/billing exhausted; `4` image count exceeds `max_images_per_run` without `--allow-large`; `5` invalid character slug or empty beats.
- Reference images per generation are capped at 16 (GPT-image-2 limit); extras are dropped and logged, never silently.
- Content-policy refusals are per-frame (recorded in the manifest, run continues); quota errors are terminal (abort run).
- Commit messages use conventional prefixes (`feat:`, `test:`, `chore:`, `docs:`, `fix:`), scope `(illustration)` or `(common)` where apt.
- The `characters/` library is tracked in git (user's own data, small PNGs) — it is NOT gitignored. `outputs/` remains gitignored (already configured).
- Do NOT modify the existing `scripts/research/` modules — the shared error taxonomy is adopted by NEW code only.

---

### Task 1: Groundwork, shared config, and package skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `scripts/illustration/__init__.py` (empty)
- Create: `scripts/illustration/tests/__init__.py` (empty)
- Create: `scripts/illustration/tests/conftest.py`
- Create: `scripts/illustration/requirements.txt`
- Create: `config/illustration-defaults.yaml`
- Create: `characters/.gitkeep` (empty)
- Modify: `.env.example` (add `OPENAI_API_KEY` line)

**Interfaces:**
- Consumes: nothing (setup task).
- Produces: the importable `scripts.illustration` test package; `pyproject.toml` making `scripts.*` importable from any cwd; a `sample_character_dir` pytest fixture (see Step 5) for later tasks.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["scripts"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Create the package skeleton files**

Create empty `scripts/illustration/__init__.py` and `scripts/illustration/tests/__init__.py` (zero bytes each). Do NOT create `scripts/__init__.py`.

- [ ] **Step 3: Create `scripts/illustration/requirements.txt`**

```text
openai>=1.50.0
PyYAML>=6.0.2
python-dotenv>=1.0.1
pytest>=8.3.0
```

- [ ] **Step 4: Create `config/illustration-defaults.yaml`**

```yaml
# Defaults for the illustration subsystem. Override per-run via CLI flags.
quality: high            # high | medium
size: "1536x1024"        # 16:9 landscape (GPT-image-2)
preview_count: 3         # sample frames generated when adding a new character
max_images_per_run: 12   # guardrail; exceeding requires explicit confirmation
```

- [ ] **Step 5: Create `scripts/illustration/tests/conftest.py`**

```python
"""Shared pytest fixtures for illustration subsystem tests."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_character_dir(tmp_path: Path) -> Path:
    """A library dir containing one character 'foxy' with two reference images."""
    lib = tmp_path / "characters"
    ref = lib / "foxy" / "reference"
    ref.mkdir(parents=True)
    (ref / "01.png").write_bytes(b"\x89PNG\r\n\x1a\n-fake-1")
    (ref / "02.png").write_bytes(b"\x89PNG\r\n\x1a\n-fake-2")
    (lib / "foxy" / "character.md").write_text(
        "A round orange fox mascot with a blue scarf, flat 2D cartoon style, cheerful.",
        encoding="utf-8",
    )
    (lib / "foxy" / "meta.yaml").write_text(
        "slug: foxy\ndisplay_name: Foxy\ncreated_at: '2026-07-02T00:00:00Z'\nnotes: ''\n",
        encoding="utf-8",
    )
    return lib
```

- [ ] **Step 6: Add the OpenAI key to `.env.example`**

Append these two lines to `.env.example` (keep the existing YouTube lines):

```text
# Get a paid key at https://platform.openai.com/api-keys (used by the illustration subsystem / GPT-image-2).
OPENAI_API_KEY=
```

- [ ] **Step 7: Install dependencies and verify pytest runs**

Run from project root:
```bash
python -m pip install -r scripts/illustration/requirements.txt
python -m pytest scripts -q
```
Expected: the existing 44 research tests still pass, 1 skipped, and the new empty illustration test package is collected without error. If a dependency fails to install on Python 3.14, STOP and report BLOCKED with the exact pip error.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml scripts/illustration config/illustration-defaults.yaml characters/.gitkeep .env.example
git commit -m "chore(illustration): scaffold package, shared config, pyproject"
```

---

### Task 2: Shared error taxonomy and retry helper

**Files:**
- Create: `scripts/common/__init__.py` (empty)
- Create: `scripts/common/errors.py`
- Test: `scripts/common/tests/__init__.py` (empty), `scripts/common/tests/test_errors.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class ApiError(Exception)`, `class TransientError(ApiError)`, `class QuotaExceeded(ApiError)`, `class RefusedByPolicy(ApiError)`
  - `retry_on_transient(fn, *, retries: int = 3, base_delay: float = 1.0)` — calls `fn()`, retries only on `TransientError` with exponential backoff `base_delay * 3**attempt`; re-raises any other exception immediately; re-raises the last `TransientError` after exhausting retries.

- [ ] **Step 1: Write the failing test**

Create `scripts/common/tests/__init__.py` (empty) and `scripts/common/tests/test_errors.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from scripts.common.errors import (
    ApiError,
    QuotaExceeded,
    RefusedByPolicy,
    TransientError,
    retry_on_transient,
)


def test_exception_hierarchy():
    assert issubclass(TransientError, ApiError)
    assert issubclass(QuotaExceeded, ApiError)
    assert issubclass(RefusedByPolicy, ApiError)


def test_returns_value_when_fn_succeeds():
    fn = MagicMock(return_value="ok")
    with patch("scripts.common.errors.time.sleep") as sleep:
        assert retry_on_transient(fn) == "ok"
    assert fn.call_count == 1
    assert sleep.call_count == 0


def test_retries_transient_then_succeeds():
    fn = MagicMock(side_effect=[TransientError("x"), TransientError("x"), "ok"])
    with patch("scripts.common.errors.time.sleep") as sleep:
        assert retry_on_transient(fn) == "ok"
    assert fn.call_count == 3
    assert sleep.call_count == 2
    sleep.assert_has_calls([call(1.0), call(3.0)])


def test_reraises_after_exhausting_retries():
    fn = MagicMock(side_effect=TransientError("boom"))
    with patch("scripts.common.errors.time.sleep") as sleep:
        with pytest.raises(TransientError):
            retry_on_transient(fn, retries=3)
    assert sleep.call_count == 3


def test_non_transient_propagates_immediately():
    fn = MagicMock(side_effect=QuotaExceeded("nope"))
    with patch("scripts.common.errors.time.sleep") as sleep:
        with pytest.raises(QuotaExceeded):
            retry_on_transient(fn)
    assert fn.call_count == 1
    assert sleep.call_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest scripts/common/tests/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.common'`

- [ ] **Step 3: Write the implementation**

Create empty `scripts/common/__init__.py`, then `scripts/common/errors.py`:

```python
"""Shared error taxonomy and retry helper for API-touching subsystems."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class ApiError(Exception):
    """Base class for external-API failures."""


class TransientError(ApiError):
    """A retryable failure (network blip, 5xx, non-quota rate limit)."""


class QuotaExceeded(ApiError):
    """Billing/quota exhausted. Terminal for the run — never retried."""


class RefusedByPolicy(ApiError):
    """The provider refused the request on content-policy grounds. Per-item, not retried."""


def retry_on_transient(
    fn: Callable[[], T], *, retries: int = 3, base_delay: float = 1.0
) -> T:
    """Call fn(), retrying only on TransientError with exponential backoff.

    Any non-TransientError propagates immediately. After exhausting retries,
    the last TransientError is re-raised.
    """
    last: TransientError | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except TransientError as e:
            if attempt >= retries:
                raise
            last = e
            time.sleep(base_delay * (3**attempt))
    raise last if last else RuntimeError("unreachable")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest scripts/common/tests/test_errors.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/common
git commit -m "feat(common): shared error taxonomy and retry_on_transient helper"
```

---

### Task 3: OpenAI GPT-image-2 client

**Files:**
- Create: `scripts/illustration/openai_image.py`
- Test: `scripts/illustration/tests/test_openai_image.py`

**Interfaces:**
- Consumes: `scripts.common.errors` (`QuotaExceeded`, `RefusedByPolicy`, `TransientError`, `retry_on_transient`).
- Produces:
  - `@dataclass(frozen=True) class GeneratedImage: png_bytes: bytes`
  - `_classify(exc) -> str` returning one of `"quota" | "refused" | "transient" | "fatal"` from duck-typed attributes (`code`, `status_code`, message).
  - `class OpenAIImageClient`: `__init__(self, api_key: str, *, client: Any | None = None)`; `generate(self, *, prompt: str, reference_images: list[Path], size: str = "1536x1024", quality: str = "high") -> GeneratedImage`. It calls `client.images.edit(model="gpt-image-2", image=[...open file handles...], prompt=prompt, size=size, quality=quality, n=1)`, wraps the call in `retry_on_transient`, classifies exceptions, and decodes `resp.data[0].b64_json` to PNG bytes.

- [ ] **Step 1: Write the failing test**

Create `scripts/illustration/tests/test_openai_image.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest scripts/illustration/tests/test_openai_image.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.illustration.openai_image'`

- [ ] **Step 3: Write the implementation**

Create `scripts/illustration/openai_image.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest scripts/illustration/tests/test_openai_image.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/illustration/openai_image.py scripts/illustration/tests/test_openai_image.py
git commit -m "feat(illustration): GPT-image-2 client with error classification and retry"
```

---

### Task 4: Character library

**Files:**
- Create: `scripts/illustration/character_library.py`
- Test: `scripts/illustration/tests/test_character_library.py`

**Interfaces:**
- Consumes: `sample_character_dir` fixture (Task 1 conftest).
- Produces:
  - `@dataclass(frozen=True) class Character: slug: str; display_name: str; reference_images: list[Path]; description: str`
  - `class CharacterNotFound(Exception)`
  - `add_character(library_dir: Path, *, slug: str, display_name: str, image_paths: list[Path], description: str, now_iso: str, notes: str = "") -> Character` — copies images into `library_dir/<slug>/reference/NN<ext>`, writes `character.md` (the description) and `meta.yaml`; returns the loaded `Character`.
  - `list_characters(library_dir: Path) -> list[dict]` — `[{"slug", "display_name"}]` sorted by slug; empty list if dir missing.
  - `load_character(library_dir: Path, slug: str) -> Character` — raises `CharacterNotFound` if the slug folder or its files are absent; `reference_images` sorted by filename.

- [ ] **Step 1: Write the failing test**

Create `scripts/illustration/tests/test_character_library.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.illustration.character_library import (
    Character,
    CharacterNotFound,
    add_character,
    list_characters,
    load_character,
)


def test_load_existing_character(sample_character_dir: Path):
    c = load_character(sample_character_dir, "foxy")
    assert isinstance(c, Character)
    assert c.slug == "foxy"
    assert c.display_name == "Foxy"
    assert "orange fox" in c.description
    assert len(c.reference_images) == 2
    assert c.reference_images[0].name == "01.png"


def test_load_missing_raises(sample_character_dir: Path):
    with pytest.raises(CharacterNotFound):
        load_character(sample_character_dir, "nope")


def test_list_characters(sample_character_dir: Path):
    assert list_characters(sample_character_dir) == [
        {"slug": "foxy", "display_name": "Foxy"}
    ]


def test_list_empty_when_dir_missing(tmp_path: Path):
    assert list_characters(tmp_path / "does-not-exist") == []


def test_add_character_copies_and_writes(tmp_path: Path):
    lib = tmp_path / "characters"
    src1 = tmp_path / "a.png"
    src2 = tmp_path / "b.jpg"
    src1.write_bytes(b"img-a")
    src2.write_bytes(b"img-b")
    c = add_character(
        lib,
        slug="robot",
        display_name="Robot",
        image_paths=[src1, src2],
        description="A boxy tin robot, matte grey, friendly.",
        now_iso="2026-07-02T12:00:00Z",
    )
    assert c.slug == "robot"
    assert (lib / "robot" / "character.md").read_text(encoding="utf-8").startswith("A boxy tin robot")
    assert (lib / "robot" / "reference" / "01.png").read_bytes() == b"img-a"
    assert (lib / "robot" / "reference" / "02.jpg").read_bytes() == b"img-b"
    # round-trips through load
    loaded = load_character(lib, "robot")
    assert loaded.display_name == "Robot"
    assert len(loaded.reference_images) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest scripts/illustration/tests/test_character_library.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.illustration.character_library'`

- [ ] **Step 3: Write the implementation**

Create `scripts/illustration/character_library.py`:

```python
"""Manage the on-disk character library (add / list / load)."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml


class CharacterNotFound(Exception):
    """Raised when a character slug is not present in the library."""


@dataclass(frozen=True)
class Character:
    slug: str
    display_name: str
    reference_images: list[Path]
    description: str


def _char_dir(library_dir: Path, slug: str) -> Path:
    return library_dir / slug


def add_character(
    library_dir: Path,
    *,
    slug: str,
    display_name: str,
    image_paths: list[Path],
    description: str,
    now_iso: str,
    notes: str = "",
) -> Character:
    cdir = _char_dir(library_dir, slug)
    ref_dir = cdir / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    for idx, src in enumerate(image_paths, start=1):
        dst = ref_dir / f"{idx:02d}{src.suffix.lower()}"
        shutil.copyfile(src, dst)
    (cdir / "character.md").write_text(description, encoding="utf-8")
    (cdir / "meta.yaml").write_text(
        yaml.safe_dump(
            {"slug": slug, "display_name": display_name, "created_at": now_iso, "notes": notes},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return load_character(library_dir, slug)


def list_characters(library_dir: Path) -> list[dict]:
    if not library_dir.is_dir():
        return []
    out: list[dict] = []
    for meta in sorted(library_dir.glob("*/meta.yaml")):
        data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
        out.append({"slug": data.get("slug", meta.parent.name), "display_name": data.get("display_name", meta.parent.name)})
    return out


def load_character(library_dir: Path, slug: str) -> Character:
    cdir = _char_dir(library_dir, slug)
    meta_path = cdir / "meta.yaml"
    desc_path = cdir / "character.md"
    ref_dir = cdir / "reference"
    if not (meta_path.is_file() and desc_path.is_file() and ref_dir.is_dir()):
        raise CharacterNotFound(f"character not found: {slug!r}")
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    refs = sorted(p for p in ref_dir.iterdir() if p.is_file())
    if not refs:
        raise CharacterNotFound(f"character {slug!r} has no reference images")
    return Character(
        slug=meta.get("slug", slug),
        display_name=meta.get("display_name", slug),
        reference_images=refs,
        description=desc_path.read_text(encoding="utf-8").strip(),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest scripts/illustration/tests/test_character_library.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/illustration/character_library.py scripts/illustration/tests/test_character_library.py
git commit -m "feat(illustration): character library add/list/load"
```

---

### Task 5: Slideshow generator core (`run`)

**Files:**
- Create: `scripts/illustration/generate_slideshow.py`
- Test: `scripts/illustration/tests/test_generate_slideshow.py`

**Interfaces:**
- Consumes: `Character` (Task 4), `OpenAIImageClient`/`GeneratedImage` (Task 3), `RefusedByPolicy`/`QuotaExceeded` (Task 2), `sample_character_dir` fixture.
- Produces:
  - `PREVIEW_SCENES: list[dict]` — 3 fixed `{"id", "scene"}` sample scenes.
  - `COST_PER_IMAGE: dict[str, float]` = `{"high": 0.17, "medium": 0.04}`.
  - `parse_beats(text: str) -> list[dict]` — parses YAML `{"beats": [{"id", "scene"}, ...]}` into the list; raises `ValueError` on empty/malformed.
  - `build_prompt(character: Character, scene: str) -> str`.
  - `estimate_cost(n: int, quality: str) -> float`.
  - `run(*, character: Character, beats: list[dict], out_dir: Path, quality: str = "high", size: str = "1536x1024", image_client, only: set[int] | None = None) -> dict` — generates images for the selected beats (all, or those in `only`), preserving prior frames from an existing `slideshow.json` for non-selected beats; writes PNGs to `out_dir` and the manifest to `out_dir.parent / "slideshow.json"`; returns the manifest dict. `RefusedByPolicy` → that frame `status="refused"`, run continues. `QuotaExceeded` propagates.

- [ ] **Step 1: Write the failing test**

Create `scripts/illustration/tests/test_generate_slideshow.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest scripts/illustration/tests/test_generate_slideshow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.illustration.generate_slideshow'`

- [ ] **Step 3: Write the implementation**

Create `scripts/illustration/generate_slideshow.py`:

```python
"""Generate one 16:9 illustration per beat for a chosen character."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from scripts.common.errors import RefusedByPolicy
from scripts.illustration.character_library import Character

COST_PER_IMAGE: dict[str, float] = {"high": 0.17, "medium": 0.04}

PREVIEW_SCENES: list[dict] = [
    {"id": 1, "scene": "standing and facing the viewer, full body, neutral pose"},
    {"id": 2, "scene": "in mid-action, gesturing with energy as if explaining something"},
    {"id": 3, "scene": "reacting with clear surprise to something just off-frame"},
]


def parse_beats(text: str) -> list[dict]:
    data = yaml.safe_load(text) or {}
    beats = data.get("beats") or []
    if not beats:
        raise ValueError("no beats found; expected a non-empty 'beats:' list")
    out: list[dict] = []
    for b in beats:
        if "id" not in b or "scene" not in b:
            raise ValueError(f"beat missing 'id' or 'scene': {b!r}")
        out.append({"id": int(b["id"]), "scene": str(b["scene"])})
    return out


def build_prompt(character: Character, scene: str) -> str:
    return (
        "A 16:9 landscape illustration. Keep this exact recurring character consistent "
        f"with the reference image(s): {character.description} "
        f"Scene: {scene}. "
        "The character is the main acting subject of the scene, not a bystander. "
        "One clear idea in the frame. Preserve the character's established art style, "
        "colors, and proportions."
    )


def estimate_cost(n: int, quality: str) -> float:
    return round(n * COST_PER_IMAGE.get(quality, COST_PER_IMAGE["high"]), 2)


def run(
    *,
    character: Character,
    beats: list[dict],
    out_dir: Path,
    quality: str = "high",
    size: str = "1536x1024",
    image_client: Any,
    only: set[int] | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir.parent / "slideshow.json"

    prior: dict[int, dict] = {}
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            prior = {f["id"]: f for f in old.get("frames", [])}
        except Exception:
            prior = {}

    refs = character.reference_images[:16]
    dropped = [str(p) for p in character.reference_images[16:]]

    frames: list[dict] = []
    for beat in beats:
        bid = beat["id"]
        selected = only is None or bid in only
        if not selected:
            frames.append(prior.get(bid, {"id": bid, "file": None, "status": "pending", "estimated_cost": 0.0}))
            continue
        fname = f"{bid:02d}-{character.slug}.png"
        fpath = out_dir / fname
        try:
            img = image_client.generate(
                prompt=build_prompt(character, beat["scene"]),
                reference_images=refs,
                size=size,
                quality=quality,
            )
        except RefusedByPolicy as e:
            frames.append({"id": bid, "file": None, "status": "refused", "reason": str(e), "estimated_cost": 0.0})
            continue
        fpath.write_bytes(img.png_bytes)
        frames.append({"id": bid, "file": fname, "status": "ok", "estimated_cost": COST_PER_IMAGE.get(quality, COST_PER_IMAGE["high"])})

    manifest = {
        "character": character.slug,
        "quality": quality,
        "size": size,
        "beats": beats,
        "frames": frames,
        "total_estimated_cost": round(sum(f.get("estimated_cost", 0.0) for f in frames), 2),
        "dropped_reference_images": dropped,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest scripts/illustration/tests/test_generate_slideshow.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/illustration/generate_slideshow.py scripts/illustration/tests/test_generate_slideshow.py
git commit -m "feat(illustration): slideshow generator core with per-frame manifest"
```

---

### Task 6: CLI (`main`), exit codes, and cost guardrail

**Files:**
- Modify: `scripts/illustration/generate_slideshow.py` (add `_parse_args`, `main`, `if __name__` block)
- Test: `scripts/illustration/tests/test_generate_slideshow_cli.py`

**Interfaces:**
- Consumes: everything in Task 5 plus `load_character`/`CharacterNotFound` (Task 4), `QuotaExceeded` (Task 2).
- Produces: `main() -> int`. Flags: `--character <slug>` (required), `--beats <path>` (optional; omitted only with `--preview`), `--out <dir>` (required), `--library <dir>` (default `characters`), `--quality high|medium`, `--preview`, `--allow-large`, `--only <comma-ids>`, `--yes`. Loads `.env` from project root, reads `OPENAI_API_KEY`. Exit codes per Global Constraints. Reads defaults from `config/illustration-defaults.yaml` when present.

- [ ] **Step 1: Write the failing test**

Create `scripts/illustration/tests/test_generate_slideshow_cli.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest scripts/illustration/tests/test_generate_slideshow_cli.py -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'main'` (and `load_dotenv`/`OpenAIImageClient` not present)

- [ ] **Step 3: Write the implementation**

Append to `scripts/illustration/generate_slideshow.py` — add these imports at the top (merge with existing imports) and the functions at the bottom:

```python
# --- add to the import block at the top of the file ---
import argparse
import os
import sys

from dotenv import load_dotenv

from scripts.common.errors import QuotaExceeded
from scripts.illustration.character_library import (
    CharacterNotFound,
    list_characters,
    load_character,
)
from scripts.illustration.openai_image import OpenAIImageClient
```

```python
# --- add at the bottom of the file ---
def _load_defaults() -> dict:
    cfg = Path(__file__).resolve().parents[2] / "config" / "illustration-defaults.yaml"
    if cfg.is_file():
        return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    return {"quality": "high", "size": "1536x1024", "preview_count": 3, "max_images_per_run": 12}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a character slideshow with GPT-image-2.")
    p.add_argument("--character", required=True, help="Character slug in the library")
    p.add_argument("--beats", type=Path, help="Path to a beats YAML file (omit with --preview)")
    p.add_argument("--out", required=True, type=Path, help="Output images dir, e.g. outputs/<run-id>/images")
    p.add_argument("--library", type=Path, default=Path("characters"), help="Character library dir")
    p.add_argument("--quality", choices=["high", "medium"], help="Override default quality")
    p.add_argument("--preview", action="store_true", help="Use built-in sample scenes")
    p.add_argument("--allow-large", action="store_true", help="Permit runs above max_images_per_run")
    p.add_argument("--only", help="Comma-separated beat ids to (re)generate")
    p.add_argument("--yes", action="store_true", help="Skip interactive confirmation (non-interactive use)")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    defaults = _load_defaults()
    quality = args.quality or defaults.get("quality", "high")
    size = defaults.get("size", "1536x1024")
    max_images = int(defaults.get("max_images_per_run", 12))
    preview_count = int(defaults.get("preview_count", 3))

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set. Copy .env.example to .env and add your key.", file=sys.stderr)
        return 2

    try:
        character = load_character(args.library, args.character)
    except CharacterNotFound as e:
        print(f"ERROR: {e}. Available: {[c['slug'] for c in list_characters(args.library)]}", file=sys.stderr)
        return 5

    if args.preview:
        beats = PREVIEW_SCENES[:preview_count]
    else:
        if not args.beats:
            print("ERROR: --beats is required unless --preview is set.", file=sys.stderr)
            return 5
        try:
            beats = parse_beats(args.beats.read_text(encoding="utf-8"))
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 5

    only = None
    if args.only:
        only = {int(x) for x in args.only.split(",") if x.strip()}

    n = len(beats) if only is None else len(only)
    print(f"Estimated cost: ${estimate_cost(n, quality)} for {n} image(s) at {quality} quality.")
    if not args.preview and n > max_images and not args.allow_large:
        print(f"ERROR: {n} images exceeds max_images_per_run={max_images}. Re-run with --allow-large to proceed.", file=sys.stderr)
        return 4

    client = OpenAIImageClient(api_key)
    try:
        run(character=character, beats=beats, out_dir=args.out, quality=quality, size=size, image_client=client, only=only)
    except QuotaExceeded as e:
        print(f"ERROR: OpenAI quota/billing exhausted.\n{e}", file=sys.stderr)
        return 3
    print(f"Wrote images to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest scripts/illustration/tests/test_generate_slideshow_cli.py -v`
Expected: PASS (6 tests). Then run the whole illustration suite: `python -m pytest scripts/illustration -v` — all green.

- [ ] **Step 5: Commit**

```bash
git add scripts/illustration/generate_slideshow.py scripts/illustration/tests/test_generate_slideshow_cli.py
git commit -m "feat(illustration): CLI, exit codes, and cost guardrail"
```

---

### Task 7: Skill files

**Files:**
- Create: `skills/illustration/SKILL.md`
- Create: `skills/illustration/references/composition.md`
- Modify: `SKILL.md` (top-level: add an illustration stage entry)

**Interfaces:**
- Consumes: the CLI from Task 6 (command shape below).
- Produces: interactive guidance only (no code).

- [ ] **Step 1: Create `skills/illustration/SKILL.md`**

```markdown
---
name: character-illustration
description: Add or select a recurring character and generate a video's 16:9 slideshow illustrations with GPT-image-2. Use when the user says "add a character", "use character X", "make the illustrations", "generate the slideshow images", or is at the image stage of a video.
---

# Character Illustration

Generate one 16:9 illustration per script beat, starring a chosen recurring character, using GPT-image-2 (reference-image generation). Each character keeps its own look.

## Prerequisites

- `OPENAI_API_KEY` must be in `.env` (paid). If missing, the CLI exits 2 — tell the user to add it.

## Adding a new character

1. Ask the user for one or more images (attached, or a file path). More angles improve consistency.
2. Look at the image(s) and write a short identity description: shape, colors, distinctive features, art-style descriptor (e.g. "flat 2D cartoon", "glossy 3D render"), and demeanor. Consult `references/composition.md`.
3. Add the character to the library by copying the images and writing `character.md` + `meta.yaml` under `characters/<slug>/` (use the `character_library` module, or write the files directly following its layout).
4. **Preview** before committing: run the generator in preview mode and show the user the sample frames:
   ```bash
   python scripts/illustration/generate_slideshow.py --character <slug> --preview --out outputs/<run-id>/preview --yes
   ```
5. If the user is happy, the character stays. If not, adjust `character.md`, swap images, or discard the folder.

## Generating a video's slideshow

1. Confirm which character to use (`list_characters`, or ask). 
2. Obtain the beats: for now, a beats YAML file (`beats:` list of `{id, scene}`) written by hand or pasted. Later this comes from the script subsystem.
3. Show the user the estimated cost and image count, get approval, then run:
   ```bash
   python scripts/illustration/generate_slideshow.py \
     --character <slug> --beats <beats.yaml> \
     --out outputs/<run-id>/images --quality high --yes
   ```
4. Review the generated set with the user. To regenerate a single frame they dislike:
   ```bash
   python scripts/illustration/generate_slideshow.py --character <slug> --beats <beats.yaml> \
     --out outputs/<run-id>/images --only 3 --yes
   ```
5. Report what was generated, any `refused` frames from the manifest (`outputs/<run-id>/slideshow.json`), and the output path.

## Stop point

This stage ends at a reviewed set of images. The video-stitch stage (audio + images → .mp4) is not built yet — do not fabricate a video. If the user asks for the finished video, say the stitching stage is still to come.
```

- [ ] **Step 2: Create `skills/illustration/references/composition.md`**

```markdown
# Composition & character-description guidance

## Writing a character's identity description (`character.md`)

Capture, in 1-3 sentences: overall shape/silhouette, primary colors, 2-3 distinctive features, an explicit art-style descriptor, and demeanor. The description rides in every generation prompt to reinforce the reference image.

Good: "A round orange fox mascot with an oversized blue scarf and tiny paws, flat 2D cartoon with thick outlines, perpetually cheerful."

Avoid: vague ("a cute animal") or style-free descriptions.

## Scene beats

Each beat is one clear idea. Keep the character the acting subject — doing the thing the narration describes, not standing beside a diagram. One action per frame; leave breathing room.

## Consistency tips

- Provide multiple reference angles when adding a character — it markedly improves cross-frame consistency.
- If frames drift, tighten `character.md` (add the most identity-defining features) and regenerate the drifting frames with `--only`.
```

- [ ] **Step 3: Add an illustration stage to the top-level `SKILL.md`**

Read the current top-level `SKILL.md`. Add an entry to its stage list/table of contents pointing at `skills/illustration/SKILL.md`, positioned after the script stage and before the (future) video stage. Keep the existing "stop at the last built stage; don't fabricate downstream" guidance intact — illustration is now a built stage; script and video remain unbuilt.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md skills/illustration
git commit -m "feat(illustration): skill and composition references"
```

---

### Task 8: README update

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing (docs).
- Produces: setup + usage docs for the illustration subsystem.

- [ ] **Step 1: Add an "Illustration subsystem" section to `README.md`**

Read the current `README.md`. Add a section documenting:
- Getting a paid OpenAI API key and adding `OPENAI_API_KEY=` to `.env` (mention `.env.example` already lists it).
- `pip install -r scripts/illustration/requirements.txt`.
- The two workflows from a Claude session: "add a character" (provide image → preview → approve) and "make the illustrations" (choose character + beats → generate → review/regenerate).
- The command forms from `skills/illustration/SKILL.md` (preview, full run, `--only` regenerate).
- A one-line note that the beats file is hand-written for now and will later come from the script subsystem.
- Cost expectation: ~$1/video at high quality (~$0.17/image, 16:9).
- Test commands: `python -m pytest scripts -v` (whole repo) and `python -m pytest scripts/illustration -v`.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document the character illustration subsystem"
```

---

### Task 9: Live integration test

**Files:**
- Create: `scripts/illustration/tests/test_integration.py`

**Interfaces:**
- Consumes: `OpenAIImageClient` (Task 3). Real network + a paid key.
- Produces: a live test that SKIPS when `OPENAI_API_KEY` is unset.

- [ ] **Step 1: Write the test**

Create `scripts/illustration/tests/test_integration.py`:

```python
"""Live GPT-image-2 test. Skipped unless OPENAI_API_KEY is set. Spends a small amount."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.illustration.openai_image import GeneratedImage, OpenAIImageClient

_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

pytestmark = pytest.mark.skipif(
    not _API_KEY, reason="OPENAI_API_KEY not set; skipping live image-generation test"
)


def test_generate_one_real_image(tmp_path: Path):
    # a tiny throwaway reference image
    ref = tmp_path / "ref.png"
    ref.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    client = OpenAIImageClient(_API_KEY)
    out = client.generate(
        prompt="A simple round mascot standing, flat cartoon, plain background.",
        reference_images=[ref],
        size="1536x1024",
        quality="medium",
    )
    assert isinstance(out, GeneratedImage)
    assert isinstance(out.png_bytes, bytes) and len(out.png_bytes) > 1000
```

- [ ] **Step 2: Run it to confirm it SKIPS without a key**

Run: `python -m pytest scripts/illustration/tests/test_integration.py -v`
Expected: `1 skipped` (no `OPENAI_API_KEY` in the build environment). This skip is the success signal. Then run the full suite: `python -m pytest scripts -v` — expected: all prior tests pass, illustration integration + research integration both skip.

- [ ] **Step 3: Commit**

```bash
git add scripts/illustration/tests/test_integration.py
git commit -m "test(illustration): live GPT-image-2 integration test (skipped without key)"
```

---

### Task 10: Manual smoke test (user-run)

**Files:** none (manual acceptance).

This task is performed by the user with their own key; it is not automated.

- [ ] **Step 1:** User adds `OPENAI_API_KEY` to `.env`.
- [ ] **Step 2:** User installs deps: `pip install -r scripts/illustration/requirements.txt`.
- [ ] **Step 3:** In a fresh Claude Code session in the project dir, user says "add a new character" and provides an image; Claude writes the description, runs a preview, and shows 2-3 sample frames.
- [ ] **Step 4:** User writes a small beats file (or Claude drafts one) and says "make the illustrations"; Claude runs a full generation and shows the set.
- [ ] **Step 5:** User confirms a frame can be regenerated with `--only`. Confirms the character's look is preserved across frames.

Expected: real 16:9 images in `outputs/<run-id>/images/`, character recognizably consistent, total cost roughly as estimated. If the real SDK call surface differs from Task 3's assumption (endpoint name, `size`/`quality` values, or response field), this is where it surfaces — adjust `openai_image.py`'s single `images.edit(...)` call and re-run the live integration test.

---

## Notes for the implementer

- The one place the real OpenAI SDK surface is assumed is Task 3's `generate()` method (`client.images.edit(model="gpt-image-2", image=[...], prompt=..., size=..., quality=..., n=1)` returning `resp.data[0].b64_json`). All unit tests mock this, so they pass regardless. Task 9 (live) and Task 10 (smoke) validate the real surface; if it differs, adjust only that call and the decode, mirroring how the research subsystem's transcript API was adapted.
- Follow the research subsystem's conventions exactly (see `scripts/research/youtube_client.py` and `scripts/research/fetch_viral_from_seeds.py`): DI seams, `from __future__ import annotations`, `pathlib`, keyword-only public functions, exit-code discipline in `main()`.
