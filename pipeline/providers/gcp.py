import asyncio
import json
import os
import shutil
import subprocess
from typing import Any
from urllib.parse import urlparse

import httpx

from .base import CloudProvider


class GCPProvider(CloudProvider):
    """
    Deploys models to Google Cloud Run and programs Kong as the edge router.

    Required for real canary routing:
      - KONG_ADMIN_URL, preferably reachable through SSH/VPN, e.g. http://127.0.0.1:8001
      - KONG_STABLE_TARGET_URL pointing at the currently stable backend
    """

    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID", "my-gcp-project")
        self.region = os.getenv("GCP_REGION", "us-central1")
        self.kong_admin_url = os.getenv("KONG_ADMIN_URL", "http://localhost:8001").rstrip("/")
        self.upstream_name = os.getenv("KONG_UPSTREAM_NAME", "indictrans-upstream")
        self.service_name = os.getenv("KONG_SERVICE_NAME", "indictrans-service")
        self.route_name = os.getenv("KONG_ROUTE_NAME", "indictrans-route")
        self.route_paths = [
            path.strip()
            for path in os.getenv("KONG_ROUTE_PATHS", "/infer").split(",")
            if path.strip()
        ]
        self.stable_target_url = os.getenv("KONG_STABLE_TARGET_URL")
        self._deployed_urls: dict[str, str] = {}

    def _gcloud_binary(self) -> str:
        if os.name == "nt":
            return shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud.cmd"
        return shutil.which("gcloud") or "gcloud"

    async def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

    @staticmethod
    def _target_from_url(url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Expected absolute backend URL, got: {url}")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        host = parsed.hostname
        if not host:
            raise ValueError(f"Could not parse backend host from URL: {url}")
        return f"{host}:{port}"

    async def deploy_model(self, model_id: str, image_uri: str, config: dict[str, Any]) -> tuple[str, str]:
        print(f"[GCP] Deploying {model_id} to Google Cloud Run in {self.region}...")

        service_name = f"bhashini-{model_id.replace('_', '-')}"
        source_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "model_server"))

        cmd = [
            self._gcloud_binary(),
            "run",
            "deploy",
            service_name,
            f"--source={source_dir}",
            f"--region={self.region}",
            f"--project={self.project_id}",
            "--set-env-vars=MODEL_NAME=ai4bharat/indictrans2-en-indic-dist-200M",
            "--allow-unauthenticated",
            "--format=json",
        ]

        try:
            result = await self._run(cmd)
            output = json.loads(result.stdout)
            service_url = output.get("status", {}).get("url")
            if not service_url:
                raise ValueError("gcloud did not return status.url")
            print(f"[GCP] Deployment successful! URL: {service_url}")
        except FileNotFoundError:
            service_url = f"https://{service_name}-fake.run.app"
            print("[GCP] gcloud CLI not found. Running in MOCK GCP mode.")
        except (subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as e:
            service_url = f"https://{service_name}-fake.run.app"
            print(f"[GCP] Deployment unavailable, using MOCK GCP URL {service_url}: {e}")

        self._deployed_urls[service_name] = service_url
        return service_name, "v1"

    async def _describe_service_url(self, service_name: str) -> str:
        if service_name in self._deployed_urls:
            return self._deployed_urls[service_name]

        cmd = [
            self._gcloud_binary(),
            "run",
            "services",
            "describe",
            service_name,
            f"--region={self.region}",
            f"--project={self.project_id}",
            "--format=json",
        ]
        result = await self._run(cmd)
        output = json.loads(result.stdout)
        service_url = output.get("status", {}).get("url")
        if not service_url:
            raise ValueError(f"Could not determine Cloud Run URL for {service_name}")
        self._deployed_urls[service_name] = service_url
        return service_url

    async def get_deployment_status(self, fn_id: str, version_id: str) -> str:
        return "ACTIVE"

    async def get_health_metrics(self, fn_id: str, version_id: str) -> dict[str, float]:
        return {"p95_latency_ms": 0.0, "error_rate_pct": 0.0}

    async def _ensure_service_route(self, client: httpx.AsyncClient) -> None:
        upstream_payload = {"name": self.upstream_name, "algorithm": "round-robin"}
        resp = await client.put(f"/upstreams/{self.upstream_name}", json=upstream_payload)
        resp.raise_for_status()

        service_payload = {
            "name": self.service_name,
            "host": self.upstream_name,
            "port": 443,
            "protocol": "https",
        }
        resp = await client.put(f"/services/{self.service_name}", json=service_payload)
        resp.raise_for_status()

        route_payload = {
            "name": self.route_name,
            "paths": self.route_paths,
            "strip_path": False,
        }
        resp = await client.put(
            f"/services/{self.service_name}/routes/{self.route_name}",
            json=route_payload,
        )
        resp.raise_for_status()

    async def _disable_stale_targets(self, client: httpx.AsyncClient, desired_targets: set[str]) -> None:
        resp = await client.get(f"/upstreams/{self.upstream_name}/targets/all")
        if resp.status_code == 404:
            return
        resp.raise_for_status()

        for target in resp.json().get("data", []):
            target_name = target.get("target")
            if target_name and target_name not in desired_targets and target.get("weight", 0) != 0:
                disable = await client.post(
                    f"/upstreams/{self.upstream_name}/targets",
                    json={"target": target_name, "weight": 0},
                )
                disable.raise_for_status()

    async def route_traffic(self, fn_id: str, version_id: str, weight: int) -> None:
        if not 0 <= int(weight) <= 100:
            raise ValueError(f"Traffic weight must be 0..100, got {weight}")

        canary_url = await self._describe_service_url(fn_id)
        canary_target = self._target_from_url(canary_url)

        stable_target = None
        if self.stable_target_url:
            stable_target = self._target_from_url(self.stable_target_url)
        elif int(weight) not in (0, 100):
            raise RuntimeError(
                "KONG_STABLE_TARGET_URL is required for partial GCP canary traffic. "
                "Set it to the currently stable Cloud Run service URL."
            )

        desired: dict[str, int] = {canary_target: int(weight)}
        if stable_target:
            desired[stable_target] = 100 - int(weight)

        print(f"[GCP-KONG] Applying desired traffic weights via {self.kong_admin_url}: {desired}")

        async with httpx.AsyncClient(base_url=self.kong_admin_url, timeout=10.0) as client:
            await self._ensure_service_route(client)
            await self._disable_stale_targets(client, set(desired))
            for target, target_weight in desired.items():
                resp = await client.post(
                    f"/upstreams/{self.upstream_name}/targets",
                    json={"target": target, "weight": target_weight},
                )
                resp.raise_for_status()

    async def promote(self, fn_id: str, version_id: str, model_name: str, image_tag: str) -> None:
        print(f"[GCP-KONG] Promoting {fn_id} to 100% traffic")
        await self.route_traffic(fn_id, version_id, 100)

    async def rollback(self, fn_id: str, version_id: str, model_name: str, image_tag: str, reason: str) -> None:
        print(f"[GCP-KONG] Rolling back {fn_id} to 0% traffic (Reason: {reason})")
        await self.route_traffic(fn_id, version_id, 0)

    async def delete_deployment(self, fn_id: str, version_id: str) -> None:
        print(f"[GCP] Deleting Cloud Run service {fn_id}")
        cmd = [
            self._gcloud_binary(),
            "run",
            "services",
            "delete",
            fn_id,
            f"--region={self.region}",
            f"--project={self.project_id}",
            "--quiet",
        ]
        try:
            await self._run(cmd)
        except Exception as e:
            print(f"[GCP] Could not delete: {e}")
