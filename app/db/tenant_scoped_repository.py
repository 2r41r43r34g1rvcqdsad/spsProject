from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TenantScopedRepository:
    """Base repository for all persistence access.

    Every tenant operation injects `tenantId` into the query filter so data is
    always isolated by tenant.
    """

    def __init__(self, db: Any, collection_name: str):
        self._collection = db[collection_name]

    @staticmethod
    def _scoped_filter(
        tenant_id: str, additional_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        filter_dict: Dict[str, Any] = {"tenantId": tenant_id}
        if additional_filter:
            filter_dict.update(additional_filter)
        return filter_dict

    async def find_one(
        self, tenant_id: str, filter_dict: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        return await self._collection.find_one(
            self._scoped_filter(tenant_id, filter_dict or {})
        )

    async def find_many(
        self,
        tenant_id: str,
        filter_dict: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        cursor = (
            self._collection.find(self._scoped_filter(tenant_id, filter_dict or {}))
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def find_many_unscoped(
        self, filter_dict: Optional[Dict[str, Any]] = None, skip: int = 0, limit: int = 50
    ) -> List[Dict[str, Any]]:
        cursor = self._collection.find(filter_dict or {}).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def insert_one(self, tenant_id: str, document: Dict[str, Any]) -> str:
        now = datetime.now(timezone.utc).isoformat()
        payload = document.copy()
        payload["tenantId"] = tenant_id
        payload["updatedAt"] = payload.get("updatedAt", now)
        payload["createdAt"] = payload.get("createdAt", now)
        result = await self._collection.insert_one(payload)
        return str(result.inserted_id)

    async def update_one(
        self, tenant_id: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]
    ) -> bool:
        payload = update_dict.copy()
        payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
        result = await self._collection.update_one(
            self._scoped_filter(tenant_id, filter_dict), {"$set": payload}
        )
        return bool(getattr(result, "matched_count", 0))

    async def upsert_one(
        self, tenant_id: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]
    ) -> bool:
        payload = update_dict.copy()
        payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
        result = await self._collection.update_one(
            self._scoped_filter(tenant_id, filter_dict), {"$set": payload}, upsert=True
        )
        return bool(
            getattr(result, "matched_count", 0)
            or getattr(result, "modified_count", 0)
            or getattr(result, "upserted_id", None)
        )

    async def delete_one(self, tenant_id: str, filter_dict: Dict[str, Any]) -> bool:
        result = await self._collection.delete_one(
            self._scoped_filter(tenant_id, filter_dict)
        )
        return bool(getattr(result, "deleted_count", 0))
