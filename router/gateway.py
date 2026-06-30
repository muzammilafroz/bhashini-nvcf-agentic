import json
import logging
import random
import time
from collections import deque
from pydantic import BaseModel
import httpx

from fastapi import FastAPI, Request, Response

logger = logging.getLogger(__name__)

app = FastAPI(title="Canary Router")

# Global state
state = {
    "canary_weight": 0,  # 0 to 100
    "stable_url": "http://localhost:8000/infer", # Example default, typically injected via env var
    "canary_url": "http://localhost:8001/infer",
    "request_count": 0
}

# Rolling metrics (last 100 requests)
metrics = {
    "canary_latencies": deque(maxlen=100),
    "canary_errors": deque(maxlen=100)
}

class WeightRequest(BaseModel):
    pct: int

@app.post("/__control/weight")
async def set_weight(req: WeightRequest):
    if not (0 <= req.pct <= 100):
        return Response("Weight must be between 0 and 100", status_code=400)
    
    state["canary_weight"] = req.pct
    logger.info(f"Set canary weight to {req.pct}%")
    return {"status": "ok", "weight": req.pct}

@app.get("/__control/state")
async def get_state():
    latencies = list(metrics["canary_latencies"])
    errors = list(metrics["canary_errors"])
    
    p95 = 0.0
    if latencies:
        s_lat = sorted(latencies)
        idx = int(len(s_lat) * 0.95)
        if idx >= len(s_lat): idx = len(s_lat) - 1
        p95 = s_lat[idx]
        
    err_rate = (sum(errors) / len(errors) * 100) if errors else 0.0
    
    return {
        "weight": state["canary_weight"],
        "p95_latency_ms": p95,
        "error_rate_pct": err_rate
    }

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    # Don't proxy control endpoints
    if path.startswith("__control"):
        return Response("Not found", status_code=404)
        
    state["request_count"] += 1
    
    # Random seeded by request count for reproducible tests
    random.seed(state["request_count"])
    draw = random.randint(1, 100)
    
    target_url = state["canary_url"] if draw <= state["canary_weight"] else state["stable_url"]
    is_canary = target_url == state["canary_url"]
    
    # Read body
    body = await request.body()
    
    start_time = time.time()
    status_code = 500
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=request.method,
                url=f"{target_url}/{path}" if path else target_url,
                content=body,
                headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")},
            )
            status_code = resp.status_code
            content = resp.content
            headers = dict(resp.headers)
            if "content-encoding" in headers:
                del headers["content-encoding"]
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        content = str(e).encode()
        
    latency_ms = (time.time() - start_time) * 1000
    
    # Record metrics
    if is_canary:
        metrics["canary_latencies"].append(latency_ms)
        metrics["canary_errors"].append(1 if status_code >= 400 else 0)
        
    return Response(content=content, status_code=status_code, headers=headers)
