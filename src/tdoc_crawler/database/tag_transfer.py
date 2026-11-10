"""Export, import and backup of tag rows keyed by natural item ids.

Tag rows are identified by ``kind`` + ``item_id`` (TDoc id, spec number or
free-text id), never by the generated ``tag_id``, so dumps stay valid across
database rebuilds. Reading works without the ORM, so a stale schema can still
be exported before ``--clear-db`` deletes it.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tdoc_crawler.database.tags import add_tags, list_tags
from tdoc_crawler.models.base import TagKind
from tdoc_crawler.utils.normalization import normalize_spec_number, normalize_tdoc_id

TAG_BACKUP_FILENAME = "tags-backup.json"
_TAG_KEYS = ("kind", "item_id", "tag")


@dataclass(frozen=True)
class TagRecord:
    """One tag attached to one item, identified by natural keys."""

    kind: TagKind
    item_id: str
    tag: str


async def export_tags(kind: TagKind | None = None) -> list[TagRecord]:
    """All tag rows (optionally one kind) as natural-key records."""
    rows = await list_tags(kind=kind)
    return [TagRecord(kind=TagKind(row.kind), item_id=row.item_id, tag=row.tag) for row in rows]


async def import_tags(records: list[TagRecord]) -> int:
    """Add tag records to the open database. Returns the number of new rows."""
    grouped: dict[tuple[TagKind, str], list[str]] = {}
    for record in records:
        key = (record.kind, normalize_item_id(record.kind, record.item_id))
        grouped.setdefault(key, []).append(record.tag)
    added = 0
    for (kind, item_id), tags in grouped.items():
        added += await add_tags(kind, item_id, tags)
    return added


def normalize_item_id(kind: TagKind, item: str) -> str:
    """Normalize an item id per kind (TDoc and spec ids have canonical forms)."""
    if kind is TagKind.TDOC:
        return normalize_tdoc_id(item)
    if kind is TagKind.SPEC:
        return normalize_spec_number(item)
    return item.strip()


def read_tags_from_database_file(db_file: Path) -> list[TagRecord]:
    """Read tag rows straight from a SQLite file, ignoring the model schema.

    Returns an empty list when the file does not exist. Raises ``sqlite3.Error``
    when the file or its ``tagentry`` table cannot be read.
    """
    if not db_file.exists():
        return []
    with closing(sqlite3.connect(db_file)) as connection:
        rows = connection.execute("SELECT kind, item_id, tag FROM tagentry").fetchall()
    return [TagRecord(kind=TagKind(kind), item_id=item_id, tag=tag) for kind, item_id, tag in rows]


def read_tag_file(path: Path) -> list[TagRecord]:
    """Load a JSON or YAML tag dump written by ``tag export`` or the backup."""
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            payload = json.loads(text)
        elif suffix in {".yaml", ".yml"}:
            payload = yaml.safe_load(text)
        else:
            msg = f"unsupported tag dump format {suffix!r} (use .json, .yaml or .yml)"
            raise ValueError(msg)
    except yaml.YAMLError as exc:
        msg = f"invalid YAML in {path}: {exc}"
        raise ValueError(msg) from exc
    return tag_records_from_payload(payload)


def tag_records_from_payload(payload: Any) -> list[TagRecord]:
    """Validate a parsed tag dump. Raises ``ValueError`` on malformed input."""
    if not isinstance(payload, list):
        msg = "tag dump must be a list of {kind, item_id, tag} objects"
        raise ValueError(msg)
    records: list[TagRecord] = []
    for entry in payload:
        if not isinstance(entry, dict) or not all(key in entry for key in _TAG_KEYS):
            msg = f"invalid tag entry (needs kind, item_id, tag): {entry!r}"
            raise ValueError(msg)
        try:
            kind = TagKind(str(entry["kind"]).strip().lower())
        except ValueError as exc:
            msg = f"invalid tag kind {entry['kind']!r} (expected tdoc, spec or other)"
            raise ValueError(msg) from exc
        records.append(TagRecord(kind=kind, item_id=str(entry["item_id"]), tag=str(entry["tag"])))
    return records


def write_tag_backup(records: list[TagRecord], path: Path) -> None:
    """Write records as a JSON backup file (overwrites the previous backup)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tag_records_to_payload(records), indent=2), encoding="utf-8")


def tag_records_to_payload(records: list[TagRecord]) -> list[dict[str, str]]:
    """Plain records for serialization (``kind``, ``item_id``, ``tag``)."""
    return [{"kind": record.kind.value, "item_id": record.item_id, "tag": record.tag} for record in records]


__all__ = [
    "TAG_BACKUP_FILENAME",
    "TagRecord",
    "export_tags",
    "import_tags",
    "normalize_item_id",
    "read_tag_file",
    "read_tags_from_database_file",
    "tag_records_from_payload",
    "tag_records_to_payload",
    "write_tag_backup",
]
