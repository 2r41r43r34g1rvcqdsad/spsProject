import json
from typing import Optional, List
from app.db.tenant_scoped_repository import TenantScopedRepository


class UserRoleService:
    def __init__(self, user_role_repo: TenantScopedRepository, redis):
        self.repo = user_role_repo
        self.redis = redis

    async def get_user_role(self, tenant_id: str, user_id: str) -> Optional[dict]:
        cache_key = f"user_role:{user_id}:{tenant_id}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        user_role = await self.repo.find_one(tenant_id, {"userId": user_id})
        if user_role:
            await self.redis.set(cache_key, json.dumps(user_role), ex=300)
        return user_role

    async def set_user_role(
        self, tenant_id: str, user_id: str, role: str, assigned_by: str
    ) -> bool:
        from datetime import datetime, timezone
        update_data = {
            "userId": user_id,
            "role": role,
            "assignedBy": assigned_by,
            "assignedAt": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
        success = await self.repo.upsert_one(
            tenant_id, {"userId": user_id}, update_data
        )
        await self.redis.delete(f"user_role:{user_id}:{tenant_id}")
        return success

    async def list_users(self, tenant_id: str, skip: int = 0, limit: int = 50) -> List[dict]:
        return await self.repo.find_many(tenant_id, {}, skip, limit)
