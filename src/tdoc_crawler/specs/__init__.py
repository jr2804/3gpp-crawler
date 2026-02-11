"""Spec catalog and download support.

Note: Avoid eager imports here to prevent circular dependencies.
Import SpecDatabase directly from tdoc_crawler.database.specs when needed.
"""

from tdoc_crawler.specs.downloads import SpecDownloads

__all__ = [
    "SpecDownloads",
]
