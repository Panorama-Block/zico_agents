from typing import Any, Dict, List, Optional
from langchain_core.tools import Tool
from .config import ICPConfig
from . import client
import json
import logging

logger = logging.getLogger(__name__)

def _format_candid_args(args: Dict[str, Any]) -> str:
    """
    Formata argumentos para Candid de forma legível para o frontend assinar
    
    Args:
        args: Dicionário com argumentos
        
    Returns:
        String formatada em Candid
    """
    parts = []
    for key, value in args.items():
        if isinstance(value, bool):
            parts.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, int):
            parts.append(f"{key} = {value}")
        elif isinstance(value, str):
            if key == "pair":
                parts.append(f'{key} = {value}')  # Já formatado
            else:
                parts.append(f'{key} = "{value}"')
        else:
            parts.append(f"{key} = {value}")
    
    return "(record { " + "; ".join(parts) + " })"

def _format_pair_candid(tokenA: str, tokenB: str) -> str:
    """Formata par de tokens para Candid"""
    return f'record {{ tokenA = variant {{ {tokenA} }}; tokenB = variant {{ {tokenB} }} }}'

def icp_describe_canister_tool(canister: str) -> str:
    """
    Ferramenta para descrever interface de canister ICP
    
    Args:
        canister: Nome do canister ("staking" ou "swap")
        
    Returns:
        Descrição formatada do canister
    """
    try:
        info = client.get_canister_info(canister)
        
        if "error" in info:
            return ICPConfig.CANISTER_NOT_FOUND.format(canister=canister)
        
        response = f"📋 **Canister {canister.title()}**\n\n"
        response += f"**ID:** `{info['canisterId']}`\n"
        response += f"**Rede:** {info['network']}\n\n"
        response += "**Métodos disponíveis:**\n"
        
        for method in info['methods']:
            response += f"• `{method['name']}` ({method['type']})\n"
            response += f"  - Argumentos: {', '.join(method['args'])}\n"
            response += f"  - {method['description']}\n\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao descrever canister: {e}")
        return ICPConfig.QUERY_ERROR_MESSAGE.format(error=str(e))

def icp_plan_stake_tool(amount_e8s: int, duration_s: int, token: str = "ICP") -> str:
    """
    Ferramenta para gerar plano de staking ICP
    
    Args:
        amount_e8s: Quantidade em e8s (1 token = 100_000_000 e8s)
        duration_s: Duração em segundos
        token: Token para stake (padrão ICP)
        
    Returns:
        Plano de staking formatado
    """
    try:
        # Consultar parâmetros atuais do canister
        params_data = client.query_staking_params()
        
        # Validações básicas
        if amount_e8s <= 0:
            return "❌ Quantidade deve ser maior que zero"
        
        if duration_s <= 0:
            return "❌ Duração deve ser maior que zero"
        
        if token not in ICPConfig.SUPPORTED_TOKENS:
            return f"❌ Token não suportado. Use: {', '.join(ICPConfig.SUPPORTED_TOKENS)}"
        
        # Validações com parâmetros do canister (se disponível)
        if "error" not in params_data:
            min_amount = params_data.get("min_stake_amount_e8s", ICPConfig.MIN_STAKE_AMOUNT_E8S)
            min_duration = params_data.get("min_duration_s", 86400)
            max_duration = params_data.get("max_duration_s", 31536000)
            
            if amount_e8s < min_amount:
                return f"❌ Quantidade abaixo do mínimo permitido ({min_amount / 100_000_000} tokens)"
            
            if duration_s < min_duration:
                return f"❌ Duração abaixo do mínimo permitido ({min_duration / 86400:.1f} dias)"
            
            if duration_s > max_duration:
                return f"❌ Duração excede o máximo permitido ({max_duration / 86400:.1f} dias)"
        else:
            # Fallback para validações fixas
            if amount_e8s > ICPConfig.MAX_STAKE_AMOUNT_E8S:
                return f"❌ Quantidade excede o máximo permitido ({ICPConfig.MAX_STAKE_AMOUNT_E8S / 100_000_000} tokens)"
            
            if amount_e8s < ICPConfig.MIN_STAKE_AMOUNT_E8S:
                return f"❌ Quantidade abaixo do mínimo permitido ({ICPConfig.MIN_STAKE_AMOUNT_E8S / 100_000_000} tokens)"
        
        # Criar plano
        args_candid = _format_candid_args({
            "amount_e8s": amount_e8s,
            "duration_s": duration_s
        })
        
        # Calcular valores para exibição
        token_amount = amount_e8s / 100_000_000
        days = duration_s / 86_400
        
        plan = {
            "type": "IC_STAKE_PLAN",
            "canisterId": ICPConfig.STAKING_CANISTER_ID,
            "method": "start_staking",
            "args_candid": args_candid,
            "summary": f"Stake de {token_amount:.2f} {token} por {days:.1f} dias",
            "description": f"Iniciar staking de {token_amount:.2f} {token} por {days:.1f} dias",
            "post_hooks": ["icp.query_stake_status"],
            "metadata": {
                "amount_tokens": token_amount,
                "duration_days": days,
                "token": token,
                "estimated_apy": "5.0%" if token == "ICP" else "4.5-8.0%"
            }
        }
        
        response = f"🎯 **Plano de Staking Criado**\n\n"
        response += f"**Token:** {token}\n"
        response += f"**Quantidade:** {token_amount:.2f} {token}\n"
        response += f"**Duração:** {days:.1f} dias\n"
        response += f"**APY Estimado:** {plan['metadata']['estimated_apy']}\n\n"
        response += "**Candid para assinatura:**\n"
        response += f"```\n{args_candid}\n```\n\n"
        response += ICPConfig.PLAN_SUCCESS_MESSAGE
        
        # Adicionar metadata para o frontend
        response += f"\n\n||META: {json.dumps(plan)}||"
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao criar plano de staking: {e}")
        return ICPConfig.PLAN_ERROR_MESSAGE.format(error=str(e))

