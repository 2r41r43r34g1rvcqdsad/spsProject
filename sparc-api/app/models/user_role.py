from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserRole(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenantId: str
    userId: str
    email: str
    role: Literal["super_admin", "tenant_admin", "analyst", "viewer"]
    status: Literal["active", "inactive"] = "active"
    assignedBy: str
    assignedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lastLoginAt: Optional[datetime] = None
    schema_version: str = Field(default="1.0", alias="_schema_version")
