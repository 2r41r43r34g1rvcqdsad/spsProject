from fastapi import APIRouter, Request, Depends
from app.auth.rbac import require_role
from app.services.feature_flag_service import FeatureFlagService

router = APIRouter(prefix="/admin/feature-flags", tags=["Admin - Feature Flags"])

@router.get("")
@require_role("super_admin")
async def list_feature_flags():
    # List GLOBAL flags
    pass

@router.post("")
@require_role("super_admin")
async def create_feature_flag(flag_key: str, enabled: bool, description: str):
    pass

@router.patch("/{flag_key}")
@require_role("super_admin")
async def update_feature_flag(flag_key: str, enabled: bool):
    pass

@router.delete("/{flag_key}")
@require_role("super_admin")
async def delete_feature_flag(flag_key: str):
    pass

