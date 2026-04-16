import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

async def test_missing_tenant_header_returns_400():
    \"\"\"TS-MT-003: All unauthenticated requests rejected at middleware\"\"\"
    response = await client.get("/admin/tenants", headers={})
    assert response.status_code == 400

# Note: full tests require mocks for services/DB

