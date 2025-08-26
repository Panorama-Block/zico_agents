import os
from dataclasses import dataclass

@dataclass
class ICPConfig:
    """Configuração para integração com canisters ICP"""
    
    # Canisters IDs (configurar após deploy)
    STAKING_CANISTER_ID: str = os.getenv("ICP_STAKING_CANISTER_ID", "rdmx6-jaaaa-aaaah-qdrva-cai")
    SWAP_CANISTER_ID: str = os.getenv("ICP_SWAP_CANISTER_ID", "rdmx6-jaaaa-aaaah-qdrva-cai")
    BITCOIN_CANISTER_ID: str = os.getenv("ICP_BITCOIN_CANISTER_ID", "rdmx6-jaaaa-aaaah-qdrva-cai")

    # Read-only façade HTTP (opcional para consultas server-side)
    BASE_URL: str = os.getenv("ICP_BASE_URL", "https://ic0.app").rstrip("/")

    # Timeouts e limites
    TIMEOUT: int = int(os.getenv("ICP_HTTP_TIMEOUT", "15"))
    
    # Configurações de segurança
    DEFAULT_MAX_SLIPPAGE_BPS: int = int(os.getenv("ICP_DEFAULT_MAX_SLIPPAGE_BPS", "200"))  # 2%
    MAX_STAKE_AMOUNT_E8S: int = int(os.getenv("ICP_MAX_STAKE_AMOUNT_E8S", "1000000000000"))  # 10,000 tokens
    MIN_STAKE_AMOUNT_E8S: int = int(os.getenv("ICP_MIN_STAKE_AMOUNT_E8S", "100000000"))  # 1 token

    # Tokens suportados
    SUPPORTED_TOKENS = ["ICP", "ckBTC", "ckETH", "CHAT"]
    
    # Mensagens de resposta
    PLAN_SUCCESS_MESSAGE = "✅ Plano criado com sucesso! Confirme a transação na sua carteira Plug."
    PLAN_ERROR_MESSAGE = "❌ Erro ao criar plano: {error}"
    QUERY_ERROR_MESSAGE = "❌ Erro ao consultar dados ICP: {error}"
    CANISTER_NOT_FOUND = "❌ Canister não encontrado: {canister}"
