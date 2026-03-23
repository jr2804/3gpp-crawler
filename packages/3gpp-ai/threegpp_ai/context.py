"""Document processing context for the AI pipeline.

This module provides the DocumentContext dataclass that carries all information
needed to process a document through the pipeline stages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from threegpp_ai.models import (
    DocumentClassification,
    ProcessingStatus,
    SourceKind,
    WorkspaceMember,
)
from threegpp_ai.operations.workspace_names import normalize_workspace_name

logger = logging.getLogger(__name__)


@dataclass
class DocumentContext:
    """Processing context for a document through the AI pipeline.

    Captures document type, folder path, artifact paths, and computed
    properties derived from SourceKind.
    """

    document_id: str
    source_kind: SourceKind
    folder_path: Path
    workspace: str
    markdown_path: Path | None = None
    meeting_id: str | None = None
    member: WorkspaceMember | None = None
    status: ProcessingStatus | None = None
    classification: DocumentClassification | None = None

    @property
    def is_spec(self) -> bool:
        """True if this document is a specification."""
        return self.source_kind == SourceKind.SPEC

    @property
    def is_tdoc(self) -> bool:
        """True if this document is a TDoc."""
        return self.source_kind == SourceKind.TDOC

    @property
    def artifact_path(self) -> Path:
        """Path to the extracted markdown artifact."""
        if self.markdown_path:
            return self.markdown_path
        return self.folder_path / ".ai" / f"{self.document_id.strip().upper()}.md"

    def ensure_artifact_dir(self) -> Path:
        """Ensure the .ai directory exists and return artifact path."""
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        return self.artifact_path

    def normalized_workspace(self) -> str:
        """Return normalized workspace name."""
        return normalize_workspace_name(self.workspace)


__all__ = ["DocumentContext"]
