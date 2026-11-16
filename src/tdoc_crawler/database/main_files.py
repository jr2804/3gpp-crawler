"""Per-TDoc manual main-file overrides.

An override records which archive member the user considers the main
document of a TDoc. It always wins over automatic selection
(heuristic ranking or the decision model) and survives re-download and
re-extraction because it is keyed by the archive member path.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from tdoc_crawler.database.oxyde_models import MainFileOverride, MainFileRecord
from tdoc_crawler.utils.misc import utc_now


async def set_main_file_override(tdoc_id: str, member_path: str, *, note: str | None = None) -> MainFileOverride:
    """Create or replace the manual main-file override of one TDoc.

    Args:
        tdoc_id: TDoc identifier (normalized by the caller).
        member_path: Archive-relative POSIX path of the main file.
        note: Optional free-text note explaining the choice.

    Raises:
        ValueError: If ``member_path`` is empty, absolute, or escapes the
            archive directory.
    """
    candidate = PurePosixPath(member_path)
    if not member_path or candidate.is_absolute() or ".." in candidate.parts:
        msg = f"invalid-member-path: {member_path!r} must be relative to the archive root"
        raise ValueError(msg)
    existing = await get_main_file_override(tdoc_id)
    if existing is not None:
        await existing.delete()
    override = MainFileOverride(tdoc_id=tdoc_id, member_path=member_path, note=note, created_at=utc_now())
    await MainFileOverride.objects.create(instance=override)
    return override


async def clear_main_file_override(tdoc_id: str) -> bool:
    """Delete the override of one TDoc. Returns True when one existed."""
    existing = await get_main_file_override(tdoc_id)
    if existing is None:
        return False
    await existing.delete()
    return True


async def get_main_file_override(tdoc_id: str) -> MainFileOverride | None:
    """Return the stored override for one TDoc, or None."""
    return await MainFileOverride.objects.filter(tdoc_id=tdoc_id).first()


async def list_main_file_overrides() -> list[MainFileOverride]:
    """All stored overrides, sorted by TDoc ID."""
    rows = await MainFileOverride.objects.all()
    return sorted(rows, key=lambda row: row.tdoc_id)


async def save_main_file_record(
    tdoc_id: str,
    *,
    member_path: str,
    source: str,
    selector: str,
    confidence: float | None = None,
) -> MainFileRecord:
    """Create or replace the stored classification of one TDoc."""
    existing = await get_main_file_record(tdoc_id)
    if existing is not None:
        await existing.delete()
    record = MainFileRecord(
        tdoc_id=tdoc_id,
        member_path=member_path,
        source=source,
        selector=selector,
        confidence=confidence,
        updated_at=utc_now(),
    )
    await MainFileRecord.objects.create(instance=record)
    return record


async def clear_main_file_record(tdoc_id: str) -> bool:
    """Delete the stored classification of one TDoc. Returns True when one existed."""
    existing = await get_main_file_record(tdoc_id)
    if existing is None:
        return False
    await existing.delete()
    return True


async def get_main_file_record(tdoc_id: str) -> MainFileRecord | None:
    """Return the last stored classification for one TDoc, or None."""
    return await MainFileRecord.objects.filter(tdoc_id=tdoc_id).first()


async def list_main_file_records() -> list[MainFileRecord]:
    """All stored classifications, sorted by TDoc ID."""
    rows = await MainFileRecord.objects.all()
    return sorted(rows, key=lambda row: row.tdoc_id)


__all__ = [
    "clear_main_file_override",
    "clear_main_file_record",
    "get_main_file_override",
    "get_main_file_record",
    "list_main_file_overrides",
    "list_main_file_records",
    "save_main_file_record",
    "set_main_file_override",
]
