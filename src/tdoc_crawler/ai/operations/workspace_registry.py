"""Workspace registry management for AI workspaces.

This module provides a centralized registry for workspace metadata,
stored in a JSON file at ~/.tdoc-crawler/.ai/workspaces.json.
"""


from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tdoc_crawler.config import resolve_cache_manager
from tdoc_crawler.utils.misc import utc_now

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE = "default"


@dataclass
class WorkspaceMetadata:
    """Metadata for a single workspace."""

    name: str
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    description: str = ""
    auto_build: bool = True
    member_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "created_at": self.created_at,
            "description": self.description,
            "auto_build": self.auto_build,
            "member_count": self.member_count,
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> WorkspaceMetadata:
        """Create from dictionary."""
        return cls(
            name=name,
            created_at=data.get("created_at", utc_now().isoformat()),
            description=data.get("description", ""),
            auto_build=data.get("auto_build", True),
            member_count=data.get("member_count", 0),
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
    cache_manager_name: str | None = None

    def save(
        self,
    ) -> None:
        """Save registry to JSON file."""
        registry_path = resolve_cache_manager(self.cache_manager_name).ai_workspace_file

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
        normalized_name = name.strip().lower()
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
        normalized_name = name.strip().lower()
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
        normalized_name = name.strip().lower() if name else DEFAULT_WORKSPACE
        return self.workspaces.get(normalized_name)

    def list_workspaces(self, storage: Any | None = None) -> list[WorkspaceDisplayInfo]:
        """List all workspaces with member counts.

        Args:
            storage: Optional AiStorage instance for getting member counts.

        Returns:
            List of WorkspaceDisplayInfo objects with member counts.
        """
        from tdoc_crawler.ai.config import AiConfig
        from tdoc_crawler.ai.storage import AiStorage

        if storage is None:
            config = AiConfig.from_env()
            storage = AiStorage(config.ai_cache_dir)  # type: ignore[arg-type]

        active_name = self.active or DEFAULT_WORKSPACE
        result = []

        for metadata in self.workspaces.values():
            counts = storage.get_workspace_member_counts(metadata.name)
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
        normalized_name = name.strip().lower()
        if normalized_name not in self.workspaces:
            raise ValueError(f"Workspace '{normalized_name}' does not exist")

        self.active = normalized_name
        logger.info(f"Set active workspace to '{normalized_name}'")

    def get_active(self) -> WorkspaceMetadata:
        """Get the active workspace metadata.

        Returns:
            Active WorkspaceMetadata.
        """
        metadata = self.workspaces.get(self.active)
        if metadata is None:
            # Fallback to default if active is invalid
            self.active = DEFAULT_WORKSPACE
            metadata = self.workspaces[DEFAULT_WORKSPACE]
        return metadata

    def update_member_count(self, name: str, count: int) -> None:
        """Update the member count for a workspace.

        Args:
            name: Workspace name.
            count: New member count.
        """
        normalized_name = name.strip().lower()
        if normalized_name in self.workspaces:
            self.workspaces[normalized_name].member_count = count

    @classmethod
    def load(cls, registry_path: Path | None = None, *, cache_manager_name: str | None = None) -> WorkspaceRegistry:
        """Load registry from JSON file.

        Args:
            registry_path: Explicit path to workspaces.json. If None, uses CacheManager.
            cache_manager_name: Cache manager name (used if registry_path is None).

        Returns:
            Loaded WorkspaceRegistry instance.
        """
        if registry_path is None:
            registry_path = resolve_cache_manager(cache_manager_name).ai_workspace_file

        if not registry_path.exists():
            logger.debug(f"Registry not found at {registry_path}, creating new")
            return cls._create_default(registry_path, cache_manager_name=cache_manager_name)

        try:
            with registry_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            workspaces = {name: WorkspaceMetadata.from_dict(name, metadata) for name, metadata in data.get("workspaces", {}).items()}

            registry = cls(
                version=data.get("version", 1),
                workspaces=workspaces,
                active=data.get("active", DEFAULT_WORKSPACE),
                cache_manager_name=cache_manager_name,
            )
            logger.debug(f"Loaded workspace registry with {len(workspaces)} workspaces")
            return registry

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load registry from {registry_path}: {e}")
            return cls._create_default(registry_path, cache_manager_name=cache_manager_name)

    @classmethod
    def _create_default(cls, registry_path: Path | None = None, *, cache_manager_name: str | None = None) -> WorkspaceRegistry:
        """Create a new registry with default workspace.

        Args:
            registry_path: Optional explicit path to save to (used if cache_manager_name is also None).
            cache_manager_name: Cache manager name for path resolution.

        Returns:
            New WorkspaceRegistry instance with default workspace.
        """
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
            cache_manager_name=cache_manager_name,
        )

        # Save if we have a path (either explicit or from cache manager)
        if registry_path is not None:
            registry.save()
        elif cache_manager_name is not None:
            # Use cache manager to get path
            registry_path = resolve_cache_manager(cache_manager_name).ai_workspace_file
            registry.save()


def get_active_workspace(cache_manager_name: str | None = None) -> str:
    """Get the name of the currently active workspace.

    Args:
        cache_manager_name: Optional cache manager name. If None, uses default.

    Returns:
        Name of the active workspace, or DEFAULT_WORKSPACE if none set.
    """
    from tdoc_crawler.config import CacheManager

    manager_name = cache_manager_name or "default"
    try:
        resolve_cache_manager(manager_name)
    except ValueError:
        CacheManager(name=manager_name).register()

    registry = WorkspaceRegistry.load(cache_manager_name=cache_manager_name)
    return registry.active or DEFAULT_WORKSPACE



def set_active_workspace(name: str, cache_manager_name: str | None = None) -> None:
    """Set the active workspace.

    Args:
        name: Workspace name to set as active.
        cache_manager_name: Optional cache manager name.
    """
    # Ensure cache manager is registered before loading registry
    from tdoc_crawler.config import CacheManager
    manager_name = cache_manager_name or "default"
    try:
        resolve_cache_manager(manager_name)
    except ValueError:
        CacheManager(name=manager_name).register()

    from tdoc_crawler.ai.operations.workspaces import normalize_workspace_name
    registry = WorkspaceRegistry.load(cache_manager_name=cache_manager_name)
    normalized_name = normalize_workspace_name(name)
    if normalized_name not in registry.workspaces:
        raise ValueError(f"Workspace '{name}' does not exist")
    registry.active = normalized_name
    registry.save()
    logger.info(f"Set active workspace to '{normalized_name}'")

__all__ = [
    "DEFAULT_WORKSPACE",
    "WorkspaceMetadata",
    "WorkspaceRegistry",
    "get_active_workspace",
    "set_active_workspace",
]
