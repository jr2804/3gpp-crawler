"""Security utilities for safe file and network operations."""

from __future__ import annotations

import ipaddress
import socket
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from tdoc_crawler.utils.clutter import is_clutter


def safe_extract_zip(zip_path: Path, extract_dir: Path) -> None:
    """Extract a zip file safely, validating member paths and dropping clutter.

    Two jobs, one boundary:

    * Path-traversal protection: no member may escape ``extract_dir``.
    * Clutter filtering: members matching the gitignore-style patterns in
      ``<cache-dir>/clutter-ignore`` (defaults ship in the package) are not
      extracted — see :mod:`tdoc_crawler.utils.clutter`.

    Filtering here (not in consumers) is deliberate: macOS sidecars inherit
    the original's suffix, so suffix-based consumers
    cannot distinguish them from real documents by name or extension.

    Args:
        zip_path: Path to the zip file to extract.
        extract_dir: Directory to extract into.

    Raises:
        ValueError: If any zip member would escape the target directory.
        zipfile.BadZipFile: If the zip file is corrupt.
    """
    extract_dir = extract_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if is_clutter(member.filename):
                continue
            member_path = (extract_dir / member.filename).resolve()
            if not str(member_path).startswith(str(extract_dir)):
                msg = f"Zip member {member.filename!r} escapes target directory {extract_dir}"
                raise ValueError(msg)
            zf.extract(member, extract_dir)


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
