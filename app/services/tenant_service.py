import json
from typing import Optional
from app.db.tenant_scoped_repository import TenantScopedRepository
from app.db.cosmos_client import get_database
from app.db.redis_client import get_redis

# Valid state transitions (TDD-002, Section 4.2)
VALID_TRANSITIONS = {
    "provisioning": ["active", "trial", "cancelled"],
    "trial":        ["active", "suspended", "cancelled"],
    "active":       ["suspended", "cancelled"],
    "suspended":    ["active", "cancelled"],
    # "cancelled" is terminal — no transitions out
}

class TenantService:
    def __init__(self, tenant_repo: TenantScopedRepository, redis):
        self.repo = tenant_repo
        self.redis = redis
    
    async def get_tenant(self, tenant_id: str) -> Optional[dict]:
        """Redis cache (5 min TTL) -> Cosmos DB fallback (TDD-002, Section 11.1)"""
        cache_key = f"tenant:{tenant_id}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Cosmos DB fallback — use tenantId as both scope AND filter
        # For tenant lookup, we query by _id which equals tenantId
        tenant = await self.repo._collection.find_one({"_id": tenant_id})
        if tenant:
            tenant["_id"] = str(tenant["_id"])
            await self.redis.set(cache_key, json.dumps(tenant), ex=300)  # 5 min TTL
        return tenant
    
    async def transition_status(self, tenant_id: str, new_status: str) -> bool:
        """Enforce lifecycle state machine. Returns False if transition invalid."""
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        current = tenant["status"]
        if new_status not in VALID_TRANSITIONS.get(current, []):
            raise ValueError(
                f"Invalid transition: {current} -> {new_status}. "
                f"Allowed: {VALID_TRANSITIONS.get(current, [])}"
            )
        await self.repo._collection.update_one(
            {"_id": tenant_id}, {"$set": {"status": new_status}}
        )
        # Invalidate cache immediately (TDD-002, Section 11.1)
        await self.redis.delete(f"tenant:{tenant_id}")
        return True
