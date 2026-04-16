import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.feature_flag_service import FeatureFlagService

@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.find_one.return_value = None
    return repo

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get.return_value = None
    return redis

@pytest.mark.asyncio
async def test_flag_not_found_returns_false(mock_repo, mock_redis):
    service = FeatureFlagService(mock_repo, mock_redis)
    result = await service.is_enabled("test", "nonexistent")
    assert result is False

