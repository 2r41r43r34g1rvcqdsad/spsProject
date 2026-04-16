from fastapi import APIRouter, Request, Depends
from app.auth.rbac import require_role
from app.services.user_role_service import UserRoleService  # To be implemented

router = APIRouter(prefix="/tenant/users", tags=["Tenant - Users"])

@router.get("")
@require_role("tenant_admin")
async def list_users(request: Request):
    tenant_id = request.state.tenant_id
    # Query user_roles where tenantId = tenant_id
    return []

@router.post("")
@require_role("tenant_admin")
async def invite_user(request: Request):
    # Create user_roles doc, send Entra ID invite
    pass

@router.patch("/{user_id}")
@require_role("tenant_admin")
async def update_user_role(user_id: str, request: Request):
    # Invalidate Redis: user_role:{userId}:{tenantId}
    pass

@router.delete("/{user_id}")
@require_role("tenant_admin")
async def remove_user(user_id: str, request: Request):
    pass

