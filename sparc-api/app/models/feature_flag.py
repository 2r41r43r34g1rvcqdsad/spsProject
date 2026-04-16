from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FeatureFlag(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenantId: str
    flagKey: str
    enabled: bool = False
    description: Optional[str] = None
    lastModifiedBy: str
    lastModifiedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = Field(default="1.0", alias="_schema_version")
