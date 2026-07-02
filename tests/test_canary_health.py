import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from pipeline.agents.canary_health import check_canary_health

@pytest.mark.anyio
@patch("pipeline.agents.canary_health.httpx.AsyncClient")
async def test_canary_health_good(mock_client_cls):
    # Mock router response
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"p95_latency_ms": 100, "error_rate_pct": 0.0}
    mock_client.get.return_value = mock_resp
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    
    # Run gate with small window
    healthy, reason = await check_canary_health(
        "test-model", "fn-123", "v-123", "img", 1, {"p95_latency_ms": 500, "error_rate_pct": 1.0}
    )

    assert healthy is True
    assert reason is None

@pytest.mark.anyio
@patch("pipeline.agents.canary_health.httpx.AsyncClient")
async def test_canary_health_bad(mock_client_cls):
    # Mock router response with bad metrics
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"p95_latency_ms": 1000, "error_rate_pct": 5.0} # Breaches error rate
    mock_client.get.return_value = mock_resp
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    
    healthy, reason = await check_canary_health(
        "test-model", "fn-123", "v-123", "img", 2, {"p95_latency_ms": 500, "error_rate_pct": 1.0}
    )

    assert healthy is False
    assert reason == "p95 latency 1000.00 > 500"
