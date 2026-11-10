"""Persistence and on-demand listing of TDoc and spec archive members.

Rows are written on checkout (recording the local zip listing) and on
explicit listing requests (remote HTTP range listing). Nothing is crawled
eagerly.
"""

from __future__ import annotations

import asyncio

from tdoc_crawler.database.oxyde_models import ArchiveMember
from tdoc_crawler.models.archives import ArchiveKind, ArchiveRecord
from tdoc_crawler.utils.archive import list_remote_zip_members
from tdoc_crawler.utils.clutter import is_clutter
from tdoc_crawler.utils.misc import utc_now


async def save_archive_records(records: list[ArchiveRecord]) -> None:
    """Persist several archive listings (caller holds an open database context)."""
    for record in records:
        await replace_archive_members(record)


async def archive_members_for(kind: ArchiveKind, item_id: str, url: str, *, refresh: bool = False) -> list[ArchiveMember]:
    """Return stored members, listing the remote archive first when none are stored (or refresh is set)."""
    if not refresh:
        existing = await list_archive_members(kind, item_id)
        if existing:
            return existing
    members = await asyncio.to_thread(list_remote_zip_members, url)
    archive_name = url.rsplit("/", 1)[-1]
    await replace_archive_members(ArchiveRecord(kind=kind, item_id=item_id, archive_name=archive_name, members=members))
    return await list_archive_members(kind, item_id)


async def replace_archive_members(record: ArchiveRecord) -> None:
    """Replace the stored member listing of one archive (kind + item_id)."""
    await _delete_matching(record.kind, record.item_id)
    recorded_at = utc_now()
    unique_members = {member.member_path: member for member in record.members}
    for member_path, member in unique_members.items():
        # oxyde create() excludes unset fields; set defaulted fields explicitly
        await ArchiveMember.objects.create(
            instance=ArchiveMember(
                member_id=f"{record.kind.value}:{record.item_id}:{member_path}",
                kind=record.kind.value,
                item_id=record.item_id,
                archive_name=record.archive_name,
                member_path=member_path,
                file_size=member.file_size,
                is_clutter=is_clutter(member_path),
                classification=None,
                recorded_at=recorded_at,
            )
        )


async def list_archive_members(kind: ArchiveKind, item_id: str) -> list[ArchiveMember]:
    """Stored member rows for one archive, sorted by path."""
    rows = await ArchiveMember.objects.filter(kind=kind.value, item_id=item_id).all()
    return sorted(rows, key=lambda row: row.member_path)


async def clear_archive_members(kind: ArchiveKind) -> int:
    """Delete all stored member rows of one kind. Returns deleted row count."""
    return await _delete_matching(kind)


async def _delete_matching(kind: ArchiveKind, item_id: str | None = None) -> int:
    query = ArchiveMember.objects.filter(kind=kind.value)
    if item_id is not None:
        query = query.filter(item_id=item_id)
    rows = await query.all()
    for row in rows:
        await row.delete()
    return len(rows)
