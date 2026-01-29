import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.crypto_data.tools import get_price, get_coingecko_id, price_cache, metadata_cache

@pytest.mark.asyncio
async def test_get_price_success():
    # Clear cache
    price_cache.clear()
    metadata_cache.clear()

    with patch("src.agents.crypto_data.tools.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Mock search response
        mock_search_resp = MagicMock()
        mock_search_resp.json.return_value = {"coins": [{"id": "bitcoin", "name": "Bitcoin"}]}
        mock_search_resp.raise_for_status.return_value = None
        
        # Mock price response
        mock_price_resp = MagicMock()
        mock_price_resp.json.return_value = {"bitcoin": {"usd": 50000.0}}
        mock_price_resp.raise_for_status.return_value = None
        
        mock_client.get.side_effect = [mock_search_resp, mock_price_resp]

        price = await get_price("bitcoin")
        assert price == 50000.0
        assert mock_client.get.call_count == 2

@pytest.mark.asyncio
async def test_get_price_caching():
    # Clear cache
    price_cache.clear()
    metadata_cache.clear()

    with patch("src.agents.crypto_data.tools.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Mock responses (same as above)
        mock_search_resp = MagicMock()
        mock_search_resp.json.return_value = {"coins": [{"id": "bitcoin", "name": "Bitcoin"}]}
        
        mock_price_resp = MagicMock()
        mock_price_resp.json.return_value = {"bitcoin": {"usd": 50000.0}}
        
        mock_client.get.side_effect = [mock_search_resp, mock_price_resp]

        # First call
        price1 = await get_price("bitcoin")
        assert price1 == 50000.0
        
        # Second call should hit cache
        price2 = await get_price("bitcoin")
        assert price2 == 50000.0
        
        # Call count should still be 2 (1 for search, 1 for price) from the first call
        # The second call shouldn't trigger new requests
        assert mock_client.get.call_count == 2
