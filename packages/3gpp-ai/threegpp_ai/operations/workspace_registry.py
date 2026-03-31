"""Workspace registry management for AI workspaces.

This module provides a centralized registry for workspace metadata,
stored in a JSON file at ~/.tdoc-crawler/.ai/workspaces.json.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tdoc_crawler.config.settings import PathConfig
from tdoc_crawler.logging import get_logger
from tdoc_crawler.utils.misc import utc_now
from tdoc_crawler.utils.normalization import normalize_release_version

from threegpp_ai.models import SourceKind
from threegpp_ai.operations.workspace_names import DEFAULT_WORKSPACE, normalize_workspace_name

logger = get_logger(__name__)


def normalize_spec_member_id(source_item_id: str) -> str:
    """Normalize spec member IDs to canonical format for display.

    Handles legacy IDs where release tuple objects were stringified.

    Examples:
        26261-REL('19', []) -> 26261-REL19.0.0
        26261-REL19 -> 26261-REL19.0.0
        26261-REL19.1 -> 26261-REL19.1.0

    Args:
        source_item_id: The source item ID to normalize.

    Returns:
        Normalized source item ID with three-digit release version.
    """
    return _normalize_legacy_spec_member_id(source_item_id)


def _normalize_legacy_spec_member_id(source_item_id: str) -> str:
    """Normalize spec IDs to canonical three-digit release versions.

    Examples:
        26261-REL('19', []) -> 26261-REL19.0.0
        26261-REL19 -> 26261-REL19.0.0
        26261-REL19.1 -> 26261-REL19.1.0
    """
    legacy_match = re.match(r"^(?P<spec>\d+(?:\.\d+)?)-REL\('(?P<release>[^']+)', \[[^\]]*\]\)$", source_item_id)
    if legacy_match is not None:
        normalized_release = normalize_release_version(legacy_match.group("release"))
        return f"{legacy_match.group('spec')}-REL{normalized_release}"

    modern_match = re.match(r"^(?P<spec>\d+(?:\.\d+)?)-REL(?P<release>.+)$", source_item_id)
    if modern_match is not None:
        normalized_release = normalize_release_version(modern_match.group("release"))
        return f"{modern_match.group('spec')}-REL{normalized_release}"

    return source_item_id


@dataclass
class WorkspaceMember:
    """Member of a workspace (TDoc, spec, or other document)."""

    source_item_id: str
    source_path: str
    source_kind: SourceKind
    added_by: str = ""
    is_active: bool = True
    added_at: str = field(default_factory=lambda: utc_now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_item_id": _normalize_legacy_spec_member_id(self.source_item_id),
            "source_path": self.source_path,
            "source_kind": self.source_kind.value,
            "added_by": self.added_by,
            "is_active": self.is_active,
            "added_at": self.added_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceMember:
        return cls(
            source_item_id=_normalize_legacy_spec_member_id(data["source_item_id"]),
            source_path=data["source_path"],
            source_kind=SourceKind(data.get("source_kind", "other")),
            added_by=data.get("added_by", ""),
            is_active=data.get("is_active", True),
            added_at=data.get("added_at", utc_now().isoformat()),
        )


@dataclass
class WorkspaceMetadata:
    """Metadata for a single workspace."""

    name: str
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    description: str = ""
    auto_build: bool = True
    members: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "description": self.description,
            "auto_build": self.auto_build,
            "members": self.members,
        }

    def add_member(self, member: WorkspaceMember) -> None:
        """Add a member to the workspace."""
        normalized_target_id = _normalize_legacy_spec_member_id(member.source_item_id)
        self.members = [m for m in self.members if _normalize_legacy_spec_member_id(str(m.get("source_item_id", ""))) != normalized_target_id]
        member.source_item_id = normalized_target_id
        self.members.append(member.to_dict())

    def remove_member(self, source_item_id: str) -> bool:
        """Remove a member by source_item_id. Returns True if found and removed."""
        normalized_target_id = _normalize_legacy_spec_member_id(source_item_id)
        original_count = len(self.members)
        self.members = [m for m in self.members if _normalize_legacy_spec_member_id(str(m.get("source_item_id", ""))) != normalized_target_id]
        return len(self.members) < original_count

    def deactivate_member(self, source_item_id: str) -> bool:
        """Deactivate a member by source_item_id. Returns True if found and deactivated."""
        normalized_target_id = _normalize_legacy_spec_member_id(source_item_id)
        for member in self.members:
            if _normalize_legacy_spec_member_id(str(member.get("source_item_id", ""))) == normalized_target_id:
                member["is_active"] = False
                return True
        return False

    def get_member_counts(self) -> dict[str, int]:
        """Get counts of members by source kind."""
        counts = {"tdoc": 0, "spec": 0, "other": 0, "total": 0}
        for member in self.members:
            if not member.get("is_active", True):
                continue
            kind = member.get("source_kind", "other").lower()
            if kind in counts:
                counts[kind] += 1
            else:
                counts["other"] += 1
            counts["total"] += 1
        return counts

    def list_members(self, include_inactive: bool = False) -> list[WorkspaceMember]:
        """List members of the workspace."""
        members = []
        for member_data in self.members:
            member = WorkspaceMember.from_dict(member_data)
            if not include_inactive and not member.is_active:
                continue
            members.append(member)
        return sorted(members, key=lambda m: m.source_item_id)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> WorkspaceMetadata:
        return cls(
            name=name,
            created_at=data.get("created_at", utc_now().isoformat()),
            description=data.get("description", ""),
            auto_build=data.get("auto_build", True),
            members=data.get("members", []),
        )


@dataclass
class WorkspaceDisplayInfo:
    """Display information for a workspace including member counts."""

    name: str
    created_at: str
    tdoc_count: int = 0
    spec_count: int = 0
    other_count: int = 0
    is_active: bool = False


@dataclass
class WorkspaceRegistry:
    """Registry for all workspaces.

    The registry is stored as a JSON file with the following structure:
    {
        "version": 1,
        "workspaces": {
            "default": { ...WorkspaceMetadata... },
            "atias": { ...WorkspaceMetadata... }
        },
        "active": "default"
    }
    """

    version: int = 1
    workspaces: dict[str, WorkspaceMetadata] = field(default_factory=dict)
    active: str = DEFAULT_WORKSPACE
    registry_path: Path | None = None

    def save(self) -> None:
        """Save registry to JSON file."""
        registry_path = self.registry_path or PathConfig().ai_workspace_file

        data = {
            "version": self.version,
            "workspaces": {name: metadata.to_dict() for name, metadata in self.workspaces.items()},
            "active": self.active,
        }

        with registry_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Saved workspace registry to {registry_path}")

    def create_workspace(
        self,
        name: str,
        description: str = "",
        auto_build: bool = True,
    ) -> WorkspaceMetadata:
        """Create a new workspace entry.

        Args:
            name: Workspace name.
            description: Optional description.
            auto_build: Whether to auto-build when members are added.

        Returns:
            Created WorkspaceMetadata.

        Raises:
            ValueError: If workspace already exists.
        """
        normalized_name = normalize_workspace_name(name)
        if not normalized_name:
            raise ValueError("Workspace name cannot be empty")

        if normalized_name in self.workspaces:
            raise ValueError(f"Workspace '{normalized_name}' already exists")

        metadata = WorkspaceMetadata(
            name=normalized_name,
            description=description,
            auto_build=auto_build,
        )
        self.workspaces[normalized_name] = metadata
        logger.info(f"Created workspace '{normalized_name}'")
        return metadata

    def delete_workspace(self, name: str) -> bool:
        """Delete a workspace entry.

        Args:
            name: Workspace name to delete.

        Returns:
            True if deleted, False if not found or if attempting to delete default.
        """
        normalized_name = normalize_workspace_name(name)
        if normalized_name == DEFAULT_WORKSPACE:
            logger.warning("Cannot delete the default workspace")
            return False

        if normalized_name not in self.workspaces:
            logger.warning(f"Workspace '{normalized_name}' not found")
            return False

        del self.workspaces[normalized_name]

        # Switch active workspace if needed
        if self.active == normalized_name:
            self.active = DEFAULT_WORKSPACE

        logger.info(f"Deleted workspace '{normalized_name}'")
        return True

    def get_workspace(self, name: str) -> WorkspaceMetadata | None:
        """Get workspace metadata by name.

        Args:
            name: Workspace name.

        Returns:
            WorkspaceMetadata if found, None otherwise.
        """
        normalized_name = normalize_workspace_name(name)
        return self.workspaces.get(normalized_name)

    def list_workspaces(self) -> list[WorkspaceDisplayInfo]:
        """List all workspaces with member counts.

        Returns:
            List of WorkspaceDisplayInfo objects with member counts.
        """
        active_name = self.active or DEFAULT_WORKSPACE
        result = []

        for metadata in self.workspaces.values():
            counts = metadata.get_member_counts()
            result.append(
                WorkspaceDisplayInfo(
                    name=metadata.name,
                    created_at=metadata.created_at,
                    tdoc_count=counts.get("tdoc", 0),
                    spec_count=counts.get("spec", 0),
                    other_count=counts.get("other", 0),
                    is_active=metadata.name == active_name,
                )
            )

        return result

    def set_active(self, name: str) -> None:
        """Set the active workspace.

        Args:
            name: Workspace name to set as active.

        Raises:
            ValueError: If workspace doesn't exist.
        """
        normalized_name = normalize_workspace_name(name)
        if normalized_name not in self.workspaces:
            raise ValueError(f"Workspace '{normalized_name}' does not exist")

        self.active = normalized_name
        logger.info(f"Set active workspace to '{normalized_name}'")

    @classmethod
    def load(cls, registry_path: Path | None = None, *, cache_manager_name: str | None = None) -> WorkspaceRegistry:
        """Load registry from JSON file.

        Args:
            registry_path: Explicit path to workspaces.json. If None, uses PathConfig.
            cache_manager_name: Ignored, kept for backward compatibility.

        Returns:
            Loaded WorkspaceRegistry instance.
        """
        if registry_path is None:
            registry_path = PathConfig().ai_workspace_file

        if not registry_path.exists():
            logger.debug(f"Registry not found at {registry_path}, creating new")
            return cls._create_default(registry_path)

        try:
            with registry_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            workspaces = {name: WorkspaceMetadata.from_dict(name, metadata) for name, metadata in data.get("workspaces", {}).items()}

            registry = cls(
                version=data.get("version", 1),
                workspaces=workspaces,
                active=data.get("active", DEFAULT_WORKSPACE),
                registry_path=registry_path,
            )
            logger.debug(f"Loaded workspace registry with {len(workspaces)} workspaces")
            return registry

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load registry from {registry_path}: {e}")
            return cls._create_default(registry_path)

    @classmethod
    def _create_default(cls, registry_path: Path | None = None, *, cache_manager_name: str | None = None) -> WorkspaceRegistry:
        """Create a new registry with default workspace.

        Args:
            registry_path: Optional explicit path to save to.
            cache_manager_name: Ignored, kept for backward compatibility.

        Returns:
            New WorkspaceRegistry instance with default workspace.
        """
        effective_path = registry_path or PathConfig().ai_workspace_file
        registry = cls(
            version=1,
            workspaces={
                DEFAULT_WORKSPACE: WorkspaceMetadata(
                    name=DEFAULT_WORKSPACE,
                    description="Default workspace",
                    auto_build=True,
                )
            },
            active=DEFAULT_WORKSPACE,
            registry_path=effective_path,
        )
        registry.save()
        return registry


def get_active_workspace(cache_manager_name: str | None = None) -> str:
    """Get the name of the currently active workspace.

    Args:
        cache_manager_name: Ignored, kept for backward compatibility.

    Returns:
        Name of the active workspace, or DEFAULT_WORKSPACE if none set.
    """
    registry = WorkspaceRegistry.load()
    return registry.active or DEFAULT_WORKSPACE


def set_active_workspace(name: str, cache_manager_name: str | None = None) -> None:
    """Set the active workspace.

    Args:
        name: Workspace name to set as active.
        cache_manager_name: Ignored, kept for backward compatibility.
    """
    registry = WorkspaceRegistry.load()
    normalized_name = normalize_workspace_name(name)
    if normalized_name not in registry.workspaces:
        raise ValueError(f"Workspace '{name}' does not exist")
    registry.active = normalized_name
    registry.save()
    logger.info(f"Set active workspace to '{normalized_name}'")


__all__ = [
    "DEFAULT_WORKSPACE",
    "WorkspaceMember",
    "WorkspaceMetadata",
    "WorkspaceRegistry",
    "get_active_workspace",
    "set_active_workspace",
]
