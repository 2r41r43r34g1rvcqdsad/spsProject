from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.auth.rbac import require_role
from app.services.tenant_service import TenantService
from app.db.tenant_scoped_repository import TenantScopedRepository
from app.db.cosmos_client import get_database
from app.models.tenant import Tenant

router = APIRouter(prefix="/admin/tenants", tags=["Admin - Tenants"])

class CreateTenantRequest(BaseModel):
    tenantId: str
    tenantName: str
    plan: str
    adminUserId: str

class UpdateTenantRequest(BaseModel):
    tenantName: Optional[str] = None
    plan: Optional[str] = None

@router.post("")
@require_role("super_admin")
async def provision_tenant(request: Request, body: CreateTenantRequest):
    """MT-005: Tenant provisioning via Super Admin only"""
    db = Request.state.database if hasattr(Request.state, 'database') else await get_database()
    tenant_repo = TenantScopedRepository(db, "tenants")
    tenant_doc = body.dict()
    tenant_doc['_id'] = tenant_doc['tenantId']
    tenant_doc['status'] = 'provisioning'
    await tenant_repo.insert_one(body.tenantId, tenant_doc)
    # Create initial tenant_admin user_role, seed flags
    await request.app.state.audit_service.log_event(
        tenant_id="GLOBAL", 
        action="tenant_created", 
        actor_role="super_admin", 
        details={"tenantId": body.tenantId}
    )
    return {"tenantId": body.tenantId, "status": "provisioning"}

@router.get("")
@require_role("super_admin")
async def list_tenants(request: Request, skip: int = 0, limit: int = 50):
    db = Request.state.database if hasattr(Request.state, 'database') else await get_database()
    tenant_repo = TenantScopedRepository(db, "tenants")
    tenants = await tenant_repo.find_many("GLOBAL", {}, skip, limit)  # tenants not tenant-scoped for super_admin
    return tenants

@router.get("/{tenant_id}")
@require_role("super_admin")
async def get_tenant(tenant_id: str, tenant_service: TenantService = Depends(lambda: TenantService(...))):
    tenant = await tenant_service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return tenant

@router.patch("/{tenant_id}")
@require_role("super_admin")
async def update_tenant(tenant_id: str, request: Request, body: UpdateTenantRequest):
    """Immutable: tenantId cannot be changed"""
    db = await get_database()
    tenant_repo = TenantScopedRepository(db, "tenants")
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    
    success = await tenant_repo.update_one("GLOBAL", {"_id": tenant_id}, update_data)
    if not success:
        raise HTTPException(404, "Tenant not found")
    
    await request.app.state.redis.delete(f"tenant:{tenant_id}")
    return {"status": "updated", "fields": list(update_data.keys())}

@router.post("/{tenant_id}/suspend")
@require_role("super_admin")
async def suspend_tenant(tenant_id: str, request: Request, tenant_service: TenantService = Depends(lambda: TenantService(...))):
    """Immediate suspension - all API calls return 403 after this"""
    success = await tenant_service.transition_status(tenant_id, "suspended")
    if success:
        await request.app.state.audit_service.log_event(tenant_id=tenant_id, action="tenant_suspended", actor_role="super_admin")
    else:
        raise HTTPException(400, "Transition failed")
    return {"status": "suspended"}

@router.post("/{tenant_id}/reactivate")
@require_role("super_admin")
async def reactivate_tenant(tenant_id: str, request: Request, tenant_service: TenantService = Depends(lambda: TenantService(...))):
    success = await tenant_service.transition_status(tenant_id, "active")
    if success:
        await request.app.state.audit_service.log_event(tenant_id=tenant_id, action="tenant_reactivated", actor_role="super_admin")
    else:
        raise HTTPException(400, "Transition failed")
    return {"status": "active"}
