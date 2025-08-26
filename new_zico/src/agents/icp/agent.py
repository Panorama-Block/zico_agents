from langgraph.prebuilt import create_react_agent
from .tools import get_tools
import logging

logger = logging.getLogger(__name__)

class ICPAgent:
    """
    Agente ICP para Internet Computer Protocol
    
    Funcionalidades:
    - Gera planos de staking e swap (Candid + args) para frontend assinar via Plug/II
    - Consulta status, taxas e dados read-only dos canisters
    - Integração completa com canisters Motoko de staking e swap
    
    Fluxo de trabalho:
    1. Usuário solicita operação (stake/swap) via chat
    2. Agente ICP gera "plano" com Candid method + argumentos
    3. Frontend recebe plano e solicita assinatura via Plug/Internet Identity
    4. Transação é executada diretamente no canister
    5. Agente pode consultar resultados via métodos read-only
    """
    
    def __init__(self, llm):
        """
        Inicializa o agente ICP
        
        Args:
            llm: Modelo de linguagem (Gemini/OpenAI)
        """
        self.llm = llm
        logger.info("Inicializando ICPAgent com ferramentas de staking e swap")
        
        # Criar agente reativo com ferramentas ICP
        self.agent = create_react_agent(
            model=llm,
            tools=get_tools(),
            name="icp_agent"
        )
        
        logger.info("ICPAgent inicializado com sucesso")
    
    def get_capabilities(self) -> list[str]:
        """
        Retorna lista de capacidades do agente ICP
        
        Returns:
            Lista de strings descrevendo capacidades
        """
        return [
            "Planejamento de staking ICP (ICP, ckBTC, ckETH, CHAT)",
            "Planejamento de swaps entre tokens ICP",
            "Consulta de status de stakes ativos", 
            "Consulta de taxas de câmbio em tempo real",
            "Geração de transações Candid para assinatura",
            "Integração com canisters Motoko nativos",
            "Suporte para Plug Wallet e Internet Identity"
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
        
        # Palavras-chave para staking
        staking_keywords = [
            "stake", "staking", "apostar", "rendimento", 
            "recompensa", "yield", "apy", "lockup"
        ]
        
        # Palavras-chave para swap
        swap_keywords = [
            "swap", "trocar", "cambio", "exchange", 
            "converter", "trade", "negociar"
        ]
        
        # Palavras-chave para tokens ICP
        icp_keywords = [
            "icp", "ckbtc", "cketh", "chat", "internet computer",
            "ic", "motoko", "canister", "candid"
        ]
        
        # Verificar se contém palavras-chave relevantes
        has_staking = any(keyword in message_lower for keyword in staking_keywords)
        has_swap = any(keyword in message_lower for keyword in swap_keywords)
        has_icp = any(keyword in message_lower for keyword in icp_keywords)
        
        return has_staking or has_swap or has_icp
    
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
        score += 0.3
        
        # Bonificação para menções específicas de ICP
        if any(token in message_lower for token in ["icp", "ckbtc", "cketh", "chat"]):
            score += 0.3
        
        # Bonificação para operações específicas
        if any(op in message_lower for op in ["stake", "staking", "swap", "trocar"]):
            score += 0.2
        
        # Bonificação para menções de blockchain/DeFi
        if any(term in message_lower for term in ["canister", "motoko", "candid", "internet computer"]):
            score += 0.2
        
        return min(score, 1.0)
