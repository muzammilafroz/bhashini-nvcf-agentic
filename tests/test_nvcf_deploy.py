import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from pipeline.nvcf_deploy import NVCFDeployer
from mock_nvcf.models import DeploymentSpec, DeploymentSpecItem

@pytest.mark.anyio
async def test_nvcf_deploy_flow():
    # We will mock the client rather than spinning up the real test server,
    # just to test the deployer logic.
    mock_client = AsyncMock()
    mock_client.get_or_create_function.return_value = "fn-123"
    mock_client.create_version.return_value = "v-456"
    mock_client.poll_deployment.return_value = True
    
    deployer = NVCFDeployer(mock_client)
    
    spec = DeploymentSpec(deploymentSpecifications=[
        DeploymentSpecItem(
            gpu="CPU",
            minInstances=1,
            maxInstances=2,
            maxRequestConcurrency=4
        )
    ])
    
    fn_id, v_id = await deployer.deploy_model("test-model", "img:latest", spec, "rebuild")
    
    assert fn_id == "fn-123"
    assert v_id == "v-456"
    
    mock_client.get_or_create_function.assert_called_once_with("test-model")
    mock_client.create_version.assert_called_once_with("fn-123", "v-latest", "img:latest")
    mock_client.deploy.assert_called_once_with("fn-123", "v-456", spec)
    mock_client.poll_deployment.assert_called_once_with("fn-123", "v-456")

@pytest.mark.anyio
async def test_nvcf_deploy_timeout():
    mock_client = AsyncMock()
    mock_client.get_or_create_function.return_value = "fn-123"
    mock_client.create_version.return_value = "v-456"
    mock_client.poll_deployment.return_value = False # Timeout!
    
    deployer = NVCFDeployer(mock_client)
    
    spec = DeploymentSpec(deploymentSpecifications=[
        DeploymentSpecItem(
            gpu="CPU",
            minInstances=1,
            maxInstances=2,
            maxRequestConcurrency=4
        )
    ])
    
    with pytest.raises(RuntimeError, match="Deployment of test-model failed"):
        await deployer.deploy_model("test-model", "img:latest", spec, "rebuild")
