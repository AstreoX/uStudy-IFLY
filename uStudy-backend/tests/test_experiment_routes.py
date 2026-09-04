"""Application-level route surface tests for the experiment build."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


def test_disabled_feature_routers_are_not_mounted():
    paths = {route.path for route in app.routes}
    assert "/api/auth/login" in paths
    assert "/api/spaces/default" in paths
    assert not any(path.startswith("/api/quick-chat") for path in paths)
    assert "/api/auth/activate" not in paths
    assert not any(path.startswith("/api/payment") for path in paths)
    assert not any(path.startswith("/api/wallet") for path in paths)
    assert not any(path.startswith("/api/invites") for path in paths)
    assert "/static/payment" not in paths


@pytest.mark.asyncio
async def test_space_creation_is_feature_disabled_before_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/spaces",
            json={"name": "Forbidden", "color": "#3B82F6"},
        )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "FEATURE_DISABLED"


@pytest.mark.asyncio
async def test_admin_payment_endpoint_is_removed():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/admin/orders/00000000-0000-0000-0000-000000000001/confirm"
        )
    assert response.status_code == 404
