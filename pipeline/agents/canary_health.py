import asyncio
import logging
import time

import httpx

from pipeline.agents.promote import promote, rollback

logger = logging.getLogger(__name__)


async def fetch_metrics_from_router(router_url: str, client: httpx.AsyncClient) -> dict:
    """Fetch canary metrics from the local FastAPI canary router (v1 / mock mode)."""
    resp = await client.get(f"{router_url}/__control/state")
    state = resp.json()
    return {
        "p95_latency_ms": state.get("p95_latency_ms", 0.0),
        "error_rate_pct": state.get("error_rate_pct", 0.0),
    }


async def fetch_metrics_from_prometheus(prom_url: str, client: httpx.AsyncClient) -> dict:
    """Fetch canary metrics from a real Prometheus instance (v2 / production mode)."""
    # Error rate: percentage of 5xx responses from Kong
    err_query = 'rate(kong_http_status{code=~"5.."}[1m]) / rate(kong_http_status[1m]) * 100'
    resp = await client.get(f"{prom_url}/api/v1/query", params={"query": err_query})
    data = resp.json()
    err_rate = 0.0
    if data.get("data", {}).get("result"):
        err_rate = float(data["data"]["result"][0]["value"][1])

    # P95 latency from Kong histogram
    p95_query = 'histogram_quantile(0.95, rate(kong_latency_bucket[1m]))'
    resp = await client.get(f"{prom_url}/api/v1/query", params={"query": p95_query})
    data = resp.json()
    p95 = 0.0
    if data.get("data", {}).get("result"):
        p95 = float(data["data"]["result"][0]["value"][1])

    return {
        "p95_latency_ms": p95,
        "error_rate_pct": err_rate,
    }


async def check_canary_health(
    model_name: str,
    fn_id: str,
    version_id: str,
    image_tag: str,
    promote_after_seconds: int,
    rollback_on: dict,
    router_url: str = "http://localhost:8001",
    prometheus_url: str | None = None,
):
    """
    Monitors canary metrics for `promote_after_seconds`.
    Rolls back immediately if thresholds are breached.
    Promotes if time elapses without breach.

    If `prometheus_url` is provided, metrics are fetched from Prometheus.
    Otherwise, metrics come from the local canary router's /__control/state endpoint.
    """
    logger.info(f"Starting canary health gate for {model_name}. Window: {promote_after_seconds}s")

    start_time = time.time()

    async with httpx.AsyncClient(timeout=10.0) as client:
        while (time.time() - start_time) < promote_after_seconds:
            try:
                if prometheus_url:
                    metrics = await fetch_metrics_from_prometheus(prometheus_url, client)
                else:
                    metrics = await fetch_metrics_from_router(router_url, client)

                p95 = metrics["p95_latency_ms"]
                err_rate = metrics["error_rate_pct"]

                logger.info(f"Canary metrics: p95={p95:.2f}ms, err={err_rate:.2f}%")

                # Check thresholds
                if "p95_latency_ms" in rollback_on and p95 > rollback_on["p95_latency_ms"]:
                    reason = f"p95 latency {p95:.2f} > {rollback_on['p95_latency_ms']}"
                    return False, reason

                if "error_rate_pct" in rollback_on and err_rate > rollback_on["error_rate_pct"]:
                    reason = f"Error rate {err_rate:.2f}% > {rollback_on['error_rate_pct']}%"
                    return False, reason

            except Exception as e:
                logger.error(f"Error fetching canary metrics: {e}")

            await asyncio.sleep(2)  # Poll every 2s for tests, ~10s for prod

    # If we made it here, promote!
    return True, None
