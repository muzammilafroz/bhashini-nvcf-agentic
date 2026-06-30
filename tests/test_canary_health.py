import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from pipeline.agents.canary_health import check_canary_health

@pytest.mark.anyio
@patch("pipeline.agents.canary_health.httpx.AsyncClient")
@patch("pipeline.agents.canary_health.rollback")
@patch("pipeline.agents.canary_health.promote")
async def test_canary_health_good(mock_promote, mock_rollback, mock_client_cls):
    # Mock router response
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"p95_latency_ms": 100, "error_rate_pct": 0.0}
    mock_client.get.return_value = mock_resp
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    
    # Run gate with small window
    result = await check_canary_health(
        "test-model", "fn-123", "v-123", "img", 1, {"p95_latency_ms": 500, "error_rate_pct": 1.0}
    )
    
    assert result is True
    mock_promote.assert_called_once()
    mock_rollback.assert_not_called()

@pytest.mark.anyio
@patch("pipeline.agents.canary_health.httpx.AsyncClient")
@patch("pipeline.agents.canary_health.rollback")
@patch("pipeline.agents.canary_health.promote")
async def test_canary_health_bad(mock_promote, mock_rollback, mock_client_cls):
    # Mock router response with bad metrics
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"p95_latency_ms": 1000, "error_rate_pct": 5.0} # Breaches error rate
    mock_client.get.return_value = mock_resp
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    
    result = await check_canary_health(
        "test-model", "fn-123", "v-123", "img", 2, {"p95_latency_ms": 500, "error_rate_pct": 1.0}
    )
    
    assert result is False
    mock_promote.assert_not_called()
    mock_rollback.assert_called_once()
