"""Tag operations for TDocs, specs, and other items.

Tags are the lightweight grouping mechanism (replacing the removed
workspace subsystem).  A tag row points at an item via ``kind`` +
``item_id`` — no foreign key; integrity is app-layer.

Filter semantics shared by CLI and MCP: a *tag group* is a set of tags
combined with OR (``--tag a,b``); repeated groups combine with AND
(``--tag a,b --tag c`` matches items having (a or b) and c).
"""

from __future__ import annotations

from uuid import uuid4

from tdoc_crawler.database.oxyde_models import TagEntry
from tdoc_crawler.models.base import TagKind
from tdoc_crawler.utils.misc import utc_now


def normalize_tags(tags: list[str]) -> list[str]:
    """Strip, drop empties, dedupe (order-preserving)."""
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        cleaned = tag.strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def parse_tag_groups(values: list[str]) -> list[list[str]]:
    """Parse CLI ``--tag`` values into OR-groups: comma-split each value."""
    return [normalize_tags(v.split(",")) for v in values if v and v.strip()]


async def add_tags(kind: TagKind, item_id: str, tags: list[str]) -> int:
    """Add tags to an item. Returns number of new tag rows (existing skipped)."""
    existing = {row.tag for row in await TagEntry.objects.filter(kind=kind.value, item_id=item_id).all()}
    added = 0
    for tag in normalize_tags(tags):
        if tag in existing:
            continue
        # oxyde create() excludes unset fields; set defaulted fields explicitly
        await TagEntry.objects.create(
            instance=TagEntry(
                tag_id=str(uuid4()),
                kind=kind.value,
                item_id=item_id,
                tag=tag,
                created_at=utc_now(),
            )
        )
        existing.add(tag)
        added += 1
    return added


async def remove_tags(kind: TagKind, item_id: str, tags: list[str] | None = None) -> int:
    """Remove tags from an item (all tags if *tags* is None). Returns removed count."""
    rows = await TagEntry.objects.filter(kind=kind.value, item_id=item_id).all()
    targets = normalize_tags(tags) if tags is not None else [row.tag for row in rows]
    target_set = set(targets)
    removed = 0
    for row in rows:
        if row.tag in target_set:
            await row.delete()
            removed += 1
    return removed


async def list_tags(
    kind: TagKind | None = None,
    item_id: str | None = None,
    tag: str | None = None,
) -> list[TagEntry]:
    """List tag rows, optionally filtered by kind, item, and/or tag."""
    rows = (
        await TagEntry.objects.filter(kind=kind.value).all()
        if kind is not None
        else await TagEntry.objects.all()
    )
    if item_id is not None:
        rows = [row for row in rows if row.item_id == item_id]
    if tag is not None:
        wanted = tag.strip().lower()
        rows = [row for row in rows if row.tag == wanted]
    return sorted(rows, key=lambda r: (r.kind, r.item_id, r.tag))


async def item_ids_for_tag_groups(groups: list[list[str]], kind: TagKind) -> set[str]:
    """Item ids matching the AND-of-ORs tag expression for *kind*.

    Empty *groups* returns an empty set (no filter applied by callers).
    """
    if not groups:
        return set()
    result: set[str] | None = None
    for group in groups:
        group_ids: set[str] = set()
        for tag in group:
            rows = await TagEntry.objects.filter(kind=kind.value, tag=tag).all()
            group_ids.update(row.item_id for row in rows)
        result = group_ids if result is None else result & group_ids
        if not result:
            return set()
    return result or set()


__all__ = [
    "add_tags",
    "item_ids_for_tag_groups",
    "list_tags",
    "normalize_tags",
    "parse_tag_groups",
    "remove_tags",
]
