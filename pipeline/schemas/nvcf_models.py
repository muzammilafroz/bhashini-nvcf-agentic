"""
Shared Pydantic models for the NVCF API contract.

These models define the request/response shapes for the NVIDIA Cloud Functions API.
Both the mock server (mock_nvcf/app.py) and the deploy client (mock_nvcf/deploy_client.py)
import from here, so production pipeline code never depends on the mock package.

Field names and structure match the real NVCF REST API documented at:
  https://docs.nvidia.com/cloud-functions/user-guide/latest/cloud-function/function-management.html
  https://docs.nvidia.com/cloud-functions/user-guide/latest/cloud-function/function-deployment.html
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---

class FunctionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"


class DeploymentStatus(str, Enum):
    DEPLOYING = "DEPLOYING"
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"
    UNDEPLOYING = "UNDEPLOYING"
    INACTIVE = "INACTIVE"


# --- Function layer ---

class FunctionSpec(BaseModel):
    """Request body for POST /v2/nvcf/functions."""
    name: str = Field(..., description="Function name (unique per org)")
    # Real NVCF also supports these fields; we make them optional for mock flexibility
    inferenceUrl: str = Field(default="/v2/nvcf/pexec/functions", description="Custom inference URL path")
    inferencePort: int = Field(default=8000, description="Container inference port")
    containerImage: str | None = Field(default=None, description="nvcr.io container image URI")
    apiBodyFormat: str = Field(default="CUSTOM", description="API body format: PREDICT_V2 or CUSTOM")
    description: str | None = None
    tags: list[str] | None = None


class NvcfFunction(BaseModel):
    """Function object in responses."""
    id: str
    name: str
    status: FunctionStatus
    inferenceUrl: str = "/v2/nvcf/pexec/functions"
    inferencePort: int = 8000
    containerImage: str | None = None
    apiBodyFormat: str = "CUSTOM"
    createdAt: str


class NvcfFunctionResponse(BaseModel):
    function: NvcfFunction


class NvcfFunctionListResponse(BaseModel):
    functions: list[NvcfFunction]


# --- Version layer ---

class VersionSpec(BaseModel):
    """Request body for POST /v2/nvcf/functions/{id}/versions."""
    name: str
    image: str  # containerImage for this version


class NvcfVersion(BaseModel):
    """Version object in responses."""
    id: str
    functionId: str
    name: str
    image: str
    status: FunctionStatus
    createdAt: str


class NvcfVersionResponse(BaseModel):
    version: NvcfVersion


# --- Deployment layer ---

class DeploymentSpecItem(BaseModel):
    """A single deployment specification within a deployment request."""
    gpu: str = Field(..., description="GPU type string, e.g. 'L40' or 'CPU'")
    instanceType: str | None = Field(default=None, description="Instance type, e.g. 'dgxa100.80g.1.norm'")
    backend: str | None = Field(default=None, description="Inference backend, e.g. 'triton'")
    minInstances: int = Field(..., ge=0, description="Minimum number of instances (0 = scale-to-zero)")
    maxInstances: int = Field(..., ge=1, description="Maximum number of instances")
    maxRequestConcurrency: int = Field(..., ge=1, description="Max concurrent requests per instance")
    regions: list[str] | None = Field(default=None, description="Deployment regions, e.g. ['us-east-1']")
    attributes: dict[str, Any] | None = None
    configuration: dict[str, Any] | None = None


class DeploymentSpec(BaseModel):
    """Request body for POST/PUT /v2/nvcf/deployments/functions/{fid}/versions/{vid}."""
    deploymentSpecifications: list[DeploymentSpecItem]


class NvcfDeployment(BaseModel):
    """Deployment object in responses."""
    functionId: str
    functionVersionId: str
    status: DeploymentStatus
    deploymentSpecifications: list[DeploymentSpecItem]


class NvcfDeploymentResponse(BaseModel):
    deployment: NvcfDeployment
