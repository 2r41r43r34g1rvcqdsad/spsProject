"""
Admin Tenants Router - Super Admin Tenant Management

This router provides endpoints for super admin users to manage all tenants in the system.

Features:
    1. Create tenant (provisioning status)
    2. List all tenants
    3. Get single tenant details
    4. Update tenant (name, plan)
    5. Suspend tenant (immediate 403 for all API calls)
    6. Reactivate suspended tenant

Base Path: /admin/tenants
Auth Required: super_admin (role level 4)

Request Headers:
    - x-tenant-id: Tenant identifier (required for non-excluded paths)
    - x-user-role: User role (must be super_admin)
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.auth.rbac import require_role
from app.services.tenant_service import TenantService
from app.db.tenant_scoped_repository import TenantScopedRepository
from app.db.cosmos_client import get_database
from app.models.tenant import Tenant

# Create router with prefix and tag for API documentation
router = APIRouter(prefix="/admin/tenants", tags=["Admin - Tenants"])


class CreateTenantRequest(BaseModel):
    """
    Request body for creating a new tenant.
    
    Fields:
        tenantId: Unique identifier for the tenant
        tenantName: Display name for the tenant
        plan: Subscription plan (e.g., "free", "pro", "enterprise")
        adminUserId: User ID of the tenant admin
    """
    tenantId: str
    tenantName: str
    plan: str
    adminUserId: str


class UpdateTenantRequest(BaseModel):
    """
    Request body for updating tenant details.
    
    Fields:
        tenantName: New display name (optional)
        plan: New subscription plan (optional)
    
    Note: tenantId cannot be changed (immutable)
    """
    tenantName: Optional[str] = None
    plan: Optional[str] = None


@router.post("")
@require_role("super_admin")
async def provision_tenant(request: Request, body: CreateTenantRequest):
    """
    Create a new tenant with provisioning status.
    
    Flow:
        1. Validate super_admin role
        2. Create tenant document with status="provisioning"
        3. Insert into tenants collection
        4. Log audit event for tenant creation
    
    Request Body:
        CreateTenantRequest with: tenantId, tenantName, plan, adminUserId
    
    Returns:
        {"tenantId": "...", "status": "provisioning"}
    
    Auth: x-user-role must be "super_admin"
    """
    # Get database connection
    db = request.state.database if hasattr(request.state, 'database') else await get_database()
    tenant_repo = TenantScopedRepository(db, "tenants")
    
    # Create tenant document from request body
    tenant_doc = body.dict()
    tenant_doc['_id'] = tenant_doc['tenantId']  # Use tenantId as _id
    tenant_doc['status'] = 'provisioning'  # Start in provisioning status
    
    # Insert tenant into database
    await tenant_repo.insert_one(body.tenantId, tenant_doc)
    
    # Log audit event
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
    """
    List all tenants in the system.
    
    Flow:
        1. Validate super_admin role
        2. Query tenants collection (not tenant-scoped)
        3. Return list of tenants
    
    Query Parameters:
        skip: Number of records to skip (pagination)
        limit: Maximum records to return (default 50)
    
    Returns:
        List of tenant documents
    
    Auth: x-user-role must be "super_admin"
    """
    db = request.state.database if hasattr(request.state, 'database') else await get_database()
    tenant_repo = TenantScopedRepository(db, "tenants")
    
    # Use "GLOBAL" scope - not tenant-scoped for super_admin
    tenants = await tenant_repo.find_many("GLOBAL", {}, skip, limit)
    return tenants


@router.get("/{tenant_id}")
@require_role("super_admin")
async def get_tenant(tenant_id: str, tenant_service: TenantService = Depends(lambda: TenantService(...))):
    """
    Get details of a specific tenant.
    
    Flow:
        1. Validate super_admin role
        2. Get tenant using TenantService
        3. Return tenant document or 404
    
    Path Parameters:
        tenant_id: The tenant to retrieve
    
    Returns:
        Tenant document
    
    Raises:
        HTTPException 404: Tenant not found
    
    Auth: x-user-role must be "super_admin"
    """
    tenant = await tenant_service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return tenant


@router.patch("/{tenant_id}")
@require_role("super_admin")
async def update_tenant(tenant_id: str, request: Request, body: UpdateTenantRequest):
    """
    Update tenant details (name or plan).
    
    Flow:
        1. Validate super_admin role
        2. Build update dict from non-null fields
        3. Update in database
        4. Invalidate Redis cache
        5. Return updated fields
    
    Path Parameters:
        tenant_id: The tenant to update
    
    Request Body:
        UpdateTenantRequest with: tenantName (optional), plan (optional)
    
    Returns:
        {"status": "updated", "fields": ["tenantName", "plan"]}
    
    Note: tenantId is immutable and cannot be changed
    
    Auth: x-user-role must be "super_admin"
    """
    db = await get_database()
    tenant_repo = TenantScopedRepository(db, "tenants")
    
    # Build update dict from non-null fields only
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    
    # Update tenant in GLOBAL scope (not tenant-scoped)
    success = await tenant_repo.update_one("GLOBAL", {"_id": tenant_id}, update_data)
    if not success:
        raise HTTPException(404, "Tenant not found")
    
    # Invalidate Redis cache so next request gets fresh data
    await request.app.state.redis.delete(f"tenant:{tenant_id}")
    
    return {"status": "updated", "fields": list(update_data.keys())}


@router.post("/{tenant_id}/suspend")
@require_role("super_admin")
async def suspend_tenant(tenant_id: str, request: Request, tenant_service: TenantService = Depends(lambda: TenantService(...))):
    """
    Immediately suspend a tenant.
    
    Flow:
        1. Validate super_admin role
        2. Transition tenant status to "suspended"
        3. Log audit event
        4. Returns 403 for all API calls
    
    Path Parameters:
        tenant_id: The tenant to suspend
    
    Returns:
        {"status": "suspended"}
    
    Effect:
        - Tenant status set to "suspended"
        - All tenant API calls return 403
        - Can be reactivated with /reactivate
    
    Auth: x-user-role must be "super_admin"
    """
    success = await tenant_service.transition_status(tenant_id, "suspended")
    if success:
        # Log audit event
        await request.app.state.audit_service.log_event(
            tenant_id=tenant_id, 
            action="tenant_suspended", 
            actor_role="super_admin"
        )
    else:
        raise HTTPException(400, "Transition failed")
    return {"status": "suspended"}


@router.post("/{tenant_id}/reactivate")
@require_role("super_admin")
async def reactivate_tenant(tenant_id: str, request: Request, tenant_service: TenantService = Depends(lambda: TenantService(...))):
    """
    Reactivate a suspended tenant.
    
    Flow:
        1. Validate super_admin role
        2. Transition tenant status to "active"
        3. Log audit event
    
    Path Parameters:
        tenant_id: The tenant to reactivate
    
    Returns:
        {"status": "active"}
    
    Note: Can only reactivate from "suspended" status
    
    Auth: x-user-role must be "super_admin"
    """
    success = await tenant_service.transition_status(tenant_id, "active")
    if success:
        # Log audit event
        await request.app.state.audit_service.log_event(
            tenant_id=tenant_id, 
            action="tenant_reactivated", 
            actor_role="super_admin"
        )
    else:
        raise HTTPException(400, "Transition failed")
    return {"status": "active"}