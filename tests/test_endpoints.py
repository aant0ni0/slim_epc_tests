import pytest
from fastapi.testclient import TestClient

import epc.traffic as traffic_module
from epc.api import get_repo
from epc.db import EPCRepository
from main import app


@pytest.fixture
def client(tmp_path):
    repo = EPCRepository(db_path=str(tmp_path / "test.db"))
    app.dependency_overrides[get_repo] = lambda: repo
    old_tm = traffic_module.traffic_manager
    traffic_module.traffic_manager = None
    yield TestClient(app)
    if traffic_module.traffic_manager:
        traffic_module.traffic_manager.stop_all()
    traffic_module.traffic_manager = old_tm
    app.dependency_overrides.clear()


# POST /ues — attach and verify UE appears in list

def test_attach_and_list_ue(client):
    client.post("/ues", json={"ue_id": 5})
    resp = client.get("/ues")
    assert resp.status_code == 200
    assert 5 in resp.json()["ues"]


# POST /ues — duplicate attach must return 400

def test_attach_duplicate_returns_400(client):
    client.post("/ues", json={"ue_id": 1})
    resp = client.post("/ues", json={"ue_id": 1})
    assert resp.status_code == 400


# POST /ues — ue_id outside 1..100 must be rejected at schema level

def test_attach_invalid_ue_id_returns_422(client):
    resp = client.post("/ues", json={"ue_id": 0})
    assert resp.status_code == 422


# GET /ues/{ue_id} — missing UE must return 400

def test_get_ue_not_found_returns_400(client):
    resp = client.get("/ues/99")
    assert resp.status_code == 400


# POST + DELETE /ues/{ue_id}/bearers — add then remove a bearer

def test_add_and_delete_bearer(client):
    client.post("/ues", json={"ue_id": 1})
    resp = client.post("/ues/1/bearers", json={"bearer_id": 3})
    assert resp.status_code == 200
    assert resp.json()["status"] == "bearer_added"
    resp = client.delete("/ues/1/bearers/3")
    assert resp.status_code == 200
    assert resp.json()["status"] == "bearer_deleted"


# DELETE /ues/{ue_id}/bearers/9 — default bearer is protected

def test_delete_default_bearer_returns_400(client):
    client.post("/ues", json={"ue_id": 1})
    resp = client.delete("/ues/1/bearers/9")
    assert resp.status_code == 400


# POST + DELETE /ues/{ue_id}/bearers/{bearer_id}/traffic — start and stop traffic

def test_start_traffic_and_stop(client):
    client.post("/ues", json={"ue_id": 1})
    resp = client.post("/ues/1/bearers/9/traffic", json={"protocol": "tcp", "Mbps": 1.0})
    assert resp.status_code == 200
    assert resp.json()["status"] == "traffic_started"
    assert resp.json()["target_bps"] == 1_000_000
    resp = client.delete("/ues/1/bearers/9/traffic")
    assert resp.status_code == 200
    assert resp.json()["status"] == "traffic_stopped"


# POST /traffic — providing two throughput fields at once must return 422

def test_start_traffic_two_throughputs_returns_422(client):
    client.post("/ues", json={"ue_id": 1})
    resp = client.post("/ues/1/bearers/9/traffic", json={"protocol": "tcp", "Mbps": 1.0, "kbps": 500.0})
    assert resp.status_code == 422


# GET /ues/stats — must not be confused with GET /ues/{ue_id}

def test_ues_stats_route_not_confused_with_ue_id(client):
    resp = client.get("/ues/stats")
    assert resp.status_code == 200
    assert "scope" in resp.json()


# POST /reset — all UEs must be gone afterwards

def test_reset_clears_everything(client):
    client.post("/ues", json={"ue_id": 1})
    client.post("/ues", json={"ue_id": 2})
    resp = client.post("/reset")
    assert resp.status_code == 200
    assert client.get("/ues").json()["ues"] == []
