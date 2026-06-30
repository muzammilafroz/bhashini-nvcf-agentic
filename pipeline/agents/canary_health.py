import asyncio
import logging
import time

import httpx

from pipeline.agents.promote import promote, rollback

logger = logging.getLogger(__name__)

async def check_canary_health(
    model_name: str,
    fn_id: str,
    version_id: str,
    image_tag: str,
    promote_after_seconds: int,
    rollback_on: dict,
    router_url: str = "http://localhost:8000"
):
    """
    Monitors router metrics for `promote_after_seconds`.
    Rolls back immediately if thresholds are breached.
    Promotes if time elapses without breach.
    """
    logger.info(f"Starting canary health gate for {model_name}. Window: {promote_after_seconds}s")
    
    start_time = time.time()
    
        import os
        provider_name = os.getenv("CLOUD_PROVIDER", "MOCK_NVCF")
        
        while (time.time() - start_time) < promote_after_seconds:
            try:
                async with httpx.AsyncClient() as client:
                    if provider_name == "MOCK_NVCF":
                        # v1: Query SQLite mock gateway
                        resp = await client.get(f"{router_url}/__control/state")
                        state = resp.json()
                        p95 = state.get("p95_latency_ms", 0.0)
                        err_rate = state.get("error_rate_pct", 0.0)
                    else:
                        # v2/v3: Query Real Prometheus on DigitalOcean
                        # Assuming DO IP is in router_url for Prometheus e.g., http://142.93.209.191:9090
                        prom_url = os.getenv("PROMETHEUS_URL", "http://142.93.209.191:9090")
                        
                        # Example simplified PromQL for 5xx errors from Kong
                        query = 'rate(kong_http_status{code=~"5.."}[1m]) / rate(kong_http_status[1m]) * 100'
                        resp = await client.get(f"{prom_url}/api/v1/query", params={"query": query})
                        data = resp.json()
                        err_rate = 0.0
                        if data.get("data", {}).get("result"):
                            err_rate = float(data["data"]["result"][0]["value"][1])
                            
                        # Simplified P95 latency query from Kong
                        p95_query = 'histogram_quantile(0.95, rate(kong_latency_bucket[1m]))'
                        resp = await client.get(f"{prom_url}/api/v1/query", params={"query": p95_query})
                        data = resp.json()
                        p95 = 0.0
                        if data.get("data", {}).get("result"):
                            p95 = float(data["data"]["result"][0]["value"][1])

                logger.info(f"Canary metrics: p95={p95:.2f}ms, err={err_rate:.2f}%")
                
                # Check thresholds
                if "p95_latency_ms" in rollback_on and p95 > rollback_on["p95_latency_ms"]:
                    reason = f"p95 latency {p95:.2f} > {rollback_on['p95_latency_ms']}"
                    await rollback(model_name, fn_id, version_id, image_tag, reason, router_url)
                    return False
                    
                if "error_rate_pct" in rollback_on and err_rate > rollback_on["error_rate_pct"]:
                    reason = f"Error rate {err_rate:.2f}% > {rollback_on['error_rate_pct']}%"
                    await rollback(model_name, fn_id, version_id, image_tag, reason, router_url)
                    return False
                    
            except Exception as e:
                logger.error(f"Error fetching router/prometheus state: {e}")
                
            await asyncio.sleep(2) # Poll every 2s for tests, ~10s for prod
            
        # If we made it here, promote!
        if provider_name == "MOCK_NVCF":
            await promote(model_name, fn_id, version_id, image_tag, router_url)
        # Note: If generic provider is used, the orchestrator handles the route_traffic call
        
        return True
