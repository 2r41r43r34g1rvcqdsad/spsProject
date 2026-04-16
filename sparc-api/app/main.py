"""
SPARC API - Main Application Entry Point

This module initializes the FastAPI application and manages the application lifecycle.
It sets up database connections, Redis caching, middleware, and registers all routers.

Features:
    1. lifespan() - Async context manager that runs on startup/shutdown:
        - Initializes Cosmos DB (or falls back to in-memory)
        - Initializes Redis (or falls back to in-memory)
        - Creates repositories for: tenants, user_roles, feature_flags, audit_logs
        - Creates services: TenantService, UserRoleService, FeatureFlagService, AuditService
        - Stores services in app.state for access across all endpoints
        - On shutdown: closes Redis connection
    
    2. Health & Readiness endpoints:
        - /health - Returns {"status": "ok"} (no dependencies checked)
        - /ready - Checks if Redis is available (returns ready or not_ready)
    
    3. Middleware: TenantMiddleware - Enforces tenant isolation on all routes except excluded paths
    
    4. Routers included:
        - /admin/tenants - Super admin tenant management
        - /admin/feature-flags - Super admin feature flag management
        - /tenant/users - Tenant user management
        - /tenant/feature-flags - Tenant feature flags

Usage:
    - Run with: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    - Access docs at: http://localhost:8000/docs
"""

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
    """
    Application lifecycle manager.
    
    On STARTUP:
        1. Initialize database connection (Cosmos DB or in-memory fallback)
        2. Initialize Redis connection (Redis or in-memory fallback)
        3. Create repositories for each data type:
           - TenantScopedRepository for "tenants" collection
           - TenantScopedRepository for "user_roles" collection
           - TenantScopedRepository for "feature_flags" collection
           - TenantScopedRepository for "audit_logs" collection
        4. Create service instances with their repositories:
           - TenantService: Get tenant, transition status, cache management
           - UserRoleService: Get/set user roles, cache management
           - FeatureFlagService: Check/enable feature flags, cache management
           - AuditService: Log all API events for auditing
        5. Store all services in app.state for access by endpoints
    
    On SHUTDOWN:
        - Close Redis connection if available
    """
    # Initialize database (Cosmos DB or in-memory fallback)
    db = await get_database()
    
    # Initialize Redis (Redis or in-memory fallback)
    redis = await get_redis()

    # Create repositories - each scoped to a specific collection
    # Tenant data isolation is enforced by TenantScopedRepository
    tenant_repo = TenantScopedRepository(db, "tenants")
    user_role_repo = TenantScopedRepository(db, "user_roles")
    feature_flag_repo = TenantScopedRepository(db, "feature_flags")
    audit_repo = TenantScopedRepository(db, "audit_logs")

    # Initialize services with their repositories and Redis for caching
    app.state.tenant_service = TenantService(tenant_repo, redis)
    app.state.user_role_service = UserRoleService(user_role_repo, redis)
    app.state.feature_flag_service = FeatureFlagService(feature_flag_repo, redis)
    app.state.audit_service = AuditService(audit_repo)
    app.state.redis = redis  # Store Redis for health checks

    yield  # Application runs here

    # Cleanup on shutdown - close Redis connection if it has a close method
    close = getattr(redis, "close", None)
    if close:
        result = close()
        if hasattr(result, "__Await__"):
            await result


# Create FastAPI application with title, version, and lifespan management
app = FastAPI(title="SPARC API", version="1.0.0", lifespan=lifespan)

# Add TenantMiddleware to enforce tenant isolation on all requests
# Excluded paths: /health, /ready, /docs, /redoc, /openapi.json
app.add_middleware(TenantMiddleware)

# Register all routers
app.include_router(admin_tenants.router)       # /admin/tenants - super admin only
app.include_router(admin_feature_flags.router)  # /admin/feature-flags - super admin only
app.include_router(tenant_users.router)         # /tenant/users - tenant admin only
app.include_router(tenant_feature_flags.router) # /tenant/feature-flags - tenant admin only


@app.get("/health")
async def health() -> dict[str, str]:
    """
    Health check endpoint.
    
    Returns simple status without checking any dependencies.
    Used by load balancers and orchestrators to check if app is running.
    
    Returns:
        {"status": "ok"}
    """
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    """
    Readiness check endpoint.
    
    Checks if Redis is available to handle requests.
    Used to ensure app is fully ready to receive traffic.
    
    Returns:
        {"status": "ready"} - Redis is available
        {"status": "not_ready"} - Redis not initialized
        {"status": "ready"} - Redis has no ping method (fallback)
    """
    redis = getattr(app.state, "redis", None)
    if redis is None:
        return {"status": "not_ready"}
    ping = getattr(redis, "ping", None)
    if ping is None:
        return {"status": "ready"}
    result = ping()
    if hasattr(result, "__Await__"):
        await result
    return {"status": "ready"}
