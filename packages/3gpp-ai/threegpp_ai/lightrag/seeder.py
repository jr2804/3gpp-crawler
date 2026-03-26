"""3GPP entity seeder for LightRAG knowledge graph.

This module provides utilities for seeding known 3GPP entities
into the LightRAG knowledge graph after document indexing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .rag import TDocRAG

logger = logging.getLogger(__name__)


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

    async def seed_tdoc(
        self,
        tdoc_id: str,
        title: str | None = None,
        meeting: str | None = None,
        wg: str | None = None,
        spec_refs: list[str] | None = None,
    ) -> bool:
        """Seed a TDoc entity with optional relationships.

        Args:
            tdoc_id: TDoc identifier (e.g., "S4-250001")
            title: Document title
            meeting: Meeting code (e.g., "SA4#131-bis")
            wg: Working group (e.g., "SA4")
            spec_refs: List of referenced specifications

        Returns:
            True if seeding was successful.
        """
        # Normalize tdoc_id
        tdoc_id = tdoc_id.strip().upper()

        # Create TDoc entity
        description = f"3GPP Temporary Document {tdoc_id}"
        if title:
            description += f": {title}"

        metadata: dict[str, Any] = {}
        if meeting:
            metadata["meeting"] = meeting
        if wg:
            metadata["working_group"] = wg
        if spec_refs:
            metadata["spec_refs"] = spec_refs

        seed = EntitySeed(
            name=tdoc_id,
            entity_type=EntityType.TDOC,
            description=description,
            metadata=metadata,
        )

        success = await self.seed_entity(seed)

        # Create relationships to specifications
        if success and spec_refs:
            for spec_ref in spec_refs:
                # Seed specification entity first
                await self.seed_specification(spec_ref)
                # Create relationship
                await self.rag._rag.acreate_relation(  # type: ignore[attr-defined]
                    tdoc_id,
                    spec_ref,
                    "REFERENCES",
                )

        # Create relationship to meeting
        if success and meeting:
            await self.seed_meeting(meeting, wg)
            await self.rag._rag.acreate_relation(  # type: ignore[attr-defined]
                tdoc_id,
                meeting,
                "PRESENTED_AT",
            )

        return success

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
        if release:
            metadata["release"] = release

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

    async def seed_working_group(
        self,
        wg_code: str,
        tsg: str | None = None,
        full_name: str | None = None,
    ) -> bool:
        """Seed a working group entity.

        Args:
            wg_code: Working group code (e.g., "SA4", "RAN1")
            tsg: Parent TSG (e.g., "SA", "RAN", "CT")
            full_name: Full working group name

        Returns:
            True if seeding was successful.
        """
        wg_code = wg_code.strip().upper()

        description = f"3GPP Working Group {wg_code}"
        if full_name:
            description += f": {full_name}"

        metadata: dict[str, Any] = {}
        if tsg:
            metadata["tsg"] = tsg.upper()
        if full_name:
            metadata["full_name"] = full_name

        seed = EntitySeed(
            name=wg_code,
            entity_type=EntityType.WORKING_GROUP,
            description=description,
            metadata=metadata,
        )

        return await self.seed_entity(seed)

    def get_stats(self) -> dict[str, int]:
        """Get seeding statistics.

        Returns:
            Dictionary with created, updated, and error counts.
        """
        return {
            "created": self._created_count,
            "updated": self._updated_count,
            "errors": self._error_count,
        }
