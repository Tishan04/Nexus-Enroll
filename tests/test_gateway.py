import pytest
from fastapi.testclient import TestClient

from services.gateway.app import SERVICE_URLS, app

class FakeResponse:
    def __init__(self, status_code=200,content=b'{"ok":true}', headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"content-type": "application/json"}

class FakeHttpClient:
    def __init__(self):
        self.calls = []

    async def get(self, url):
        self.calls.append(("GET", url, None, None))
        return FakeResponse(content=b'{"status":"ok","service":"enrollment"}')

    async def request(self, method, url, content=b"", headers=None):
        self.calls.append((method, url, content, headers))
        return FakeResponse(content=b'{"proxied":true}')

    async def aclose(self):
        pass

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        fake_http_client = FakeHttpClient()
        app.state.http_client = fake_http_client
        yield test_client, fake_http_client

def test_routes_to_enrollment_and_preserves_query(client):
    test_client, fake_http_client = client
    response = test_client.get("/enrollment/courses?department=Computer%20Science")

    assert response.status_code == 200
    assert response.json() == {"proxied": True}
    assert fake_http_client.calls[0][0] == "GET"
    assert fake_http_client.calls[0][1] == (f"{SERVICE_URLS['enrollment']}" "/courses?department=Computer%20Science")

def test_blocks_internal_endpoints(client):
    test_client, fake_http_client = client

    response = test_client.post("/enrollment/internal/override")

    assert response.status_code == 404
    assert fake_http_client.calls == []

def test_notification_is_not_public(client):
    test_client, fake_http_client = client

    response = test_client.post("/notification/events", json={"type": "test"})

    assert response.status_code == 404
    assert fake_http_client.calls == []

def test_identity_write_is_not_public(client):
    test_client, fake_http_client = client

    response = test_client.post("/identity/users", json={"user_id": "X"})

    assert response.status_code == 404
    assert fake_http_client.calls == []
