import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.parametrize("role, expected_code", [
    ("viewer", 403),
    ("tenant_admin", 403),
    ("super_admin", 200),
])
async def test_admin_endpoint_rbac(role, expected_code):
    response = client.get("/admin/tenants", headers={"x-user-role": role})
    assert response.status_code == expected_code

