from __future__ import annotations

from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_version_matches_latest_changelog_entry() -> None:
    """Pin the version to the CHANGELOG instead of to a literal.

    The old form hardcoded "0.5.5" and had been failing since the 0.5.6 release,
    so it stopped guarding anything and just made the suite permanently red.
    Deriving the expectation from the CHANGELOG keeps the real invariant: you do
    not get to bump the version without writing down what changed.
    """
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text()

    latest = next(
        line.removeprefix("## ").split(" - ")[0].strip()
        for line in changelog.splitlines()
        if line.startswith("## ")
    )

    assert pyproject["project"]["version"] == latest


def test_changelog_records_0_1_5_protocol_release() -> None:
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text()

    assert "## 0.1.5 - 2026-05-07" in changelog
    assert "Backfillable" in changelog
    assert "TierAStreamConsumer" in changelog
    assert "ADR-016" in changelog


def test_adr_016_document_locks_tiered_trigger_matrix() -> None:
    adr = (PROJECT_ROOT / "docs" / "adr" / "ADR-016-tiered-l1-l2-trigger.md").read_text()

    assert "ADR-016 LOCK" in adr
    assert "HTAP L1→L2 trigger transport is partitioned into 5 tiers" in adr
    assert "m12-fqx-trading-stream-v1" in adr
    assert "SQLite ring at `~/.local/share/htap/hot-buffer.db`" in adr
    assert "Backfillable" in adr
    assert "TierAStreamConsumer" in adr
