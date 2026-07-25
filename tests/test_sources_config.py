from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def write_yaml(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_sources_yaml_accepts_valid_sources_yaml(tmp_path: Path) -> None:
    from hlpp_l0_contracts.sources_config import SourceStatus, load_sources_yaml, validate_source

    path = write_yaml(
        tmp_path,
        """
sources:
  - name: fred
    url: https://example.com/fred
    ops:
      status: active
    disabled_reason: null
    last_verified_at: "2026-05-05T09:00:00Z"
""",
    )

    sources = load_sources_yaml(path)

    assert len(sources) == 1
    assert sources[0].name == "fred"
    assert sources[0].url == "https://example.com/fred"
    assert sources[0].ops.status is SourceStatus.active
    assert sources[0].disabled_reason is None
    assert sources[0].last_verified_at == datetime(
        2026,
        5,
        5,
        9,
        0,
        0,
        tzinfo=timezone.utc,
    )
    assert validate_source(sources[0].model_dump()).name == "fred"


def test_load_sources_yaml_accepts_null_last_verified_at(tmp_path: Path) -> None:
    """A registered-but-never-verified source is a real state, not a schema error.

    Push-stream sources must be registered active before their first live session
    (an unrecorded session cannot be recovered), so they have no verified timestamp
    to declare until that session runs.
    """
    from hlpp_l0_contracts.sources_config import load_sources_yaml

    path = write_yaml(
        tmp_path,
        """
sources:
  - name: stream-not-yet-run
    url: vendor://stream?mode=push
    ops:
      status: active
    disabled_reason: null
    last_verified_at: null
""",
    )

    sources = load_sources_yaml(path)

    assert len(sources) == 1
    assert sources[0].last_verified_at is None


def test_load_sources_yaml_still_rejects_missing_last_verified_at(tmp_path: Path) -> None:
    """Nullable must not decay into optional: the key itself stays mandatory."""
    from hlpp_l0_contracts.sources_config import load_sources_yaml

    path = write_yaml(
        tmp_path,
        """
sources:
  - name: fred
    url: https://example.com/fred
    ops:
      status: active
    disabled_reason: null
""",
    )

    with pytest.raises(ValidationError, match="last_verified_at"):
        load_sources_yaml(path)


def test_load_sources_yaml_rejects_entry_missing_ops(tmp_path: Path) -> None:
    from hlpp_l0_contracts.sources_config import load_sources_yaml

    path = write_yaml(
        tmp_path,
        """
sources:
  - name: fred
    url: https://example.com/fred
    disabled_reason: null
    last_verified_at: "2026-05-05T09:00:00Z"
""",
    )

    with pytest.raises(ValidationError, match="ops"):
        load_sources_yaml(path)


def test_load_sources_yaml_rejects_bad_status_enum(tmp_path: Path) -> None:
    from hlpp_l0_contracts.sources_config import load_sources_yaml

    path = write_yaml(
        tmp_path,
        """
sources:
  - name: fred
    url: https://example.com/fred
    ops:
      status: paused
    disabled_reason: null
    last_verified_at: "2026-05-05T09:00:00Z"
""",
    )

    with pytest.raises(ValidationError, match="status"):
        load_sources_yaml(path)