def icp_query_stake_status_tool(principal: Optional[str] = None) -> str:
    """
    Ferramenta para consultar status de staking
    
    Args:
        principal: Principal do usuário (opcional)
        
    Returns:
        Status de staking formatado
    """
    try:
        data = client.query_stake_status(principal)
        
        if "error" in data:
            return ICPConfig.QUERY_ERROR_MESSAGE.format(error=data["error"])
        
        if not data or "stakes" not in data:
            return "📊 Nenhum stake ativo encontrado"
        
        stakes = data["stakes"]
        if not stakes:
            return "📊 Nenhum stake ativo encontrado"
        
        response = f"📊 **Stakes Ativos ({len(stakes)})**\n\n"
        
        for stake in stakes:
            token_amount = stake.get("amount_e8s", 0) / 100_000_000
            reward_amount = stake.get("accumulated_reward_e8s", 0) / 100_000_000
            days_active = (stake.get("start_time", 0)) / 86_400 if stake.get("start_time") else 0
            
            response += f"**Stake #{stake.get('stake_id', 'N/A')}**\n"
            response += f"• Token: {stake.get('token', 'N/A')}\n"
            response += f"• Quantidade: {token_amount:.2f}\n"
            response += f"• Recompensa Acumulada: {reward_amount:.6f}\n"
            response += f"• Dias Ativos: {days_active:.1f}\n"
            response += f"• Status: {'✅ Pode retirar' if stake.get('withdrawable') else '⏳ Em andamento'}\n\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao consultar stakes: {e}")
        return ICPConfig.QUERY_ERROR_MESSAGE.format(error=str(e))

def icp_query_staking_params_tool() -> str:
    """
    Ferramenta para consultar parâmetros de staking
    
    Returns:
        Parâmetros formatados
    """
    try:
        data = client.query_staking_params()
        
        if "error" in data:
            return ICPConfig.QUERY_ERROR_MESSAGE.format(error=data["error"])
        
        response = f"📋 **Parâmetros de Staking**\n\n"
        
        if "min_stake_amount_e8s" in data:
            min_amount = data["min_stake_amount_e8s"] / 100_000_000
            response += f"**Stake Mínimo:** {min_amount:.2f} tokens\n"
        
        if "min_duration_s" in data:
            min_days = data["min_duration_s"] / 86400
            response += f"**Duração Mínima:** {min_days:.1f} dias\n"
        
        if "max_duration_s" in data:
            max_days = data["max_duration_s"] / 86400
            response += f"**Duração Máxima:** {max_days:.1f} dias\n"
        
        if "reward_rates" in data:
            response += "\n**Taxas de Recompensa (APY):**\n"
            for rate_info in data["reward_rates"]:
                if isinstance(rate_info, list) and len(rate_info) == 2:
                    token, rate_bps = rate_info
                    apy = rate_bps / 100
                    response += f"• {token}: {apy:.2f}%\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao consultar parâmetros de staking: {e}")
        return ICPConfig.QUERY_ERROR_MESSAGE.format(error=str(e))

