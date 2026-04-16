import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.tenant_service import TenantService, VALID_TRANSITIONS
from app.db.tenant_scoped_repository import TenantScopedRepository

@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=TenantScopedRepository)
    repo._collection.find_one.return_value = None
    return repo

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get.return_value = None
    return redis

@pytest.mark.asyncio
async def test_valid_transition_active_to_suspended(mock_repo, mock_redis):
    service = TenantService(mock_repo, mock_redis)
    mock_repo._collection.find_one.return_value = {"_id": "test", "status": "active"}
    success = await service.transition_status("test", "suspended")
    assert success is True

@pytest.mark.asyncio
async def test_invalid_transition(mock_repo, mock_redis):
    service = TenantService(mock_repo, mock_redis)
    mock_repo._collection.find_one.return_value = {"status": "cancelled"}
    with pytest.raises(ValueError):
        await service.transition_status("test", "active")

