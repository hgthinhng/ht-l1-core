"""Pydantic schema and loader for ``sources.yaml`` configuration files.

Exports ``SourceEntry`` (individual source definition), ``SourcesYaml`` (top-level
model), and ``load_sources_yaml`` (parse a YAML file into a list of validated entries).
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict


class SourceStatus(str, Enum):
    active = "active"
    disabled = "disabled"
    deprecated = "deprecated"


class SourceOps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SourceStatus


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str
    ops: SourceOps
    disabled_reason: str | None
    # Nullable but REQUIRED, same shape as disabled_reason above: the key must be
    # present so nobody can forget to state it, while an explicit null records the
    # legitimate "registered but never verified yet" state. That state is real for
    # push-stream sources, which must be registered active BEFORE the first live
    # session (an unrecorded session is gone permanently), so there is no verified
    # timestamp to give until that session runs. Aligns with the sibling contract
    # l1a/research/contracts/reports_v1.py, which already declares this column
    # nullable=True + required=True, and with the research collectors that already
    # emit last_verified_at: None.
    last_verified_at: datetime | None


class SourcesYaml(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[SourceEntry]


def validate_source(entry_dict: dict[str, Any]) -> SourceEntry:
    return SourceEntry.model_validate(entry_dict)


def load_sources_yaml(path: Path) -> list[SourceEntry]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SourcesYaml.model_validate(data).sources
