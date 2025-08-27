import os
from dataclasses import dataclass

@dataclass 
class FetchConfig:
    """Configuração para integração com Fetch.ai uAgents e ASI:One"""
    
    # Endpoints dos advisors Fetch.ai (uAgents/ASI:One)
    TIMING_URL: str = os.getenv("FETCH_TIMING_URL", "")
    SIZING_URL: str = os.getenv("FETCH_SIZING_URL", "")
    FEESLIP_URL: str = os.getenv("FETCH_FEESLIP_URL", "")
    METRICS_URL: str = os.getenv("FETCH_METRICS_URL", "")
    
    # URLs de fallback para testes
    FALLBACK_TIMING_URL: str = os.getenv("FETCH_FALLBACK_TIMING_URL", "https://api.fetch.ai/v1/advisors/timing")
    FALLBACK_SIZING_URL: str = os.getenv("FETCH_FALLBACK_SIZING_URL", "https://api.fetch.ai/v1/advisors/sizing")
    FALLBACK_FEESLIP_URL: str = os.getenv("FETCH_FALLBACK_FEESLIP_URL", "https://api.fetch.ai/v1/advisors/feeslip")
    FALLBACK_METRICS_URL: str = os.getenv("FETCH_FALLBACK_METRICS_URL", "https://api.fetch.ai/v1/advisors/metrics")
    
    # Configurações de autenticação
    API_KEY: str = os.getenv("FETCH_API_KEY", "")
    ASI_ONE_KEY: str = os.getenv("ASI_ONE_API_KEY", "")
    
    # Timeouts e limites
    TIMEOUT: int = int(os.getenv("FETCH_HTTP_TIMEOUT", "15"))
    MAX_RETRIES: int = int(os.getenv("FETCH_MAX_RETRIES", "3"))
    
    # Configurações de cache
    CACHE_TTL: int = int(os.getenv("FETCH_CACHE_TTL", "300"))  # 5 minutos
    
    # Chains suportadas
    SUPPORTED_CHAINS = ["avalanche", "icp", "ethereum", "bitcoin"]
    
    # Assets suportados
    SUPPORTED_ASSETS = ["AVAX", "ICP", "BTC", "ETH", "USDC", "USDT", "ckBTC", "ckETH", "CHAT"]
    
    # Mensagens de resposta
    ADVISOR_SUCCESS_MESSAGE = "💡 Análise da Fetch.ai: {insight}"
    ADVISOR_ERROR_MESSAGE = "❌ Erro no advisor Fetch.ai: {error}"
    TIMING_SUCCESS_MESSAGE = "⏰ Análise de Timing: {analysis}"
    SIZING_SUCCESS_MESSAGE = "📊 Recomendação de Posição: {recommendation}"
    FEESLIP_SUCCESS_MESSAGE = "💰 Análise de Taxas: {analysis}"
    METRICS_SUCCESS_MESSAGE = "📈 Métricas de Rede: {metrics}"
    
    # Configurações de fallback para quando APIs não estão disponíveis
    ENABLE_FALLBACK_RESPONSES: bool = os.getenv("FETCH_ENABLE_FALLBACK", "true").lower() == "true"
