"""
NVCF Provider — wraps the NVCF deploy client and the canary router
into a single CloudProvider implementation.

Works identically against both the mock NVCF server and the real
api.ngc.nvidia.com — the only difference is the base URL and auth token
configured in NVCFDeployClient.
"""

import logging
from typing import Any

import httpx

from mock_nvcf.deploy_client import NVCFDeployClient
from pipeline.providers.base import CloudProvider
from pipeline.schemas.nvcf_models import DeploymentSpec, DeploymentSpecItem
from router.db import log_event

logger = logging.getLogger(__name__)


class NVCFProvider(CloudProvider):
    """
    CloudProvider implementation for NVCF (mock or real).
    Delegates deploy operations to NVCFDeployClient and traffic control
    to the external canary router.
    """

    def __init__(self, mock: bool = True, router_url: str = "http://localhost:8001"):
        self.client = NVCFDeployClient(mock=mock)
        self.router_url = router_url
        self._http = httpx.AsyncClient(timeout=10.0)

    async def deploy_model(self, model_id: str, image_uri: str, config: dict[str, Any]) -> tuple[str, str]:
        logger.info(f"[NVCF] Starting deploy for {model_id}")

        # 1. Get or create function
        fn_id = await self.client.get_or_create_function(model_id)
        logger.info(f"[NVCF] Function ID: {fn_id}")

        # 2. Create version
        version_name = "v-" + image_uri.split(":")[-1] if ":" in image_uri else "v-latest"
        v_id = await self.client.create_version(fn_id, version_name, image_uri)
        logger.info(f"[NVCF] Version ID: {v_id}")

        # 3. Use the planner's deployment spec when provided; fall back to the
        # legacy dict-shaped config so older callers keep working.
        if hasattr(config, "deploymentSpecifications"):
            spec = config
        else:
            config_data = config.model_dump() if hasattr(config, "model_dump") else config
            spec_item = DeploymentSpecItem(
                gpu=config_data.get("gpu", {}).get("type", "CPU"),
                minInstances=config_data.get("scaling", {}).get("min_instances", 1),
                maxInstances=config_data.get("scaling", {}).get("max_instances", 2),
                maxRequestConcurrency=config_data.get("scaling", {}).get("concurrency", 4),
            )
            spec = DeploymentSpec(deploymentSpecifications=[spec_item])

        # 4. Deploy
        await self.client.deploy(fn_id, v_id, spec)

        # 5. Wait for ACTIVE
        logger.info("[NVCF] Waiting for deployment to become ACTIVE...")
        success = await self.client.poll_deployment(fn_id, v_id)

        if not success:
            logger.error("[NVCF] Deployment failed or timed out!")
            raise RuntimeError(f"Deployment of {model_id} failed.")

        logger.info(f"[NVCF] Deployment {fn_id}/{v_id} is ACTIVE.")
        return fn_id, v_id

    async def get_deployment_status(self, fn_id: str, version_id: str) -> str:
        success = await self.client.poll_deployment(fn_id, version_id, timeout_sec=5)
        return "ACTIVE" if success else "DEPLOYING"

    async def get_health_metrics(self, fn_id: str, version_id: str) -> dict[str, float]:
        """Fetch metrics from the canary router's control endpoint."""
        resp = await self._http.get(f"{self.router_url}/__control/state")
        state = resp.json()
        return {
            "p95_latency_ms": state.get("p95_latency_ms", 0.0),
            "error_rate_pct": state.get("error_rate_pct", 0.0),
        }

    async def route_traffic(self, fn_id: str, version_id: str, weight: int) -> None:
        logger.info(f"[NVCF] Setting canary weight to {weight}%")
        await self._http.post(f"{self.router_url}/__control/weight", json={"pct": weight})

    async def promote(self, fn_id: str, version_id: str, model_name: str, image_tag: str) -> None:
        logger.info(f"[NVCF] PROMOTING {model_name} to 100% traffic")
        await self.route_traffic(fn_id, version_id, 100)
        log_event(
            model_name=model_name,
            git_sha="unknown",
            image_tag=image_tag,
            fn_id=fn_id,
            version_id=version_id,
            stage="promoted",
            traffic_pct=100,
        )

    async def rollback(self, fn_id: str, version_id: str, model_name: str, image_tag: str, reason: str) -> None:
        logger.warning(f"[NVCF] ROLLING BACK {model_name} to 0% traffic! Reason: {reason}")
        await self.route_traffic(fn_id, version_id, 0)
        log_event(
            model_name=model_name,
            git_sha="unknown",
            image_tag=image_tag,
            fn_id=fn_id,
            version_id=version_id,
            stage="rolled_back",
            traffic_pct=0,
            rollback_reason=reason,
        )

    async def delete_deployment(self, fn_id: str, version_id: str) -> None:
        await self.client.undeploy(fn_id, version_id)

    async def close(self) -> None:
        await self._http.aclose()
        await self.client.close()
