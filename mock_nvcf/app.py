import asyncio
import datetime
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from .models import (
    DeploymentSpec,
    DeploymentStatus,
    FunctionSpec,
    FunctionStatus,
    NvcfDeployment,
    NvcfDeploymentResponse,
    NvcfFunction,
    NvcfFunctionListResponse,
    NvcfFunctionResponse,
    NvcfVersion,
    NvcfVersionResponse,
    VersionSpec,
)

app = FastAPI(title="Mock NVCF Control Plane")

# In-memory stores
_functions: dict[str, NvcfFunction] = {}
_versions: dict[str, NvcfVersion] = {}
_deployments: dict[str, dict[str, NvcfDeployment]] = {} # functionId -> versionId -> deployment

# Configuration
DEPLOYMENT_DELAY_SECONDS = 5.0

def _require_auth(request: Request):
    if not request.headers.get("Authorization"):
        raise HTTPException(status_code=401, detail="Unauthorized")

def _now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()

@app.post("/v2/nvcf/functions", response_model=NvcfFunctionResponse, status_code=201)
async def create_function(spec: FunctionSpec, request: Request):
    _require_auth(request)
    
    # Simple check for existing name
    for fn in _functions.values():
        if fn.name == spec.name:
            return NvcfFunctionResponse(function=fn)
            
    fn_id = str(uuid.uuid4())
    fn = NvcfFunction(
        id=fn_id,
        name=spec.name,
        inferenceUrl=spec.inferenceUrl,
        inferencePort=spec.inferencePort,
        containerImage=spec.containerImage,
        apiBodyFormat=spec.apiBodyFormat,
        status=FunctionStatus.ACTIVE,
        createdAt=_now()
    )
    _functions[fn_id] = fn
    _deployments[fn_id] = {}
    return NvcfFunctionResponse(function=fn)

@app.get("/v2/nvcf/functions", response_model=NvcfFunctionListResponse)
async def list_functions(request: Request, visibility: Optional[str] = None):
    _require_auth(request)
    # Simple list
    return NvcfFunctionListResponse(functions=list(_functions.values()))

@app.post("/v2/nvcf/functions/{functionId}/versions", response_model=NvcfVersionResponse, status_code=201)
async def create_version(functionId: str, spec: VersionSpec, request: Request):
    _require_auth(request)
    if functionId not in _functions:
        raise HTTPException(status_code=404, detail="Function not found")
        
    version_id = str(uuid.uuid4())
    version = NvcfVersion(
        id=version_id,
        functionId=functionId,
        name=spec.name,
        image=spec.image,
        status=FunctionStatus.ACTIVE,
        createdAt=_now()
    )
    _versions[version_id] = version
    return NvcfVersionResponse(version=version)

async def _transition_deployment_status(function_id: str, version_id: str):
    await asyncio.sleep(DEPLOYMENT_DELAY_SECONDS)
    if function_id in _deployments and version_id in _deployments[function_id]:
        dep = _deployments[function_id][version_id]
        if dep.status == DeploymentStatus.DEPLOYING:
            dep.status = DeploymentStatus.ACTIVE

@app.post("/v2/nvcf/deployments/functions/{functionId}/versions/{versionId}", response_model=NvcfDeploymentResponse, status_code=202)
async def deploy_version(functionId: str, versionId: str, spec: DeploymentSpec, request: Request):
    _require_auth(request)
    if functionId not in _functions:
        raise HTTPException(status_code=404, detail="Function not found")
    if versionId not in _versions:
        raise HTTPException(status_code=404, detail="Version not found")
        
    dep = NvcfDeployment(
        functionId=functionId,
        functionVersionId=versionId,
        status=DeploymentStatus.DEPLOYING,
        deploymentSpecifications=spec.deploymentSpecifications
    )
    _deployments[functionId][versionId] = dep
    
    # Start background task to transition state
    asyncio.create_task(_transition_deployment_status(functionId, versionId))
    
    return NvcfDeploymentResponse(deployment=dep)

@app.get("/v2/nvcf/deployments/functions/{functionId}/versions/{versionId}", response_model=NvcfDeploymentResponse)
async def get_deployment(functionId: str, versionId: str, request: Request):
    _require_auth(request)
    if functionId not in _deployments or versionId not in _deployments[functionId]:
        raise HTTPException(status_code=404, detail="Deployment not found")
        
    return NvcfDeploymentResponse(deployment=_deployments[functionId][versionId])

@app.put("/v2/nvcf/deployments/functions/{functionId}/versions/{versionId}", response_model=NvcfDeploymentResponse, status_code=202)
async def update_deployment(functionId: str, versionId: str, spec: DeploymentSpec, request: Request):
    _require_auth(request)
    if functionId not in _deployments or versionId not in _deployments[functionId]:
        raise HTTPException(status_code=404, detail="Deployment not found")
        
    dep = _deployments[functionId][versionId]
    dep.deploymentSpecifications = spec.deploymentSpecifications
    return NvcfDeploymentResponse(deployment=dep)

@app.delete("/v2/nvcf/deployments/functions/{functionId}/versions/{versionId}", status_code=204)
async def delete_deployment(functionId: str, versionId: str, request: Request):
    _require_auth(request)
    if functionId in _deployments and versionId in _deployments[functionId]:
        del _deployments[functionId][versionId]
    return None

# --- Testing hooks ---

class AdminAdvanceRequest(BaseModel):
    status: DeploymentStatus

@app.post("/__admin/advance/deployments/{functionId}/versions/{versionId}")
async def admin_advance_deployment(functionId: str, versionId: str, req: AdminAdvanceRequest):
    """Test hook to instantly force a deployment status without waiting."""
    if functionId in _deployments and versionId in _deployments[functionId]:
        _deployments[functionId][versionId].status = req.status
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Deployment not found")
