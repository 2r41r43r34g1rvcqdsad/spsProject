from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.config import settings

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ModuleNotFoundError:  # pragma: no cover - optional local fallback
    AsyncIOMotorClient = None


@dataclass
class InMemoryInsertResult:
    inserted_id: str


@dataclass
class InMemoryUpdateResult:
    matched_count: int
    modified_count: int
    upserted_id: Optional[str] = None


@dataclass
class InMemoryDeleteResult:
    deleted_count: int


class InMemoryCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs
        self._skip = 0
        self._limit = None

    def skip(self, count: int) -> "InMemoryCursor":
        self._skip = max(0, count)
        return self

    def limit(self, count: int) -> "InMemoryCursor":
        self._limit = max(0, count)
        return self

    async def to_list(self, length: Optional[int] = None) -> List[Dict[str, Any]]:
        docs = self._docs[self._skip :]
        max_len = length if length is not None else self._limit
        if max_len is not None:
            docs = docs[:max_len]
        return [doc.copy() for doc in docs]


class InMemoryCollection:
    def __init__(self) -> None:
        self._documents: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _matches(doc: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        for key, expected in filter_dict.items():
            if doc.get(key) != expected:
                return False
        return True

    async def find_one(self, filter_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for doc in self._documents.values():
            if self._matches(doc, filter_dict):
                return doc.copy()
        return None

    def find(self, filter_dict: Dict[str, Any]) -> InMemoryCursor:
        matched = [
            doc.copy()
            for doc in self._documents.values()
            if self._matches(doc, filter_dict)
        ]
        return InMemoryCursor(matched)

    async def insert_one(self, document: Dict[str, Any]) -> InMemoryInsertResult:
        doc = document.copy()
        doc_id = str(doc.get("_id") or uuid.uuid4().hex)
        doc["_id"] = doc_id
        self._documents[doc_id] = doc
        return InMemoryInsertResult(inserted_id=doc_id)

    async def update_one(
        self, filter_dict: Dict[str, Any], update: Dict[str, Any], upsert: bool = False
    ) -> InMemoryUpdateResult:
        set_values = update.get("$set", {})
        for doc_id, doc in self._documents.items():
            if self._matches(doc, filter_dict):
                updated = doc.copy()
                updated.update(set_values)
                self._documents[doc_id] = updated
                return InMemoryUpdateResult(matched_count=1, modified_count=1)

        if upsert:
            new_doc = filter_dict.copy()
            new_doc.update(set_values)
            doc_id = str(new_doc.get("_id") or uuid.uuid4().hex)
            new_doc["_id"] = doc_id
            self._documents[doc_id] = new_doc
            return InMemoryUpdateResult(
                matched_count=0, modified_count=0, upserted_id=doc_id
            )

        return InMemoryUpdateResult(matched_count=0, modified_count=0)

    async def delete_one(self, filter_dict: Dict[str, Any]) -> InMemoryDeleteResult:
        for doc_id, doc in list(self._documents.items()):
            if self._matches(doc, filter_dict):
                del self._documents[doc_id]
                return InMemoryDeleteResult(deleted_count=1)
        return InMemoryDeleteResult(deleted_count=0)


class InMemoryDatabase:
    def __init__(self) -> None:
        self._collections: Dict[str, InMemoryCollection] = {}

    def __getitem__(self, name: str) -> InMemoryCollection:
        if name not in self._collections:
            self._collections[name] = InMemoryCollection()
        return self._collections[name]


_db_instance: Optional[Any] = None
_motor_client: Optional[Any] = None


async def get_database() -> Any:
    """Return Cosmos/Mongo database handle or an in-memory fallback."""

    global _db_instance, _motor_client
    if _db_instance is not None:
        return _db_instance

    if settings.cosmos_connection_string and AsyncIOMotorClient is not None:
        _motor_client = AsyncIOMotorClient(settings.cosmos_connection_string)
        _db_instance = _motor_client[settings.cosmos_database_name]
        return _db_instance

    _db_instance = InMemoryDatabase()
    return _db_instance
