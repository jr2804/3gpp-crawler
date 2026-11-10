"""Zip member listing for local archives and remote (HTTP range) archives."""

from __future__ import annotations

import zipfile
from pathlib import Path

from unzip_http import RemoteZipFile

from tdoc_crawler.models.archives import ArchiveMemberInfo


def list_zip_members(zip_path: Path) -> list[ArchiveMemberInfo]:
    """List the file entries of a local zip archive (directory entries skipped)."""
    with zipfile.ZipFile(zip_path) as zf:
        return [ArchiveMemberInfo(member_path=info.filename, file_size=info.file_size) for info in zf.infolist() if not info.is_dir()]


def list_remote_zip_members(url: str) -> list[ArchiveMemberInfo]:
    """List the file entries of a remote zip via HTTP range reads (no full download)."""
    return remote_zip_members(RemoteZipFile(url))


def remote_zip_members(rzf: RemoteZipFile) -> list[ArchiveMemberInfo]:
    """File entries of an opened remote zip (directory entries skipped)."""
    return [ArchiveMemberInfo(member_path=info.filename, file_size=info.file_size) for info in rzf.infolist() if not info.filename.endswith("/")]
