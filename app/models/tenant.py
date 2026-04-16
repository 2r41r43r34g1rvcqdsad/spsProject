from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class TenantSettings(BaseModel):
    logoUrl: Optional[str] = None
    primaryColor: str = "#0052CC"
    defaultRubricId: Optional[str] = None
    notificationEmail: Optional[str] = None
    maxDealsPerCycle: int = 100
    allowExternalValidation: bool = False
    externalValidationSources: list[str] = Field(default_factory=list)


class TenantQuotas(BaseModel):
    dealsPerMonth: int = 50
    storageGb: int = 100
    llmCallsPerDay: int = 5000


class Tenant(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenantId: str = Field(..., description="Partition key; immutable after creation.")
    tenantName: str
    status: Literal["provisioning", "trial", "active", "suspended", "cancelled"] = (
        "provisioning"
    )
    plan: Literal["trial", "starter", "professional", "enterprise"] = "trial"
    trialExpiryDate: Optional[datetime] = None
    dataRetentionDays: int = 365
    settings: TenantSettings = Field(default_factory=TenantSettings)
    quotas: TenantQuotas = Field(default_factory=TenantQuotas)
    adminUserId: str
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = Field(default="1.0", alias="_schema_version")
