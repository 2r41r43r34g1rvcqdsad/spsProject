"""
Tenant Service - Manages tenant lifecycle and data

This service handles:
    1. Getting tenant information (with Redis caching)
    2. Managing tenant status transitions (state machine)
    3. Cache invalidation on updates

Features:
    - get_tenant(): Check Redis first (5 min TTL), fallback to Cosmos DB
    - transition_status(): Enforce valid state machine transitions
        Valid transitions:
        - provisioning -> active, trial, cancelled
        - trial -> active, suspended, cancelled
        - active -> suspended, cancelled
        - suspended -> active, cancelled
        - cancelled is terminal (no transitions out)
"""

import json
from typing import Optional
from app.db.tenant_scoped_repository import TenantScopedRepository
from app.db.cosmos_client import get_database
from app.db.redis_client import get_redis

# Valid state transitions (TDD-002, Section 4.2)
# Defines which status transitions are allowed for each current state
VALID_TRANSITIONS = {
    "provisioning": ["active", "trial", "cancelled"],
    "trial":        ["active", "suspended", "cancelled"],
    "active":       ["suspended", "cancelled"],
    "suspended":    ["active", "cancelled"],
    # "cancelled" is terminal — no transitions out
}


class TenantService:
    """
    Service for managing tenant lifecycle and data.
    
    Provides:
        - Tenant retrieval with caching
        - Status transition enforcement (state machine)
        - Cache invalidation
    
    Attributes:
        tenant_repo: Repository for tenant data persistence
        redis: Redis client for caching
    """
    
    def __init__(self, tenant_repo: TenantScopedRepository, redis):
        """
        Initialize TenantService.
        
        Args:
            tenant_repo: TenantScopedRepository instance for tenant data
            redis: Redis client for caching tenant data
        """
        self.repo = tenant_repo
        self.redis = redis
    
    async def get_tenant(self, tenant_id: str) -> Optional[dict]:
        """
        Get tenant information with caching.
        
        Flow:
            1. Check Redis cache with key "tenant:{tenant_id}"
            2. If cache hit, return parsed JSON
            3. If cache miss, query Cosmos DB by _id
            4. Cache result for 5 minutes (300 seconds TTL)
        
        Args:
            tenant_id: The unique tenant identifier
            
        Returns:
            Tenant document dict or None if not found
        """
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
        """
        Transition tenant to new status using state machine.
        
        Flow:
            1. Get current tenant status
            2. Validate transition is allowed (see VALID_TRANSITIONS)
            3. Update status in Cosmos DB
            4. Invalidate Redis cache immediately
        
        Args:
            tenant_id: The tenant to transition
            new_status: Target status
            
        Returns:
            True if transition successful
            
        Raises:
            ValueError: If transition is not allowed
        """
        # Get current tenant to determine current status
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            return False
        current = tenant["status"]
        
        # Validate transition against state machine
        if new_status not in VALID_TRANSITIONS.get(current, []):
            raise ValueError(
                f"Invalid transition: {current} -> {new_status}. "
                f"Allowed: {VALID_TRANSITIONS.get(current, [])}"
            )
        
        # Update status in database
        await self.repo._collection.update_one(
            {"_id": tenant_id}, {"$set": {"status": new_status}}
        )
        
        # Invalidate cache immediately (TDD-002, Section 11.1)
        # This forces next request to fetch fresh data
        await self.redis.delete(f"tenant:{tenant_id}")
        return True
