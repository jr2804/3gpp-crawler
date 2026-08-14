"""LibreOffice executable discovery."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from convert_lo.exceptions import SofficeNotFoundError

_VALID_BINARY_NAMES = {"soffice", "soffice.exe", "soffice.bin"}


def find_soffice() -> Path:
    """Locate the LibreOffice soffice executable.

    Returns:
        Path to the soffice executable.

    Raises:
        SofficeNotFoundError: If soffice cannot be located.
    """
    env_path = os.getenv("LIBREOFFICE_PATH")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists() and _is_valid_soffice(candidate):
            return candidate

    candidates: list[Path] = []
    if sys.platform.startswith("win"):
        candidates.append(Path("C:/Program Files/LibreOffice/program/soffice.exe"))
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"))
    else:
        candidates.extend(
            [
                Path("/usr/bin/soffice"),
                Path("/usr/lib/libreoffice/program/soffice"),
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    which_path = shutil.which("soffice")
    if which_path:
        return Path(which_path)

    msg = "LibreOffice soffice executable not found"
    raise SofficeNotFoundError(msg)


def _is_valid_soffice(candidate: Path) -> bool:
    """Validate that a candidate path is a plausible soffice binary.

    Checks that the filename matches expected binary names and that no
    path traversal components (``..``) are present.
    """
    if candidate.name not in _VALID_BINARY_NAMES:
        return False
    return ".." not in candidate.parts
