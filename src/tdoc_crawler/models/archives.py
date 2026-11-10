"""Archive (zip) member models for TDoc and specification checkouts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ArchiveKind(StrEnum):
    """Owner type of an archive: a TDoc or a specification."""

    TDOC = "tdoc"
    SPEC = "spec"


@dataclass(frozen=True)
class ArchiveMemberInfo:
    """One entry inside an archive. ``file_size`` is None when the size is unknown."""

    member_path: str
    file_size: int | None = None


@dataclass
class ArchiveRecord:
    """Member listing of one archive, ready to persist."""

    kind: ArchiveKind
    item_id: str
    archive_name: str
    members: list[ArchiveMemberInfo] = field(default_factory=list)
