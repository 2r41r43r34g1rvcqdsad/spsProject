# TS-MT-002, TS-MT-007: Suspended tenants blocked
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_suspended_tenant_returns_403():
    response = client.get("/tenant/users", headers={"x-tenant-id": "suspended_tenant", "x-user-role": "super_admin"})
    assert response.status_code == 403
    assert "suspended" in response.json()["detail"]

