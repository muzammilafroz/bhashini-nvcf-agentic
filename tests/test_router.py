import pytest
from fastapi.testclient import TestClient

from router.gateway import app

client = TestClient(app)

def test_set_weight():
    resp = client.post("/__control/weight", json={"pct": 50})
    assert resp.status_code == 200
    
    resp = client.get("/__control/state")
    assert resp.json()["weight"] == 50

def test_invalid_weight():
    resp = client.post("/__control/weight", json={"pct": 150})
    assert resp.status_code == 400

# Testing actual proxying requires spinning up mock upstream servers, 
# which is slightly complex for a simple unit test, but we can verify the state changes.
