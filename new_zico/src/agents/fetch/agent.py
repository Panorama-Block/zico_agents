from langgraph.prebuilt import create_react_agent
from .tools import get_tools
import logging

logger = logging.getLogger(__name__)

class FetchAgent:
    """
    Agente Fetch.ai para análises de mercado e conselhos de trading
    
    Funcionalidades:
    - Análise de timing de mercado via advisors Fetch.ai
    - Recomendações de tamanho de posição
    - Estimativas de fees e slippage  
    - Métricas de saúde de rede
    - Integração com uAgents e ASI:One platform
    
    Fluxo de trabalho:
    1. Usuário solicita análise de mercado via chat
    2. Agente Fetch.ai consulta advisors especializados via HTTP
    3. Respostas são processadas e formatadas em português
    4. Conselhos são integrados com recomendações acionáveis
    5. Fallbacks automáticos quando APIs não estão disponíveis
    """
    
    def __init__(self, llm):
        """
        Inicializa o agente Fetch.ai
        
        Args:
            llm: Modelo de linguagem (Gemini/OpenAI)
        """
        self.llm = llm
        logger.info("Inicializando FetchAgent com advisors de trading")
        
        # Criar agente reativo com ferramentas Fetch.ai
        self.agent = create_react_agent(
            model=llm,
            tools=get_tools(),
            name="fetch_agent"
        )
        
        logger.info("FetchAgent inicializado com sucesso")
    
    def get_capabilities(self) -> list[str]:
        """
        Retorna lista de capacidades do agente Fetch.ai
        
        Returns:
            Lista de strings descrevendo capacidades
        """
        return [
            "Análise de timing de mercado (volatilidade, regime)",
            "Recomendações de tamanho de posição (Kelly, ATR)",
            "Estimativas de fees e slippage para múltiplas chains",
            "Métricas de saúde de rede (TPS, whales, volume)", 
            "Integração com advisors Fetch.ai via HTTP",
            "Suporte para AVAX, ICP, BTC, ETH e outros assets",
            "Fallbacks automáticos quando APIs indisponíveis",
            "Análises em múltiplos horizontes temporais"
        ]
    
    def can_handle(self, message: str, context: dict = None) -> bool:
        """
        Determina se o agente pode lidar com uma mensagem
        
        Args:
            message: Mensagem do usuário
            context: Contexto adicional
            
        Returns:
            True se pode lidar com a mensagem
        """
        message_lower = message.lower()
        
        # Palavras-chave para análise de mercado
        market_keywords = [
            "análise", "mercado", "volatilidade", "timing", 
            "quando", "momento", "tendência", "regime"
        ]
        
        # Palavras-chave para sizing
        sizing_keywords = [
            "posição", "tamanho", "quanto", "size", "sizing",
            "risco", "capital", "portfólio", "alocação"
        ]
        
        # Palavras-chave para fees/slippage
        cost_keywords = [
            "taxa", "fee", "custo", "slippage", "deslizamento",
            "liquidez", "spread", "comissão"
        ]
        
        # Palavras-chave para métricas
        metrics_keywords = [
            "métrica", "rede", "network", "tps", "transações",
            "volume", "atividade", "whales", "saúde"
        ]
        
        # Palavras-chave para assets suportados
        asset_keywords = [
            "avax", "icp", "btc", "eth", "bitcoin", "ethereum",
            "avalanche", "ckbtc", "cketh", "chat", "usdc", "usdt"
        ]
        
        # Verificar se contém palavras-chave relevantes
        has_market = any(keyword in message_lower for keyword in market_keywords)
        has_sizing = any(keyword in message_lower for keyword in sizing_keywords)
        has_cost = any(keyword in message_lower for keyword in cost_keywords)
        has_metrics = any(keyword in message_lower for keyword in metrics_keywords)
        has_asset = any(keyword in message_lower for keyword in asset_keywords)
        
        return (has_market or has_sizing or has_cost or has_metrics) and has_asset
    
    def get_confidence_score(self, message: str, context: dict = None) -> float:
        """
        Calcula pontuação de confiança para lidar com a mensagem
        
        Args:
            message: Mensagem do usuário
            context: Contexto adicional
            
        Returns:
            Pontuação de 0.0 a 1.0
        """
        if not self.can_handle(message, context):
            return 0.0
        
        message_lower = message.lower()
        score = 0.0
        
        # Pontuação base para capacidade de lidar
        score += 0.2
        
        # Bonificação para análises específicas
        analysis_terms = [
            ("timing", 0.2), ("análise", 0.15), ("mercado", 0.15),
            ("posição", 0.2), ("tamanho", 0.15), ("risco", 0.1),
            ("taxa", 0.15), ("slippage", 0.2), ("custo", 0.1),
            ("métrica", 0.15), ("rede", 0.1), ("volume", 0.1)
        ]
        
        for term, points in analysis_terms:
            if term in message_lower:
                score += points
        
        # Bonificação para assets específicos
        asset_terms = [
            ("avax", 0.1), ("icp", 0.1), ("btc", 0.1), ("eth", 0.1)
        ]
        
        for term, points in asset_terms:
            if term in message_lower:
                score += points
        
        # Bonificação para menções de Fetch.ai
        if any(term in message_lower for term in ["fetch", "advisor", "conselho"]):
            score += 0.15
        
        return min(score, 1.0)
    
    def supports_asset(self, asset: str) -> bool:
        """
        Verifica se um asset é suportado
        
        Args:
            asset: Símbolo do asset
            
        Returns:
            True se suportado
        """
        from .config import FetchConfig
        return asset.upper() in FetchConfig.SUPPORTED_ASSETS
    
    def supports_chain(self, chain: str) -> bool:
        """
        Verifica se uma chain é suportada
        
        Args:
            chain: Nome da chain
            
        Returns:
            True se suportada
        """
        from .config import FetchConfig
        return chain.lower() in FetchConfig.SUPPORTED_CHAINS
