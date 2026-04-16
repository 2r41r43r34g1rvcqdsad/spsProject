from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.cosmos_client import get_database
from app.db.redis_client import get_redis
from app.db.tenant_scoped_repository import TenantScopedRepository
from app.middleware.tenant_middleware import TenantMiddleware
from app.routers import (
    admin_feature_flags,
    admin_tenants,
    tenant_feature_flags,
    tenant_users,
)
from app.services.audit_service import AuditService
from app.services.feature_flag_service import FeatureFlagService
from app.services.tenant_service import TenantService
from app.services.user_role_service import UserRoleService


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await get_database()
    redis = await get_redis()

    tenant_repo = TenantScopedRepository(db, "tenants")
    user_role_repo = TenantScopedRepository(db, "user_roles")
    feature_flag_repo = TenantScopedRepository(db, "feature_flags")
    audit_repo = TenantScopedRepository(db, "audit_logs")

    app.state.tenant_service = TenantService(tenant_repo, redis)
    app.state.user_role_service = UserRoleService(user_role_repo, redis)
    app.state.feature_flag_service = FeatureFlagService(feature_flag_repo, redis)
    app.state.audit_service = AuditService(audit_repo)
    app.state.redis = redis

    yield

    close = getattr(redis, "close", None)
    if close:
        result = close()
        if hasattr(result, "__await__"):
            await result


app = FastAPI(title="SPARC API", version="1.0.0", lifespan=lifespan)
app.add_middleware(TenantMiddleware)

app.include_router(admin_tenants.router)
app.include_router(admin_feature_flags.router)
app.include_router(tenant_users.router)
app.include_router(tenant_feature_flags.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    redis = getattr(app.state, "redis", None)
    if redis is None:
        return {"status": "not_ready"}
    ping = getattr(redis, "ping", None)
    if ping is None:
        return {"status": "ready"}
    result = ping()
    if hasattr(result, "__await__"):
        await result
    return {"status": "ready"}
