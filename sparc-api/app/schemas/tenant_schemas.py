from pydantic import BaseModel
from typing import Optional
from app.models.tenant import Tenant

class CreateTenantRequest(BaseModel):
    tenantId: str
    tenantName: str
    plan: str = "trial"
    adminUserId: str

class UpdateTenantRequest(BaseModel):
    tenantName: Optional[str] = None
    plan: Optional[str] = None
    # etc.

class TenantResponse(Tenant):
    pass

