from datetime import datetime, timezone
import uuid
from app.db.tenant_scoped_repository import TenantScopedRepository

class AuditService:
    def __init__(self, repo: TenantScopedRepository):
        self.repo = repo

    async def log_event(self, tenant_id: str, action: str, actor_role: str = "",
                        details: dict = None, outcome: str = "success",
                        actor_user_id: str = "", actor_email: str = ""):
        """Write-once audit log. No updates or deletes (Cosmos DB RBAC enforces)."""
        audit_doc = {
            "auditId": f"aud_{uuid.uuid4().hex[:12]}",
            "action": action,
            "actor": {
                "userId": actor_user_id,
                "email": actor_email,
                "role": actor_role
            },
            "details": details or {},
            "outcome": outcome,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_schema_version": "1.0"
        }
        await self.repo.insert_one(tenant_id, audit_doc)
