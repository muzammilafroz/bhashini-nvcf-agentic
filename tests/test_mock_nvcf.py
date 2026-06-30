import pytest
from fastapi.testclient import TestClient
import uuid

from mock_nvcf.app import app
from mock_nvcf.models import DeploymentSpec, DeploymentSpecItem

client = TestClient(app)

def test_missing_auth():
    resp = client.get("/v2/nvcf/functions")
    assert resp.status_code == 401

def test_full_lifecycle():
    headers = {"Authorization": "Bearer mock"}
    
    # 1. Create function
    spec = {"name": f"test-func-{uuid.uuid4()}"}
    resp = client.post("/v2/nvcf/functions", json=spec, headers=headers)
    assert resp.status_code == 201
    fn_id = resp.json()["function"]["id"]
    
    # 2. Create version
    v_spec = {"name": "v1", "image": "ghcr.io/test/img:123"}
    resp = client.post(f"/v2/nvcf/functions/{fn_id}/versions", json=v_spec, headers=headers)
    assert resp.status_code == 201
    vid = resp.json()["version"]["id"]
    
    # 3. Deploy
    d_spec = {
        "deploymentSpecifications": [
            {
                "gpu": "CPU",
                "minInstances": 1,
                "maxInstances": 2,
                "maxRequestConcurrency": 4
            }
        ]
    }
    resp = client.post(f"/v2/nvcf/deployments/functions/{fn_id}/versions/{vid}", json=d_spec, headers=headers)
    assert resp.status_code == 202
    assert resp.json()["deployment"]["status"] == "DEPLOYING"
    
    # 4. Advance status
    resp = client.post(
        f"/__admin/advance/deployments/{fn_id}/versions/{vid}",
        json={"status": "ACTIVE"},
        headers=headers
    )
    assert resp.status_code == 200
    
    # 5. Get deployment
    resp = client.get(f"/v2/nvcf/deployments/functions/{fn_id}/versions/{vid}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["deployment"]["status"] == "ACTIVE"
    
    # 6. Update deployment
    d_spec["deploymentSpecifications"][0]["maxInstances"] = 3
    resp = client.put(f"/v2/nvcf/deployments/functions/{fn_id}/versions/{vid}", json=d_spec, headers=headers)
    assert resp.status_code == 202
    
    # 7. Delete deployment
    resp = client.delete(f"/v2/nvcf/deployments/functions/{fn_id}/versions/{vid}", headers=headers)
    assert resp.status_code == 204
    
    # Should be gone
    resp = client.get(f"/v2/nvcf/deployments/functions/{fn_id}/versions/{vid}", headers=headers)
    assert resp.status_code == 404

def test_no_traffic_split_endpoint():
    """Verify that there's no endpoint for traffic split per the spec constraints."""
    headers = {"Authorization": "Bearer mock"}
    resp = client.put("/v2/nvcf/functions/123/versions/456/traffic", json={"trafficPercentage": 10}, headers=headers)
    assert resp.status_code == 404
