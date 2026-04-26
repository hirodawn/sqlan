import time
import pytest
from fastapi.testclient import TestClient
from web.app import create_app

CONFIG = {
    "source": {"java_root": "tests/fixtures", "sql_root": "tests/fixtures"},
    "database": {"url": "sqlite:///:memory:"},
    "analysis": {"timeout_seconds": 30, "cardinality_sample": 1000},
}

@pytest.fixture
def client():
    return TestClient(create_app(CONFIG))

def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_analyze_returns_job_id(client):
    resp = client.post("/api/analyze", json={"config": CONFIG})
    assert resp.status_code == 200
    assert "job_id" in resp.json()

def test_status_returns_valid_state(client):
    job_id = client.post("/api/analyze", json={"config": CONFIG}).json()["job_id"]
    resp = client.get(f"/api/status/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["state"] in ("running", "completed", "error")

def test_graph_returns_nodes_and_edges(client):
    job_id = client.post("/api/analyze", json={"config": CONFIG}).json()["job_id"]
    for _ in range(20):
        if client.get(f"/api/status/{job_id}").json()["state"] == "completed":
            break
        time.sleep(0.3)
    resp = client.get(f"/api/graph/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data

def test_status_404_for_unknown_job(client):
    assert client.get("/api/status/no-such-job").status_code == 404
