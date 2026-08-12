"""
Generic Base Repository — Async MongoDB CRUD operations
Implements the Repository Pattern for clean separation of data access logic.
All collection-specific repositories inherit from this class.
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

import structlog
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Generic async repository providing standard CRUD operations.
    Uses Motor for non-blocking MongoDB access.

    Type parameter T is not strictly enforced at runtime — it serves
    as documentation for the expected document type.
    """

    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str) -> None:  # type: ignore[type-arg]
        self._collection = db[collection_name]
        self._collection_name = collection_name

    async def find_by_id(self, doc_id: str) -> dict[str, Any] | None:
        """
        Fetch a single document by its MongoDB ObjectId.

        Args:
            doc_id: String representation of the ObjectId.

        Returns:
            Document dict or None if not found.
        """
        if not ObjectId.is_valid(doc_id):
            return None
        doc = await self._collection.find_one({"_id": ObjectId(doc_id)})
        return self._serialize(doc) if doc else None

    async def find_one(self, filter: dict[str, Any]) -> dict[str, Any] | None:
        """Find a single document matching the filter."""
        doc = await self._collection.find_one(filter)
        return self._serialize(doc) if doc else None

    async def find_many(
        self,
        filter: dict[str, Any] | None = None,
        sort: list[tuple[str, int]] | None = None,
        skip: int = 0,
        limit: int = 20,
        projection: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch multiple documents with filtering, sorting and pagination.

        Args:
            filter: MongoDB query filter dict.
            sort: List of (field, direction) tuples.
            skip: Number of documents to skip (for pagination).
            limit: Maximum documents to return.
            projection: Fields to include/exclude.

        Returns:
            List of serialized document dicts.
        """
        filter = filter or {}
        cursor = self._collection.find(filter, projection)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self._serialize(doc) for doc in docs]

    async def count(self, filter: dict[str, Any] | None = None) -> int:
        """Count documents matching the filter."""
        return await self._collection.count_documents(filter or {})

    async def insert_one(self, data: dict[str, Any]) -> str:
        """
        Insert a single document.

        Args:
            data: Document data dict (without _id).

        Returns:
            String representation of the new document's ObjectId.
        """
        now = datetime.utcnow()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        result = await self._collection.insert_one(data)
        return str(result.inserted_id)

    async def update_one(
        self,
        doc_id: str,
        update_data: dict[str, Any],
    ) -> bool:
        """
        Update a document by ID. Automatically sets updated_at.

        Args:
            doc_id: ObjectId string of the document to update.
            update_data: Fields to update (without $set wrapper).

        Returns:
            True if a document was modified, False otherwise.
        """
        if not ObjectId.is_valid(doc_id):
            return False
        update_data["updated_at"] = datetime.utcnow()
        result = await self._collection.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": update_data},
        )
        return result.modified_count > 0

    async def upsert_one(
        self,
        filter: dict[str, Any],
        update_data: dict[str, Any],
    ) -> str:
        """
        Insert or update a document matching the filter.

        Returns:
            String ObjectId of the upserted document.
        """
        update_data["updated_at"] = datetime.utcnow()
        result = await self._collection.update_one(
            filter,
            {"$set": update_data, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True,
        )
        if result.upserted_id:
            return str(result.upserted_id)
        doc = await self.find_one(filter)
        return doc["id"] if doc else ""

    async def delete_one(self, doc_id: str) -> bool:
        """Delete a document by ID. Returns True if deleted."""
        if not ObjectId.is_valid(doc_id):
            return False
        result = await self._collection.delete_one({"_id": ObjectId(doc_id)})
        return result.deleted_count > 0

    async def aggregate(self, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run a MongoDB aggregation pipeline."""
        cursor = self._collection.aggregate(pipeline)
        return await cursor.to_list(length=None)

    @staticmethod
    def _serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
        """Convert MongoDB document's ObjectId to string 'id' field."""
        if doc is None:
            return None
        doc = dict(doc)
        if "_id" in doc:
            doc["id"] = str(doc.pop("_id"))
        return doc