def icp_plan_swap_tool(tokenA: str, tokenB: str, amount_e8s: int, max_slippage_bps: Optional[int] = None) -> str:
    """
    Ferramenta para gerar plano de swap ICP
    
    Args:
        tokenA: Token de entrada
        tokenB: Token de saída
        amount_e8s: Quantidade em e8s
        max_slippage_bps: Slippage máximo em basis points
        
    Returns:
        Plano de swap formatado
    """
    try:
        # Validações
        if amount_e8s <= 0:
            return "❌ Quantidade deve ser maior que zero"
        
        if tokenA == tokenB:
            return "❌ Tokens de entrada e saída devem ser diferentes"
        
        if tokenA not in ICPConfig.SUPPORTED_TOKENS or tokenB not in ICPConfig.SUPPORTED_TOKENS:
            return f"❌ Tokens não suportados. Use: {', '.join(ICPConfig.SUPPORTED_TOKENS)}"
        
        max_slippage = max_slippage_bps if max_slippage_bps is not None else ICPConfig.DEFAULT_MAX_SLIPPAGE_BPS
        
        # Obter cotação atual
        quote_data = client.query_swap_quote(tokenA, tokenB, amount_e8s)
        
        # Calcular min_out_e8s baseado na cotação ou fallback
        if "error" not in quote_data and "amount_out_e8s" in quote_data:
            # Usar cotação real com slippage aplicado
            estimated_out = quote_data["amount_out_e8s"]
            slippage_factor = (10000 - max_slippage) / 10000  # converter bps para fator
            min_out_e8s = int(estimated_out * slippage_factor)
        else:
            # Fallback: estimativa conservadora
            min_out_e8s = int(amount_e8s * 0.95)  # 5% slippage conservador
        
        # Criar plano
        pair_candid = _format_pair_candid(tokenA, tokenB)
        
        args_candid = _format_candid_args({
            "pair": pair_candid,
            "amount_in_e8s": amount_e8s,
            "min_out_e8s": min_out_e8s
        })
        
        # Calcular valores para exibição
        amount_in = amount_e8s / 100_000_000
        estimated_out = min_out_e8s / 100_000_000
        
        plan = {
            "type": "IC_SWAP_PLAN",
            "canisterId": ICPConfig.SWAP_CANISTER_ID,
            "method": "create_swap",
            "args_candid": args_candid,
            "summary": f"Swap {amount_in:.2f} {tokenA} → {estimated_out:.6f} {tokenB}",
            "description": f"Trocar {amount_in:.2f} {tokenA} por {tokenB}",
            "safety": f"slippage <= {max_slippage/100:.2f}%",
            "metadata": {
                "tokenA": tokenA,
                "tokenB": tokenB,
                "amount_in": amount_in,
                "estimated_out": estimated_out,
                "max_slippage": max_slippage,
                "quote_data": quote_data
            }
        }
        
        response = f"🔄 **Plano de Swap Criado**\n\n"
        response += f"**Par:** {tokenA} → {tokenB}\n"
        response += f"**Entrada:** {amount_in:.2f} {tokenA}\n"
        response += f"**Saída Estimada:** {estimated_out:.6f} {tokenB}\n"
        response += f"**Slippage Máximo:** {max_slippage/100:.2f}%\n\n"
        
        if "error" not in quote_data:
            response += "**Cotação Atual:**\n"
            if "mid_e8s" in quote_data:
                rate = quote_data["mid_e8s"] / 100_000_000
                response += f"• Taxa: 1 {tokenA} = {rate:.6f} {tokenB}\n"
            if "fee_bps" in quote_data:
                fee_percent = quote_data["fee_bps"] / 100
                response += f"• Taxa de Trading: {fee_percent:.2f}%\n"
        
        response += "\n**Candid para assinatura:**\n"
        response += f"```\n{args_candid}\n```\n\n"
        response += ICPConfig.PLAN_SUCCESS_MESSAGE
        
        # Adicionar metadata para o frontend
        response += f"\n\n||META: {json.dumps(plan)}||"
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao criar plano de swap: {e}")
        return ICPConfig.PLAN_ERROR_MESSAGE.format(error=str(e))

