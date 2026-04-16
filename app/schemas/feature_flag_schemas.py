from pydantic import BaseModel
from app.models.feature_flag import FeatureFlag

class FeatureFlagRequest(BaseModel):
    enabled: bool
    description: Optional[str] = None

class FeatureFlagResponse(FeatureFlag):
    pass

