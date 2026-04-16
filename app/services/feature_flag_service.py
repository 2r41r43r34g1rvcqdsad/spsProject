from app.db.tenant_scoped_repository import TenantScopedRepository
from app.db.redis_client import get_redis
from app.db.cosmos_client import get_database

class FeatureFlagService:
    def __init__(self, flag_repo: TenantScopedRepository, redis):
        self.repo = flag_repo
        self.redis = redis
    
    async def is_enabled(self, tenant_id: str, flag_key: str) -> bool:
        """Check flag: Redis cache (60s TTL) -> tenant-specific -> GLOBAL fallback"""
        cache_key = f"ff:{tenant_id}:{flag_key}"
        cached = await self.redis.get(cache_key)
        if cached is not None:
            return cached == "true"
        
        # Tenant-specific flag first
        flag = await self.repo.find_one(tenant_id, {"flagKey": flag_key})
        if not flag:
            # Fall back to GLOBAL default
            flag = await self.repo.find_one("GLOBAL", {"flagKey": flag_key})
        
        result = flag["enabled"] if flag else False
        await self.redis.set(cache_key, str(result).lower(), ex=60)  # 60s TTL
        return result
    
    async def set_flag(self, tenant_id: str, flag_key: str, 
                       enabled: bool, modified_by: str):
        """Super Admin only - toggle flag and invalidate cache"""
        from datetime import datetime, timezone
        update_data = {
            "flagKey": flag_key,
            "enabled": enabled,
            "lastModifiedBy": modified_by,
            "lastModifiedAt": datetime.now(timezone.utc).isoformat()
        }
        await self.repo.update_one(tenant_id, {"flagKey": flag_key}, update_data)
        await self.redis.delete(f"ff:{tenant_id}:{flag_key}")

