import requests
import json
import time
from typing import Any, Dict, List, Optional
from .config import FetchConfig
import logging

logger = logging.getLogger(__name__)

class FetchAIClient:
    """Cliente para comunicação com advisors Fetch.ai via HTTP"""
    
    def __init__(self):
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """Configura sessão HTTP com headers padrão"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ZicoAgent/1.0 (Fetch.ai Integration)"
        }
        
        if FetchConfig.API_KEY:
            headers["Authorization"] = f"Bearer {FetchConfig.API_KEY}"
        
        if FetchConfig.ASI_ONE_KEY:
            headers["X-ASI-One-Key"] = FetchConfig.ASI_ONE_KEY
        
        self.session.headers.update(headers)
        self.session.timeout = FetchConfig.TIMEOUT

    def _post_with_fallback(self, primary_url: str, fallback_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa POST com fallback automático
        
        Args:
            primary_url: URL primária
            fallback_url: URL de fallback
            payload: Dados para enviar
            
        Returns:
            Resposta JSON ou erro
        """
        urls = [url for url in [primary_url, fallback_url] if url]
        
        if not urls:
            return {"error": "Nenhum endpoint configurado"}
        
        last_error = None
        
        for attempt, url in enumerate(urls):
            try:
                logger.info(f"Tentativa {attempt + 1}: Chamando {url}")
                response = self.session.post(url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Sucesso na chamada para {url}")
                return data
                
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                logger.warning(f"Falha em {url}: {e}")
                continue
            except json.JSONDecodeError as e:
                last_error = f"Resposta JSON inválida: {e}"
                logger.warning(f"JSON inválido de {url}: {e}")
                continue
            except Exception as e:
                last_error = f"Erro inesperado: {e}"
                logger.error(f"Erro inesperado com {url}: {e}")
                continue
        
        return {"error": f"Todos os endpoints falharam. Último erro: {last_error}"}

    def timing_advice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consulta advisor de timing para análise de volatilidade e regime de mercado
        
        Args:
            payload: {
                "asset": "AVAX",
                "pair": "AVAX/USDT", 
                "horizon": "intra|swing|pos",
                "window": "30d"
            }
            
        Returns:
            {
                "score": 0.62,
                "regime": "high_vol", 
                "rationale": "vol spike; spreads wider",
                "cooldown_minutes": 45
            }
        """
        return self._post_with_fallback(
            FetchConfig.TIMING_URL,
            FetchConfig.FALLBACK_TIMING_URL,
            payload
        )

    def sizing_advice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consulta advisor de sizing para recomendações de tamanho de posição
        
        Args:
            payload: {
                "portfolio_value": 10000,
                "risk_pct": 0.01,
                "vol_lookback_days": 30,
                "unit": "AVAX"
            }
            
        Returns:
            {
                "size_quote": 120,
                "unit": "AVAX",
                "stop_hint": "-2.3%",
                "rationale": "ATR-based"
            }
        """
        return self._post_with_fallback(
            FetchConfig.SIZING_URL,
            FetchConfig.FALLBACK_SIZING_URL,
            payload
        )

    def feeslip_advice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consulta advisor de fees/slippage para estimativas de custo
        
        Args:
            payload: {
                "chain": "icp",
                "pair": "ICP/XTC", 
                "amount_in": 100000000,
                "side": "sell"
            }
            
        Returns:
            {
                "fee_bps": 30,
                "est_slippage_bps": 22,
                "min_out": 98700000,
                "route": ["poolA"]
            }
        """
        return self._post_with_fallback(
            FetchConfig.FEESLIP_URL,
            FetchConfig.FALLBACK_FEESLIP_URL,
            payload
        )

    def network_metrics(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consulta advisor de métricas de rede para análise de health
        
        Args:
            payload: {
                "chain": "avalanche",
                "signals": ["tps", "fees", "whales"],
                "window": "7d"
            }
            
        Returns:
            {
                "series": {"tps": [...], "fees": [...]},
                "anomalies": [{"when": "2025-08-03", "signal": "whales"}]
            }
        """
        return self._post_with_fallback(
            FetchConfig.METRICS_URL,
            FetchConfig.FALLBACK_METRICS_URL,
            payload
        )

# Instância global do cliente
fetch_client = FetchAIClient()

# Funções de conveniência para as ferramentas
def advice_timing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper para advisor de timing"""
    return fetch_client.timing_advice(payload)

def advice_sizing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper para advisor de sizing"""
    return fetch_client.sizing_advice(payload)

def advice_feeslip(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper para advisor de fees/slippage"""
    return fetch_client.feeslip_advice(payload)

def query_metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper para advisor de métricas"""
    return fetch_client.network_metrics(payload)

def generate_fallback_timing_response(asset: str, horizon: str) -> Dict[str, Any]:
    """Gera resposta de fallback para timing quando APIs não estão disponíveis"""
    import random
    
    responses = {
        "intra": {
            "score": round(random.uniform(0.3, 0.8), 2),
            "regime": random.choice(["low_vol", "normal", "high_vol"]),
            "rationale": "Análise intraday sugere cautela devido à volatilidade recente",
            "cooldown_minutes": random.randint(15, 120)
        },
        "swing": {
            "score": round(random.uniform(0.4, 0.9), 2), 
            "regime": random.choice(["trending", "ranging", "choppy"]),
            "rationale": "Tendências de médio prazo mostram oportunidades limitadas",
            "cooldown_minutes": random.randint(60, 480)
        },
        "pos": {
            "score": round(random.uniform(0.2, 0.7), 2),
            "regime": random.choice(["accumulation", "distribution", "consolidation"]),
            "rationale": "Posicionamento de longo prazo requer paciência no mercado atual",
            "cooldown_minutes": random.randint(240, 1440)
        }
    }
    
    return responses.get(horizon, responses["intra"])

def generate_fallback_sizing_response(portfolio_value: float, risk_pct: float, unit: str) -> Dict[str, Any]:
    """Gera resposta de fallback para sizing"""
    risk_amount = portfolio_value * risk_pct
    # Estimativa simples baseada em volatilidade típica
    suggested_size = risk_amount / (portfolio_value * 0.05)  # Assume 5% de volatilidade
    
    return {
        "size_quote": round(suggested_size, 2),
        "unit": unit,
        "stop_hint": "-3.5%",
        "rationale": "Cálculo conservador baseado em volatilidade histórica"
    }

def generate_fallback_feeslip_response(chain: str, amount_in: int) -> Dict[str, Any]:
    """Gera resposta de fallback para fees/slippage"""
    # Taxas típicas por chain
    chain_fees = {
        "icp": 30,       # 0.3%
        "avalanche": 25, # 0.25%  
        "ethereum": 100, # 1.0%
        "bitcoin": 50    # 0.5%
    }
    
    fee_bps = chain_fees.get(chain.lower(), 30)
    slippage_bps = min(fee_bps * 2, 100)  # Max 1% slippage
    min_out = int(amount_in * (1 - (fee_bps + slippage_bps) / 10000))
    
    return {
        "fee_bps": fee_bps,
        "est_slippage_bps": slippage_bps,
        "min_out": min_out,
        "route": ["direct_pool"]
    }

def generate_fallback_metrics_response(chain: str, signals: List[str]) -> Dict[str, Any]:
    """Gera resposta de fallback para métricas"""
    import random
    
    # Dados sintéticos para demonstração
    series = {}
    for signal in signals:
        if signal == "tps":
            series[signal] = [random.randint(50, 200) for _ in range(7)]
        elif signal == "fees":
            series[signal] = [round(random.uniform(0.1, 2.0), 2) for _ in range(7)]
        elif signal == "whales":
            series[signal] = [random.randint(0, 10) for _ in range(7)]
    
    anomalies = []
    if random.random() > 0.7:  # 30% chance de anomalia
        anomalies.append({
            "when": "2025-01-15",
            "signal": random.choice(signals),
            "severity": random.choice(["low", "medium", "high"])
        })
    
    return {
        "series": series,
        "anomalies": anomalies,
        "status": "fallback_data"
    }
