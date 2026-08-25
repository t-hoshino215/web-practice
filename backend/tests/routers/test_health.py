"""HTTP contract tests for public health routes."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.parametrize(
    ("path", "expected"),
    [("/api/", {"message": "Hello, Web Server!"}), ("/api/health", {"status": "ok"})],
)
def test_public_health_routes(client: TestClient, path: str, expected: dict[str, str]) -> None:
    """Public liveness routes should return their stable JSON contracts."""
    response = client.get(path)

    assert (response.status_code, response.json()) == (200, expected)


@pytest.mark.integration
def test_database_health_executes_query(client: TestClient) -> None:
    """A reachable database should produce the connected health response."""
    response = client.get("/api/db-health")

    assert (response.status_code, response.json()) == (200, {"status": "ok", "database": "connected"})
