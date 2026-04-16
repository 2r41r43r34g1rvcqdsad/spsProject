"""
Tenant Middleware - Enforces Tenant Isolation

This middleware ensures that all API requests have a valid tenant context.
It acts as a gatekeeper before any request reaches the route handlers.

Features:
    1. Excluded paths - Skip tenant check for health/docs endpoints
    2. Header validation - Ensure x-tenant-id header is present
    3. Tenant existence - Verify tenant exists in database
    4. Tenant status - Ensure tenant is active/trial (not suspended)

Request Flow:
    1. Request arrives
    2. If path in EXCLUDED_PATHS: Allow through
    3. If no x-tenant-id header: 400 error
    4. If tenant not found: 403 error
    5. If status not active/trial: 403 error
    6. Otherwise: Set request.state and continue

Excluded Paths:
    - /health
    - /ready
    - /docs
    - /redoc
    - /openapi.json

Response Codes:
    - 400: Missing tenant context (no x-tenant-id header)
    - 403: Tenant not found or status not active/trial
    - 503: Tenant service not initialized
"""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Paths that don't require tenant context
# These are typically system/health endpoints
EXCLUDED_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces tenant isolation on all API requests.
    
    Checks performed (in order):
        1. Is path excluded from check?
        2. Is x-tenant-id header present?
        3. Does tenant exist in database?
        4. Is tenant status active or trial?
    
    Sets on successful check:
        - request.state.tenant: The full tenant document
        - request.state.tenant_id: The tenant identifier
    
    Returns errors if any check fails before passing to handler.
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process each request through tenant validation.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            Response from next handler, or error response
        """
        # Get the requested path
        path = request.url.path
        
        # 1. Skip tenant check for excluded paths (health, docs, etc.)
        if path in EXCLUDED_PATHS:
            return await call_next(request)
        
        # 2. Check for x-tenant-id header
        tenant_id = request.headers.get("x-tenant-id")
        if not tenant_id:
            return JSONResponse(
                status_code=400, 
                content={"detail": "Missing tenant context"}
            )
        
        # 3. Get tenant service from app state
        tenant_service = getattr(request.app.state, "tenant_service", None)
        if tenant_service is None:
            return JSONResponse(
                status_code=503, 
                content={"detail": "Tenant service not initialized"}
            )
        
        # 4. Verify tenant exists
        tenant = await tenant_service.get_tenant(tenant_id)
        if not tenant:
            return JSONResponse(
                status_code=403, 
                content={"detail": "Tenant not found"}
            )
        
        # 5. Verify tenant is active or trial (not suspended/cancelled)
        if tenant.get("status") not in {"active", "trial"}:
            return JSONResponse(
                status_code=403,
                content={"detail": f"Tenant access denied: status={tenant.get('status')}"},
            )
        
        # All checks passed - set tenant info on request state
        request.state.tenant = tenant
        request.state.tenant_id = tenant_id
        
        # Continue to route handler
        return await call_next(request)