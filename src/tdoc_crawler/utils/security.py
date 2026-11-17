"""Security utilities for safe file and network operations."""

from __future__ import annotations

import ipaddress
import shutil
import socket
import zipfile
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

from pathspec import GitIgnoreSpec

from tdoc_crawler.utils.clutter import is_clutter


def safe_extract_zip(
    zip_path: Path,
    extract_dir: Path,
    *,
    exclude: Sequence[str] = (),
    flatten_single_root: bool = False,
) -> None:
    """Extract a zip file safely, validating member paths and dropping clutter.

    Three jobs, one boundary:

    * Path-traversal protection: no member may escape ``extract_dir``.
    * Clutter filtering: members matching the gitignore-style patterns in
      ``<cache-dir>/clutter-ignore`` (defaults ship in the package) are not
      extracted — see :mod:`tdoc_crawler.utils.clutter`.
    * Configurable skips: *exclude* adds gitignore patterns (e.g. ``.git/``)
      whose members are never written, so VCS metadata and similar folders do
      not have to be deleted afterwards.

    Filtering happens before any write (not after extraction): a member that
    matches a pattern is never materialized at all.

    Args:
        zip_path: Path to the zip file to extract.
        extract_dir: Directory to extract into.
        exclude: Extra gitignore-style patterns whose members are skipped.
        flatten_single_root: When every file sits under one top-level folder,
            extract that folder's contents directly into ``extract_dir`` so
            the payload is immediately at the root.

    Raises:
        ValueError: If any zip member would escape the target directory.
        zipfile.BadZipFile: If the zip file is corrupt.
    """
    extract_dir = extract_dir.resolve()
    extra_spec = GitIgnoreSpec.from_lines(exclude) if exclude else None
    with zipfile.ZipFile(zip_path) as zf:
        members = [member for member in zf.infolist() if not is_clutter(member.filename) and not _matches(extra_spec, member.filename)]
        prefix = _single_root_prefix(members) if flatten_single_root else ""
        for member in members:
            name = member.filename
            if prefix:
                if not name.startswith(prefix):
                    continue
                name = name[len(prefix) :]
                if not name:
                    continue
            # Windows path segments cannot end with a space or dot: the OS
            # silently strips them, so the resolved path would no longer match
            # the target directory and the member would be refused as an
            # "escape". Sanitize each segment instead (e.g. ``"S4aA260016 … /"``
            # becomes ``"S4aA260016 …/"``), keeping the layout extractable.
            name = _sanitize_member_path(name)
            member_path = (extract_dir / name).resolve()
            if not str(member_path).startswith(str(extract_dir)):
                msg = (
                    f"Zip member {member.filename!r} escapes target directory {extract_dir} "
                    "(the archive itself downloaded successfully; this member path "
                    "is not extractable on this platform)"
                )
                raise ValueError(msg)
            if name.endswith("/"):
                member_path.mkdir(parents=True, exist_ok=True)
                continue
            member_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as source, member_path.open("wb") as target:
                shutil.copyfileobj(source, target)


def _sanitize_member_path(name: str) -> str:
    """Strip trailing spaces/dots from each path segment of a zip member.

    Windows cannot represent a segment ending in a space or dot on disk and
    silently strips it, which used to trip the zip-slip guard. Each segment
    is sanitized instead (e.g. ``"S4aA260016 … /"`` becomes
    ``"S4aA260016 …/"``), keeping the layout extractable.

    ``.``, ``..`` and a leading ``/`` are preserved verbatim so the
    zip-slip guard still sees (and rejects) genuine escapes; an emptied
    segment (e.g. ``"..."``) becomes ``"_"`` so the member stays
    addressable.
    """
    is_dir = name.endswith("/")
    segments = [segment for segment in name.split("/") if segment != ""]
    sanitized = [segment if segment in (".", "..") else segment.rstrip(" .") or "_" for segment in segments]
    rebuilt = "/".join(sanitized)
    if name.startswith("/"):
        rebuilt = f"/{rebuilt}"
    if is_dir:
        rebuilt = f"{rebuilt}/"
    return rebuilt


def _matches(spec: GitIgnoreSpec | None, name: str) -> bool:
    """Return True when *name* matches the extra exclusion patterns."""
    return spec is not None and spec.match_file(name)


def _single_root_prefix(members: list[zipfile.ZipInfo]) -> str:
    """Return the ``root/`` prefix when all files share one top-level folder.

    Conservative by design: a root-level file (``readme.txt`` next to
    ``S4-1/``) leaves the layout untouched, because flattening would then
    silently drop the folder boundary the archive author chose.
    """
    roots: set[str] = set()
    for member in members:
        name = member.filename
        if not name or name.endswith("/"):
            continue
        head, separator, _ = name.partition("/")
        if not separator:
            return ""
        roots.add(head)
        if len(roots) > 1:
            return ""
    return f"{next(iter(roots))}/" if roots else ""


def validate_api_url(url: str) -> str:
    """Validate an API URL is safe to use (no SSRF).

    Ensures the URL uses HTTP/HTTPS and does not target internal
    or private network addresses.

    Args:
        url: The API base URL to validate.

    Returns:
        The validated URL string.

    Raises:
        ValueError: If the URL scheme is invalid or targets a private address.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        msg = f"Invalid API URL scheme {parsed.scheme!r} -- only http and https are allowed"
        raise ValueError(msg)

    if not parsed.hostname:
        msg = "API URL must include a hostname"
        raise ValueError(msg)

    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        # Hostname is a domain name -- resolve DNS and check all resulting IPs
        try:
            addr_infos = socket.getaddrinfo(parsed.hostname, None)
        except socket.gaierror:
            msg = f"Cannot resolve API URL hostname {parsed.hostname!r}"
            raise ValueError(msg) from None
        for _family, _type, _proto, _canonname, sockaddr in addr_infos:
            resolved_ip = ipaddress.ip_address(sockaddr[0])
            if resolved_ip.is_private or resolved_ip.is_loopback or resolved_ip.is_reserved or resolved_ip.is_link_local or resolved_ip.is_multicast:
                msg = f"API URL hostname {parsed.hostname!r} resolves to private/reserved address {resolved_ip}"
                raise ValueError(msg)
        return url

    if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast:
        msg = f"API URL hostname {parsed.hostname!r} resolves to private/reserved address {ip}"
        raise ValueError(msg)
    return url