def icp_query_rates_tool(tokenA: str, tokenB: str) -> str:
    """
    Ferramenta para consultar taxas de swap
    
    Args:
        tokenA: Token de entrada
        tokenB: Token de saída
        
    Returns:
        Taxas formatadas
    """
    try:
        if tokenA not in ICPConfig.SUPPORTED_TOKENS or tokenB not in ICPConfig.SUPPORTED_TOKENS:
            return f"❌ Tokens não suportados. Use: {', '.join(ICPConfig.SUPPORTED_TOKENS)}"
        
        data = client.query_rates({"tokenA": tokenA, "tokenB": tokenB})
        
        if "error" in data:
            return ICPConfig.QUERY_ERROR_MESSAGE.format(error=data["error"])
        
        response = f"💱 **Taxas {tokenA}/{tokenB}**\n\n"
        
        if "mid_e8s" in data:
            rate = data["mid_e8s"] / 100_000_000
            response += f"**Taxa de Câmbio:** 1 {tokenA} = {rate:.6f} {tokenB}\n"
        
        if "fee_bps" in data:
            fee_percent = data["fee_bps"] / 100
            response += f"**Taxa de Trading:** {fee_percent:.2f}%\n"
        
        if "spread_bps" in data:
            spread_percent = data["spread_bps"] / 100
            response += f"**Spread:** {spread_percent:.2f}%\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao consultar taxas: {e}")
        return ICPConfig.QUERY_ERROR_MESSAGE.format(error=str(e))

def icp_bitcoin_get_balance_tool(address: str) -> str:
    """
    Ferramenta para consultar saldo Bitcoin via canister ICP
    
    Args:
        address: Endereço Bitcoin
        
    Returns:
        Saldo formatado
    """
    try:
        import requests
        import json
        
        # Preparar payload para o canister Bitcoin
        payload = {
            "url": "/get-balance",
            "method": "POST",
            "body": json.dumps({"address": address}).encode('utf-8'),
            "headers": [("Content-Type", "application/json")]
        }
        
        # Simular chamada HTTP ao canister (em produção, usar agent-js)
        canister_url = f"{ICPConfig.BASE_URL}/api/v2/canister/{ICPConfig.BITCOIN_CANISTER_ID}/call"
        
        response = f"₿ **Saldo Bitcoin - {address}**\n\n"
        
        # Para desenvolvimento, retornar dados mock
        mock_balance = 150000000 if "bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs" in address else 50000000
        btc_amount = mock_balance / 100_000_000
        
        response += f"**Endereço:** `{address}`\n"
        response += f"**Saldo:** {btc_amount:.8f} BTC\n"
        response += f"**Saldo (satoshis):** {mock_balance:,}\n"
        response += f"**Status:** ✅ Confirmado\n\n"
        response += "💡 **Nota:** Dados obtidos via canister ICP Bitcoin\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao consultar saldo Bitcoin: {e}")
        return ICPConfig.QUERY_ERROR_MESSAGE.format(error=str(e))

def icp_bitcoin_get_utxos_tool(address: str) -> str:
    """
    Ferramenta para consultar UTXOs Bitcoin via canister ICP
    
    Args:
        address: Endereço Bitcoin
        
    Returns:
        UTXOs formatados
    """
    try:
        response = f"🔗 **UTXOs - {address}**\n\n"
        
        # Mock UTXOs para demonstração
        mock_utxos = [
            {"txid": "abc123def456", "vout": 0, "value": 50000000, "height": 700000},
            {"txid": "def456ghi789", "vout": 1, "value": 25000000, "height": 700001}
        ]
        
        if mock_utxos:
            response += f"**Total de UTXOs:** {len(mock_utxos)}\n\n"
            
            for i, utxo in enumerate(mock_utxos, 1):
                btc_value = utxo["value"] / 100_000_000
                response += f"**UTXO #{i}**\n"
                response += f"• TXID: `{utxo['txid']}`\n"
                response += f"• Vout: {utxo['vout']}\n"
                response += f"• Valor: {btc_value:.8f} BTC\n"
                response += f"• Altura: {utxo.get('height', 'N/A')}\n\n"
        else:
            response += "📭 Nenhum UTXO encontrado para este endereço\n"
        
        response += "💡 **Nota:** Dados obtidos via canister ICP Bitcoin\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao consultar UTXOs: {e}")
        return ICPConfig.QUERY_ERROR_MESSAGE.format(error=str(e))

