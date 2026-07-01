import asyncio
import os
import time

import httpx

from mock_nvcf.models import (
    DeploymentSpec,
    FunctionSpec,
    NvcfDeploymentResponse,
    NvcfFunctionListResponse,
    NvcfFunctionResponse,
    NvcfVersionResponse,
    VersionSpec,
)


class NVCFDeployClient:
    """
    Client for the NVCF Deploy API.
    By default, talks to the real NVIDIA API, but `mock=True` switches to local FastAPI mock.
    The ONLY difference is BASE_URL and the auth header.
    """

    def __init__(self, mock: bool = True, auth_token: str | None = None, mock_port: int = 8000):
        self.mock = mock
        if self.mock:
            self.base_url = f"http://localhost:{mock_port}"
            self.auth_token = "mock-token"
        else:
            self.base_url = "https://api.ngc.nvidia.com"
            self.auth_token = auth_token or os.environ.get("NVCF_API_KEY")
            if not self.auth_token:
                raise ValueError("NVCF_API_KEY is required for real NVCF client")

        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # Single reusable client — must call close() when done
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the underlying HTTP client. Call this when the deployer is done."""
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url}{path}"
        resp = await self._client.request(method, url, headers=self.headers, **kwargs)
        resp.raise_for_status()
        return resp

    async def get_or_create_function(self, name: str) -> str:
        """Returns the functionId."""
        try:
            resp = await self._request("GET", "/v2/nvcf/functions?visibility=private")
            data = NvcfFunctionListResponse.model_validate(resp.json())
            for fn in data.functions:
                if fn.name == name:
                    return fn.id
        except httpx.HTTPError:
            pass

        spec = FunctionSpec(name=name)
        resp = await self._request("POST", "/v2/nvcf/functions", json=spec.model_dump())
        data = NvcfFunctionResponse.model_validate(resp.json())
        return data.function.id

    async def create_version(self, function_id: str, name: str, image: str) -> str:
        """Returns the versionId."""
        spec = VersionSpec(name=name, image=image)
        resp = await self._request(
            "POST",
            f"/v2/nvcf/functions/{function_id}/versions",
            json=spec.model_dump(),
        )
        data = NvcfVersionResponse.model_validate(resp.json())
        return data.version.id

    async def deploy(self, function_id: str, version_id: str, spec: DeploymentSpec) -> None:
        """Starts deployment. Doesn't wait for ACTIVE."""
        await self._request(
            "POST",
            f"/v2/nvcf/deployments/functions/{function_id}/versions/{version_id}",
            json=spec.model_dump(),
        )

    async def update_deployment(self, function_id: str, version_id: str, spec: DeploymentSpec) -> None:
        """Updates deployment specs."""
        await self._request(
            "PUT",
            f"/v2/nvcf/deployments/functions/{function_id}/versions/{version_id}",
            json=spec.model_dump(),
        )

    async def poll_deployment(self, function_id: str, version_id: str, timeout_sec: int = 600) -> bool:
        """Polls until ACTIVE. Returns True if ACTIVE, False if ERROR or timeout."""
        start = time.time()
        while (time.time() - start) < timeout_sec:
            try:
                resp = await self._request(
                    "GET",
                    f"/v2/nvcf/deployments/functions/{function_id}/versions/{version_id}",
                )
                data = NvcfDeploymentResponse.model_validate(resp.json())
                status = data.deployment.status

                if status == "ACTIVE":
                    return True
                elif status == "ERROR":
                    return False

            except httpx.HTTPError:
                pass

            await asyncio.sleep(2)

        return False

    async def undeploy(self, function_id: str, version_id: str) -> None:
        await self._request(
            "DELETE",
            f"/v2/nvcf/deployments/functions/{function_id}/versions/{version_id}",
        )
