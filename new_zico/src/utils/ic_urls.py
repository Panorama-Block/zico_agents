"""
Utilitários para formatação de URLs dos canisters ICP
"""

def canister_http_base(canister_id: str, base_url: str = "http://127.0.0.1:4943") -> str:
    """
    Formata a URL base HTTP para um canister ICP de acordo com o ambiente.

    Args:
        canister_id: ID do canister
        base_url: URL base configurada (auto-detecta local vs mainnet)

    Returns:
        URL formatada corretamente para o ambiente
    """
    # Detecta ambiente local vs mainnet
    if "localhost" in base_url or "127.0.0.1" in base_url:
        # Local: http://{canister_id}.localhost:4943
        port = "4943"  # porta padrão do dfx
        if ":" in base_url:
            port = base_url.split(":")[-1]
        return f"http://{canister_id}.localhost:{port}"

    # Mainnet: https://{canister_id}.icp0.io (formato recomendado)
    if "ic0.app" in base_url:
        return f"https://{canister_id}.ic0.app"
    else:
        # Usa icp0.io como padrão moderno
        return f"https://{canister_id}.icp0.io"

def format_canister_endpoint(canister_id: str, endpoint: str, base_url: str = "http://127.0.0.1:4943") -> str:
    """
    Formata URL completa para um endpoint específico do canister.

    Args:
        canister_id: ID do canister
        endpoint: Path do endpoint (ex: "/get-balance", "/staking/status")
        base_url: URL base configurada

    Returns:
        URL completa do endpoint
    """
    base = canister_http_base(canister_id, base_url)
    endpoint = endpoint.lstrip('/')  # Remove / inicial se presente
    return f"{base}/{endpoint}"
