from fastapi.testclient import TestClient

from ltts.server import app


def test_mcp_http_endpoints():
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        health = client.get("/health").json()
        assert health.get("mcp_http") == "/mcp"

        r = client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        assert r.status_code == 200
        assert "capabilities" in r.text
