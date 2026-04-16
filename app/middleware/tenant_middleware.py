from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

EXCLUDED_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in EXCLUDED_PATHS:
            return await call_next(request)

        tenant_id = request.headers.get("x-tenant-id")
        if not tenant_id:
            return JSONResponse(
                status_code=400, content={"detail": "Missing tenant context"}
            )

        tenant_service = getattr(request.app.state, "tenant_service", None)
        if tenant_service is None:
            return JSONResponse(
                status_code=503, content={"detail": "Tenant service not initialized"}
            )

        tenant = await tenant_service.get_tenant(tenant_id)
        if not tenant:
            return JSONResponse(status_code=403, content={"detail": "Tenant not found"})

        if tenant.get("status") not in {"active", "trial"}:
            return JSONResponse(
                status_code=403,
                content={"detail": f"Tenant access denied: status={tenant.get('status')}"},
            )

        request.state.tenant = tenant
        request.state.tenant_id = tenant_id
        return await call_next(request)
