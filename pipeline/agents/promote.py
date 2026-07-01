import httpx
import logging
from router.db import log_event

logger = logging.getLogger(__name__)


async def set_router_weight(pct: int, router_url: str, client: httpx.AsyncClient):
    await client.post(f"{router_url}/__control/weight", json={"pct": pct})


async def promote(
    model_name: str,
    fn_id: str,
    version_id: str,
    image_tag: str,
    router_url: str = "http://localhost:8000",
    client: httpx.AsyncClient | None = None,
):
    logger.info(f"PROMOTING {model_name} to 100% traffic")

    if client:
        await set_router_weight(100, router_url, client)
    else:
        async with httpx.AsyncClient(timeout=10.0) as c:
            await set_router_weight(100, router_url, c)

    log_event(
        model_name=model_name,
        git_sha="unknown",
        image_tag=image_tag,
        fn_id=fn_id,
        version_id=version_id,
        stage="promoted",
        traffic_pct=100,
    )


async def rollback(
    model_name: str,
    fn_id: str,
    version_id: str,
    image_tag: str,
    reason: str,
    router_url: str = "http://localhost:8000",
    client: httpx.AsyncClient | None = None,
):
    logger.warning(f"ROLLING BACK {model_name} to 0% traffic! Reason: {reason}")

    if client:
        await set_router_weight(0, router_url, client)
    else:
        async with httpx.AsyncClient(timeout=10.0) as c:
            await set_router_weight(0, router_url, c)

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
