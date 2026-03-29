"""3GPP entity seeder for LightRAG knowledge graph.

This module provides utilities for seeding known 3GPP entities
into the LightRAG knowledge graph after document indexing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from tdoc_crawler.logging import get_logger

from .metadata import normalize_release_label
from .rag import TDocRAG

logger = get_logger(__name__)


class EntityType(StrEnum):
    """Types of 3GPP entities that can be seeded."""

    TDOC = "TDoc"
    SPECIFICATION = "Specification"
    MEETING = "Meeting"
    WORKING_GROUP = "Working Group"
    RELEASE = "Release"
    COMPANY = "Company"


@dataclass
class EntitySeed:
    """Seed data for creating a 3GPP entity.

    Attributes:
        name: Entity name (e.g., "S4-250001", "TS 26.444")
        entity_type: Type of entity from EntityType enum
        description: Human-readable description
        metadata: Additional key-value metadata for the entity
    """

    name: str
    entity_type: EntityType
    description: str
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for LightRAG entity creation."""
        result: dict[str, Any] = {
            "entity_type": self.entity_type.value,
            "description": self.description,
            "source": "seeded",  # Mark as manually seeded
        }
        if self.metadata:
            result.update(self.metadata)
        return result


class EntitySeeder:
    """Seeds 3GPP entities into LightRAG knowledge graph.

    This class provides methods for creating entities and relationships
    from structured metadata (e.g., SQLite database) after document
    indexing is complete.

    Args:
        rag: TDocRAG instance (must be started before seeding)

    Example:
        >>> async with TDocRAG() as rag:
        ...     await rag.start("default")
        ...     seeder = EntitySeeder(rag)
        ...     await seeder.seed_tdoc("S4-250001", "TS 26.444")
        ...     await rag.stop()
    """

    def __init__(self, rag: TDocRAG) -> None:
        self.rag = rag
        self._created_count = 0
        self._updated_count = 0
        self._error_count = 0

    async def seed_entity(self, seed: EntitySeed) -> bool:
        """Seed a single entity into the knowledge graph.

        Args:
            seed: EntitySeed with entity data.

        Returns:
            True if entity was created/updated successfully.
        """
        if not self.rag.is_started:
            raise RuntimeError("TDocRAG not started. Call start() first.")

        try:
            # Check if entity already exists
            existing = await self.rag._rag.get_entity_info(seed.name)  # type: ignore[attr-defined]

            if existing:
                # Update existing entity
                await self.rag._rag.aedit_entity(  # type: ignore[attr-defined]
                    seed.name,
                    seed.to_dict(),
                )
                self._updated_count += 1
                logger.debug("Updated entity: %s (%s)", seed.name, seed.entity_type)
            else:
                # Create new entity
                await self.rag._rag.acreate_entity(  # type: ignore[attr-defined]
                    seed.name,
                    seed.to_dict(),
                )
                self._created_count += 1
                logger.debug("Created entity: %s (%s)", seed.name, seed.entity_type)

            return True

        except Exception as e:
            logger.error("Failed to seed entity %s: %s", seed.name, e)
            self._error_count += 1
            return False

    async def seed_specification(
        self,
        spec_number: str,
        title: str | None = None,
        release: str | None = None,
    ) -> bool:
        """Seed a specification entity.

        Args:
            spec_number: Specification number (e.g., "TS 26.444")
            title: Specification title
            release: 3GPP release (e.g., "Rel-18")

        Returns:
            True if seeding was successful.
        """
        spec_number = spec_number.strip()

        description = f"3GPP Specification {spec_number}"
        if title:
            description += f": {title}"

        metadata: dict[str, Any] = {}
        normalized_release = normalize_release_label(release)
        if normalized_release:
            metadata["release"] = normalized_release

        seed = EntitySeed(
            name=spec_number,
            entity_type=EntityType.SPECIFICATION,
            description=description,
            metadata=metadata,
        )

        return await self.seed_entity(seed)

    async def seed_meeting(
        self,
        meeting_code: str,
        wg: str | None = None,
        location: str | None = None,
        date: str | None = None,
    ) -> bool:
        """Seed a meeting entity.

        Args:
            meeting_code: Meeting code (e.g., "SA4#131-bis")
            wg: Working group (e.g., "SA4")
            location: Meeting location
            date: Meeting date

        Returns:
            True if seeding was successful.
        """
        meeting_code = meeting_code.strip()

        description = f"3GPP Meeting {meeting_code}"
        if wg:
            description += f" ({wg})"

        metadata: dict[str, Any] = {}
        if wg:
            metadata["working_group"] = wg
        if location:
            metadata["location"] = location
        if date:
            metadata["date"] = date

        seed = EntitySeed(
            name=meeting_code,
            entity_type=EntityType.MEETING,
            description=description,
            metadata=metadata,
        )

        return await self.seed_entity(seed)
