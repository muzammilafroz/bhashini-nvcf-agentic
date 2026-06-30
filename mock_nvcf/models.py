from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

class FunctionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"

class DeploymentStatus(str, Enum):
    DEPLOYING = "DEPLOYING"
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"
    UNDEPLOYING = "UNDEPLOYING"
    INACTIVE = "INACTIVE"

class FunctionSpec(BaseModel):
    name: str = Field(..., description="Function name")

class NvcfFunction(BaseModel):
    id: str
    name: str
    status: FunctionStatus
    createdAt: str

class NvcfFunctionResponse(BaseModel):
    function: NvcfFunction

class NvcfFunctionListResponse(BaseModel):
    functions: list[NvcfFunction]

class VersionSpec(BaseModel):
    name: str
    image: str

class NvcfVersion(BaseModel):
    id: str
    functionId: str
    name: str
    image: str
    status: FunctionStatus
    createdAt: str

class NvcfVersionResponse(BaseModel):
    version: NvcfVersion

class DeploymentSpecItem(BaseModel):
    gpu: str
    instanceType: str | None = None
    backend: str | None = None
    minInstances: int
    maxInstances: int
    maxRequestConcurrency: int
    attributes: dict[str, Any] | None = None
    configuration: dict[str, Any] | None = None

class DeploymentSpec(BaseModel):
    deploymentSpecifications: list[DeploymentSpecItem]

class NvcfDeployment(BaseModel):
    functionId: str
    functionVersionId: str
    status: DeploymentStatus
    deploymentSpecifications: list[DeploymentSpecItem]

class NvcfDeploymentResponse(BaseModel):
    deployment: NvcfDeployment
