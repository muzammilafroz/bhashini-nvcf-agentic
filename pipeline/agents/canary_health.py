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
    
    while (time.time() - start_time) < promote_after_seconds:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{router_url}/__control/state")
                state = resp.json()
                
            p95 = state.get("p95_latency_ms", 0.0)
            err_rate = state.get("error_rate_pct", 0.0)
            
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
            logger.error(f"Error fetching router state: {e}")
            
        await asyncio.sleep(2) # Poll every 2s for tests, ~10s for prod
        
    # If we made it here, promote!
    await promote(model_name, fn_id, version_id, image_tag, router_url)
    return True
