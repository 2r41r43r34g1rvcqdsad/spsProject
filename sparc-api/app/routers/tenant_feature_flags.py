from fastapi import APIRouter, Request
from app.auth.rbac import require_role
from app.services.feature_flag_service import FeatureFlagService

router = APIRouter(prefix="/tenant/feature-flags", tags=["Tenant - Feature Flags"])

@router.get("")
@require_role("tenant_admin")
async def list_tenant_feature_flags(request: Request):
    tenant_id = request.state.tenant_id
    # tenant-specific flags
    pass

@router.get("/{flag_key}")
@require_role("tenant_admin")
async def get_feature_flag(flag_key: str, request: Request):
    tenant_id = request.state.tenant_id
    # is_enabled
    pass