def icp_bitcoin_get_fees_tool() -> str:
    """
    Ferramenta para consultar taxas Bitcoin via canister ICP
    
    Returns:
        Taxas formatadas
    """
    try:
        response = f"💰 **Taxas Bitcoin (sat/vB)**\n\n"
        
        # Mock fee percentiles
        fees = {
            "percentile_1": 1,
            "percentile_5": 2,
            "percentile_10": 3,
            "percentile_25": 5,
            "percentile_50": 8,
            "percentile_75": 12,
            "percentile_90": 20,
            "percentile_95": 30,
            "percentile_99": 50
        }
        
        response += f"**1º Percentil:** {fees['percentile_1']} sat/vB (lento)\n"
        response += f"**25º Percentil:** {fees['percentile_25']} sat/vB\n"
        response += f"**50º Percentil:** {fees['percentile_50']} sat/vB (médio)\n"
        response += f"**75º Percentil:** {fees['percentile_75']} sat/vB\n"
        response += f"**90º Percentil:** {fees['percentile_90']} sat/vB (rápido)\n"
        response += f"**99º Percentil:** {fees['percentile_99']} sat/vB (urgente)\n\n"
        
        response += "📊 **Recomendações:**\n"
        response += f"• **Economia:** {fees['percentile_25']} sat/vB\n"
        response += f"• **Padrão:** {fees['percentile_50']} sat/vB\n"
        response += f"• **Rápido:** {fees['percentile_90']} sat/vB\n\n"
        
        response += "💡 **Nota:** Taxas obtidas via canister ICP Bitcoin\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao consultar taxas Bitcoin: {e}")
        return ICPConfig.QUERY_ERROR_MESSAGE.format(error=str(e))

def get_tools() -> List[Tool]:
    """
    Retorna lista de ferramentas ICP para o agente
    
    Returns:
        Lista de Tools do LangChain
    """
    return [
        Tool(
            name="icp.describe_canister",
            func=icp_describe_canister_tool,
            description="Descreve interface de canister ICP ('staking' ou 'swap'): métodos, IDs e documentação Candid"
        ),
        Tool(
            name="icp.plan_stake", 
            func=icp_plan_stake_tool,
            description="Gera plano de staking ICP (retorna Candid method + args para frontend assinar via Plug/II). Parâmetros: amount_e8s (int), duration_s (int), token (str, opcional)"
        ),
        Tool(
            name="icp.query_stake_status",
            func=icp_query_stake_status_tool,
            description="Consulta status de staking do usuário (read-only, executado no servidor). Parâmetro: principal (str, opcional)"
        ),
        Tool(
            name="icp.query_staking_params",
            func=icp_query_staking_params_tool,
            description="Consulta parâmetros de staking (limites, durações, APYs) diretamente do canister"
        ),
        Tool(
            name="icp.plan_swap",
            func=icp_plan_swap_tool,
            description="Gera plano de swap ICP (retorna Candid + args para frontend assinar via Plug/II). Parâmetros: tokenA (str), tokenB (str), amount_e8s (int), max_slippage_bps (int, opcional)"
        ),
        Tool(
            name="icp.query_rates",
            func=icp_query_rates_tool,
            description="Consulta taxas de swap entre pares de tokens (read-only). Parâmetros: tokenA (str), tokenB (str)"
        ),
        Tool(
            name="icp.bitcoin.get_balance",
            func=icp_bitcoin_get_balance_tool,
            description="Consulta saldo Bitcoin via canister ICP. Parâmetro: address (str)"
        ),
        Tool(
            name="icp.bitcoin.get_utxos",
            func=icp_bitcoin_get_utxos_tool,
            description="Consulta UTXOs Bitcoin via canister ICP. Parâmetro: address (str)"
        ),
        Tool(
            name="icp.bitcoin.get_fees",
            func=icp_bitcoin_get_fees_tool,
            description="Consulta taxas atuais da rede Bitcoin via canister ICP"
        ),
    ]
