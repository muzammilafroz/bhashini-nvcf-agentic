from abc import ABC, abstractmethod
from typing import Any


class CloudProvider(ABC):
    """
    Abstract Base Class for all cloud deployment providers.
    Allows seamlessly swapping between GCP, AWS, Azure, NVCF, etc.

    Every provider must implement the full deployment lifecycle:
    deploy → poll status → get health metrics → promote/rollback → cleanup.
    The orchestrator calls ONLY these methods — no provider-specific branching.
    """

    @abstractmethod
    async def deploy_model(self, model_id: str, image_uri: str, config: dict[str, Any]) -> tuple[str, str]:
        """
        Deploys a model image to the cloud provider.
        Returns (function_id, version_id) representing the new deployment.
        """
        ...

    @abstractmethod
    async def get_deployment_status(self, fn_id: str, version_id: str) -> str:
        """
        Checks the status of the deployment.
        Must return one of: 'DEPLOYING', 'ACTIVE', 'FAILED'
        """
        ...

    @abstractmethod
    async def get_health_metrics(self, fn_id: str, version_id: str) -> dict[str, float]:
        """
        Returns current health metrics for the canary deployment.
        Must return a dict with at least:
            {"p95_latency_ms": float, "error_rate_pct": float}
        """
        ...

    @abstractmethod
    async def route_traffic(self, fn_id: str, version_id: str, weight: int) -> None:
        """
        Updates the gateway/router to route `weight` % of traffic to this deployment.
        """
        ...

    @abstractmethod
    async def promote(self, fn_id: str, version_id: str, model_name: str, image_tag: str) -> None:
        """
        Promotes the canary to 100% traffic and logs the event.
        """
        ...

    @abstractmethod
    async def rollback(self, fn_id: str, version_id: str, model_name: str, image_tag: str, reason: str) -> None:
        """
        Rolls back the canary to 0% traffic and logs the event.
        """
        ...

    @abstractmethod
    async def delete_deployment(self, fn_id: str, version_id: str) -> None:
        """
        Tears down the deployment resources.
        """
        ...

    async def close(self) -> None:
        """Optional cleanup hook for providers that hold resources (HTTP clients, etc.)."""
        pass
