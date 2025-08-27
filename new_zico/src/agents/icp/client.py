import requests
import json
import sys
import os
from typing import Any, Dict, Optional, List
from .config import ICPConfig
import logging

# Adicionar src ao path para importar utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from utils.ic_urls import canister_http_base, format_canister_endpoint

logger = logging.getLogger(__name__)

def _canister_url(canister_id: str, endpoint: str) -> str:
    """Constrói URL para consultas HTTP diretas aos canisters"""
    if not ICPConfig.BASE_URL:
        raise RuntimeError("ICP_BASE_URL não configurado para consultas read-only")
    return format_canister_endpoint(canister_id, endpoint, ICPConfig.BASE_URL)

def query_stake_status(principal: Optional[str] = None) -> Dict[str, Any]:
    """
    Consulta status de staking via HTTP (read-only)
    
    Args:
        principal: Principal do usuário (opcional)
        
    Returns:
        Dict com dados do stake ou erro
    """
    try:
        params = {}
        if principal:
            params["principal"] = principal
            
        response = requests.get(
            _canister_url(ICPConfig.STAKING_CANISTER_ID, "/staking/status"), 
            params=params, 
            timeout=ICPConfig.TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao consultar status de staking: {e}")
        return {"error": f"Falha na consulta: {e}"}
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return {"error": f"Erro interno: {e}"}

def query_rates(pair: Dict[str, str]) -> Dict[str, Any]:
    """
    Consulta taxas de swap via HTTP (read-only)
    
    Args:
        pair: Dicionário com tokenA e tokenB
        
    Returns:
        Dict com taxas ou erro
    """
    try:
        response = requests.get(
            _canister_url(ICPConfig.SWAP_CANISTER_ID, "/swap/rates"), 
            params=pair, 
            timeout=ICPConfig.TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao consultar taxas: {e}")
        return {"error": f"Falha na consulta: {e}"}
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return {"error": f"Erro interno: {e}"}

def query_swap_quote(tokenA: str, tokenB: str, amount_e8s: int) -> Dict[str, Any]:
    """
    Consulta cotação de swap via HTTP (read-only)
    
    Args:
        tokenA: Token de entrada
        tokenB: Token de saída  
        amount_e8s: Quantidade em e8s
        
    Returns:
        Dict com cotação ou erro
    """
    try:
        params = {
            "tokenA": tokenA,
            "tokenB": tokenB,
            "amount_e8s": amount_e8s
        }
        
        response = requests.get(
            _canister_url(ICPConfig.SWAP_CANISTER_ID, "/swap/quote"), 
            params=params, 
            timeout=ICPConfig.TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao consultar cotação: {e}")
        return {"error": f"Falha na consulta: {e}"}
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return {"error": f"Erro interno: {e}"}

def query_swap_history(principal: str, limit: int = 50) -> Dict[str, Any]:
    """
    Consulta histórico de swaps via HTTP (read-only)
    
    Args:
        principal: Principal do usuário
        limit: Limite de resultados
        
    Returns:
        Dict com histórico ou erro
    """
    try:
        params = {
            "principal": principal,
            "limit": limit
        }
        
        response = requests.get(
            _canister_url(ICPConfig.SWAP_CANISTER_ID, "/swap/history"), 
            params=params, 
            timeout=ICPConfig.TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao consultar histórico: {e}")
        return {"error": f"Falha na consulta: {e}"}
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return {"error": f"Erro interno: {e}"}

def query_staking_params() -> Dict[str, Any]:
    """
    Consulta parâmetros de staking via HTTP (read-only)
    
    Returns:
        Dict com parâmetros ou erro
    """
    try:
        response = requests.get(
            _canister_url(ICPConfig.STAKING_CANISTER_ID, "/staking/params"), 
            timeout=ICPConfig.TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao consultar parâmetros de staking: {e}")
        return {"error": f"Falha na consulta: {e}"}
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return {"error": f"Erro interno: {e}"}

def get_canister_info(canister_name: str) -> Dict[str, Any]:
    """
    Retorna informações do canister incluindo interface Candid
    
    Args:
        canister_name: Nome do canister ("staking", "swap" ou "bitcoin")
        
    Returns:
        Dict com informações do canister
    """
    if canister_name not in ["staking", "swap", "bitcoin"]:
        return {"error": "Canister inválido. Use 'staking', 'swap' ou 'bitcoin'"}
    
    if canister_name == "staking":
        canister_id = ICPConfig.STAKING_CANISTER_ID
    elif canister_name == "swap":
        canister_id = ICPConfig.SWAP_CANISTER_ID
    else:  # bitcoin
        canister_id = ICPConfig.BITCOIN_CANISTER_ID
    
    # Ler arquivo .did se disponível
    did_content = ""
    try:
        with open(f"icp_canisters/{canister_name}.did", "r", encoding="utf-8") as f:
            did_content = f.read()
    except FileNotFoundError:
        logger.warning(f"Arquivo .did não encontrado para {canister_name}")
    except Exception as e:
        logger.error(f"Erro ao ler arquivo .did: {e}")
    
    # Definir métodos disponíveis
    methods = {
        "staking": [
            {
                "name": "start_staking",
                "type": "update",
                "args": ["amount_e8s: nat", "duration_s: nat"],
                "description": "Inicia um novo stake"
            },
            {
                "name": "get_stake_status", 
                "type": "query",
                "args": ["user: opt principal"],
                "description": "Consulta status dos stakes"
            },
            {
                "name": "withdraw_stake",
                "type": "update", 
                "args": ["stake_id: nat"],
                "description": "Retira stake após vencimento"
            },
            {
                "name": "params",
                "type": "query",
                "args": [],
                "description": "Parâmetros de staking"
            }
        ],
        "swap": [
            {
                "name": "quote",
                "type": "query",
                "args": ["pair: Pair", "amount_in_e8s: nat"],
                "description": "Cotação de swap"
            },
            {
                "name": "create_swap",
                "type": "update",
                "args": ["pair: Pair", "amount_in_e8s: nat", "min_out_e8s: nat"],
                "description": "Executa swap"
            },
            {
                "name": "get_rates",
                "type": "query", 
                "args": ["pair: Pair"],
                "description": "Taxa de câmbio atual"
            },
            {
                "name": "list_swaps",
                "type": "query",
                "args": ["user: principal", "cursor: opt nat"],
                "description": "Histórico de swaps"
            }
        ],
        "bitcoin": [
            {
                "name": "http_request",
                "type": "query",
                "args": ["request: HttpRequest"],
                "description": "HTTP endpoint para operações Bitcoin"
            },
            {
                "name": "add_mock_balance",
                "type": "update",
                "args": ["address: text", "balance: nat64"],
                "description": "Adiciona saldo mock para teste"
            },
            {
                "name": "get_mock_balance",
                "type": "query",
                "args": ["address: text"],
                "description": "Consulta saldo mock"
            },
            {
                "name": "list_mock_addresses",
                "type": "query",
                "args": [],
                "description": "Lista endereços mock disponíveis"
            }
        ]
    }
    
    return {
        "canisterId": canister_id,
        "did": did_content,
        "methods": methods.get(canister_name, []),
        "network": "ic" if "ic0.app" in ICPConfig.BASE_URL else "local"
    }
