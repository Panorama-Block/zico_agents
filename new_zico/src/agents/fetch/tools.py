from typing import Any, Dict, List, Optional
from langchain_core.tools import Tool
from .config import FetchConfig
from . import client
import json
import logging

logger = logging.getLogger(__name__)

def fetch_advice_trade_timing_tool(asset: str, pair: str = "", horizon: str = "intra", window: str = "30d") -> str:
    """
    Ferramenta para análise de timing de trading via Fetch.ai
    
    Args:
        asset: Asset principal (ex: "AVAX", "ICP", "BTC")
        pair: Par completo (ex: "AVAX/USDT", "ICP/ckBTC") 
        horizon: Horizonte temporal ("intra", "swing", "pos")
        window: Janela de análise (ex: "30d", "7d", "1h")
        
    Returns:
        Análise de timing formatada
    """
    try:
        if asset.upper() not in FetchConfig.SUPPORTED_ASSETS:
            return f"❌ Asset não suportado: {asset}. Use: {', '.join(FetchConfig.SUPPORTED_ASSETS)}"
        
        payload = {
            "asset": asset.upper(),
            "pair": pair.upper() if pair else f"{asset.upper()}/USD",
            "horizon": horizon.lower(),
            "window": window.lower()
        }
        
        response = client.advice_timing(payload)
        
        if "error" in response:
            if FetchConfig.ENABLE_FALLBACK_RESPONSES:
                logger.warning(f"API indisponível, usando fallback para timing: {response['error']}")
                response = client.generate_fallback_timing_response(asset, horizon)
            else:
                return FetchConfig.ADVISOR_ERROR_MESSAGE.format(error=response["error"])
        
        # Formatar resposta
        score = response.get("score", 0.5)
        regime = response.get("regime", "normal")
        rationale = response.get("rationale", "Análise não disponível")
        cooldown = response.get("cooldown_minutes", 60)
        
        # Interpretar score
        timing_assessment = "⚠️ Evitar" if score < 0.3 else "✅ Favorável" if score > 0.7 else "🔄 Neutro"
        
        result = f"⏰ **Análise de Timing - {asset.upper()}**\n\n"
        result += f"**Assessment:** {timing_assessment} (Score: {score:.2f})\n"
        result += f"**Regime:** {regime.replace('_', ' ').title()}\n"
        result += f"**Horizonte:** {horizon.title()}\n"
        result += f"**Período:** {window}\n\n"
        result += f"**Análise:** {rationale}\n\n"
        
        if cooldown > 0:
            hours = cooldown / 60
            if hours >= 1:
                result += f"⏱️ **Cooldown sugerido:** {hours:.1f}h\n"
            else:
                result += f"⏱️ **Cooldown sugerido:** {cooldown}min\n"
        
        # Adicionar recomendações baseadas no score
        if score < 0.3:
            result += "\n💡 **Recomendação:** Aguardar condições mais favoráveis antes de entrar em posições"
        elif score > 0.7:
            result += "\n💡 **Recomendação:** Momento favorável para considerar novas posições"
        else:
            result += "\n💡 **Recomendação:** Momento neutro, proceder com cautela normal"
        
        return result
        
    except Exception as e:
        logger.error(f"Erro na análise de timing: {e}")
        return FetchConfig.ADVISOR_ERROR_MESSAGE.format(error=str(e))

def fetch_advice_position_size_tool(portfolio_value: float, risk_pct: float, vol_lookback_days: int = 30, unit: str = "AVAX") -> str:
    """
    Ferramenta para recomendação de tamanho de posição via Fetch.ai
    
    Args:
        portfolio_value: Valor total do portfólio
        risk_pct: Percentual de risco (ex: 0.01 = 1%)
        vol_lookback_days: Dias para cálculo de volatilidade
        unit: Unidade do asset
        
    Returns:
        Recomendação de posição formatada
    """
    try:
        if portfolio_value <= 0:
            return "❌ Valor do portfólio deve ser maior que zero"
        
        if risk_pct <= 0 or risk_pct > 1:
            return "❌ Percentual de risco deve estar entre 0 e 1 (ex: 0.01 = 1%)"
        
        if unit.upper() not in FetchConfig.SUPPORTED_ASSETS:
            return f"❌ Asset não suportado: {unit}. Use: {', '.join(FetchConfig.SUPPORTED_ASSETS)}"
        
        payload = {
            "portfolio_value": portfolio_value,
            "risk_pct": risk_pct,
            "vol_lookback_days": vol_lookback_days,
            "unit": unit.upper()
        }
        
        response = client.advice_sizing(payload)
        
        if "error" in response:
            if FetchConfig.ENABLE_FALLBACK_RESPONSES:
                logger.warning(f"API indisponível, usando fallback para sizing: {response['error']}")
                response = client.generate_fallback_sizing_response(portfolio_value, risk_pct, unit)
            else:
                return FetchConfig.ADVISOR_ERROR_MESSAGE.format(error=response["error"])
        
        # Extrair dados da resposta
        size_quote = response.get("size_quote", 0)
        unit_response = response.get("unit", unit)
        stop_hint = response.get("stop_hint", "-3%")
        rationale = response.get("rationale", "Cálculo baseado em volatilidade histórica")
        
        # Calcular valores
        risk_amount = portfolio_value * risk_pct
        position_value = size_quote * (portfolio_value / 1000)  # Estimativa
        
        result = f"📊 **Recomendação de Posição - {unit_response}**\n\n"
        result += f"**Portfólio:** ${portfolio_value:,.2f}\n"
        result += f"**Risco por trade:** {risk_pct*100:.2f}% (${risk_amount:,.2f})\n"
        result += f"**Lookback:** {vol_lookback_days} dias\n\n"
        result += f"**Tamanho sugerido:** {size_quote:.2f} {unit_response}\n"
        result += f"**Stop sugerido:** {stop_hint}\n\n"
        result += f"**Metodologia:** {rationale}\n\n"
        
        # Adicionar alertas baseados no tamanho
        if size_quote * 100 > portfolio_value:  # Posição muito grande
            result += "⚠️ **Alerta:** Posição pode ser muito grande para o portfólio. Considere reduzir.\n"
        elif size_quote <= 0:
            result += "⚠️ **Alerta:** Condições atuais não favorecem posicionamento.\n"
        else:
            result += "✅ **Status:** Tamanho de posição dentro de parâmetros aceitáveis.\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Erro na recomendação de posição: {e}")
        return FetchConfig.ADVISOR_ERROR_MESSAGE.format(error=str(e))

def fetch_advice_fee_slip_tool(chain: str, pair: str, amount_in: int, side: str = "sell") -> str:
    """
    Ferramenta para análise de fees e slippage via Fetch.ai
    
    Args:
        chain: Blockchain ("icp", "avalanche", "ethereum", "bitcoin")
        pair: Par de trading (ex: "ICP/ckBTC", "AVAX/USDC")
        amount_in: Quantidade de entrada em unidades menores (e8s para ICP)
        side: Lado da operação ("buy" ou "sell")
        
    Returns:
        Análise de fees e slippage formatada
    """
    try:
        if chain.lower() not in FetchConfig.SUPPORTED_CHAINS:
            return f"❌ Chain não suportada: {chain}. Use: {', '.join(FetchConfig.SUPPORTED_CHAINS)}"
        
        if amount_in <= 0:
            return "❌ Quantidade deve ser maior que zero"
        
        payload = {
            "chain": chain.lower(),
            "pair": pair.upper(),
            "amount_in": amount_in,
            "side": side.lower()
        }
        
        response = client.advice_feeslip(payload)
        
        if "error" in response:
            if FetchConfig.ENABLE_FALLBACK_RESPONSES:
                logger.warning(f"API indisponível, usando fallback para fees: {response['error']}")
                response = client.generate_fallback_feeslip_response(chain, amount_in)
            else:
                return FetchConfig.ADVISOR_ERROR_MESSAGE.format(error=response["error"])
        
        # Extrair dados
        fee_bps = response.get("fee_bps", 30)
        slippage_bps = response.get("est_slippage_bps", 20)
        min_out = response.get("min_out", amount_in * 0.98)
        route = response.get("route", ["direct"])
        
        # Converter para percentuais
        fee_percent = fee_bps / 100
        slippage_percent = slippage_bps / 100
        total_cost_percent = fee_percent + slippage_percent
        
        # Calcular valores
        fee_amount = (amount_in * fee_bps) / 10000
        expected_slippage = (amount_in * slippage_bps) / 10000
        total_cost = fee_amount + expected_slippage
        
        result = f"💰 **Análise de Custos - {pair} ({chain.title()})**\n\n"
        result += f"**Operação:** {side.title()} {amount_in:,} unidades\n"
        result += f"**Rota:** {' → '.join(route)}\n\n"
        result += f"**Taxa de Trading:** {fee_percent:.2f}% ({fee_amount:,.0f} unidades)\n"
        result += f"**Slippage Estimado:** {slippage_percent:.2f}% ({expected_slippage:,.0f} unidades)\n"
        result += f"**Custo Total:** {total_cost_percent:.2f}% ({total_cost:,.0f} unidades)\n\n"
        result += f"**Mínimo Esperado:** {min_out:,} unidades\n\n"
        
        # Adicionar alertas baseados nos custos
        if total_cost_percent > 2.0:
            result += "🔴 **Alerta:** Custos altos! Considere aguardar melhor liquidez.\n"
        elif total_cost_percent > 1.0:
            result += "🟡 **Cuidado:** Custos elevados. Avalie se a operação vale a pena.\n"
        else:
            result += "🟢 **OK:** Custos dentro do esperado para esta chain.\n"
        
        # Recomendações específicas por chain
        if chain.lower() == "icp":
            result += "\n💡 **Dica ICP:** Considere usar canisters nativos para menores custos.\n"
        elif chain.lower() == "avalanche":
            result += "\n💡 **Dica AVAX:** Aproveite as baixas taxas da rede Avalanche.\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Erro na análise de fees: {e}")
        return FetchConfig.ADVISOR_ERROR_MESSAGE.format(error=str(e))

def fetch_query_metrics_tool(chain: str, signals: List[str], window: str = "7d") -> str:
    """
    Ferramenta para consulta de métricas de rede via Fetch.ai
    
    Args:
        chain: Blockchain para análise
        signals: Lista de sinais ["tps", "fees", "whales", "volume"]
        window: Janela temporal ("7d", "30d", "1h")
        
    Returns:
        Métricas de rede formatadas
    """
    try:
        if chain.lower() not in FetchConfig.SUPPORTED_CHAINS:
            return f"❌ Chain não suportada: {chain}. Use: {', '.join(FetchConfig.SUPPORTED_CHAINS)}"
        
        if not signals:
            signals = ["tps", "fees", "whales"]
        
        payload = {
            "chain": chain.lower(),
            "signals": signals,
            "window": window.lower()
        }
        
        response = client.query_metrics(payload)
        
        if "error" in response:
            if FetchConfig.ENABLE_FALLBACK_RESPONSES:
                logger.warning(f"API indisponível, usando fallback para métricas: {response['error']}")
                response = client.generate_fallback_metrics_response(chain, signals)
            else:
                return FetchConfig.ADVISOR_ERROR_MESSAGE.format(error=response["error"])
        
        # Extrair dados
        series = response.get("series", {})
        anomalies = response.get("anomalies", [])
        status = response.get("status", "live")
        
        result = f"📈 **Métricas de Rede - {chain.title()}**\n\n"
        result += f"**Período:** {window}\n"
        result += f"**Status:** {'🔴 Dados de fallback' if status == 'fallback_data' else '🟢 Dados ao vivo'}\n\n"
        
        # Processar séries de dados
        for signal, data in series.items():
            if not data:
                continue
                
            avg_value = sum(data) / len(data) if data else 0
            latest_value = data[-1] if data else 0
            
            if signal == "tps":
                result += f"**Transações/seg:** {latest_value} (média: {avg_value:.1f})\n"
            elif signal == "fees":
                result += f"**Taxas médias:** ${latest_value:.2f} (média: ${avg_value:.2f})\n"
            elif signal == "whales":
                result += f"**Atividade de whales:** {latest_value} (média: {avg_value:.1f})\n"
            elif signal == "volume":
                result += f"**Volume 24h:** ${latest_value:,.0f} (média: ${avg_value:,.0f})\n"
        
        # Processar anomalias
        if anomalies:
            result += "\n🔍 **Anomalias Detectadas:**\n"
            for anomaly in anomalies[:3]:  # Mostrar apenas as 3 mais recentes
                when = anomaly.get("when", "N/A")
                signal = anomaly.get("signal", "N/A")
                severity = anomaly.get("severity", "low")
                
                severity_emoji = {"low": "🟡", "medium": "🟠", "high": "🔴"}.get(severity, "⚪")
                result += f"• {severity_emoji} {when}: {signal} ({severity})\n"
        
        # Análise geral da rede
        result += "\n📊 **Análise Geral:**\n"
        
        if chain.lower() == "icp":
            result += "• Internet Computer mantém alta eficiência energética\n"
            result += "• Canisters processam transações de forma determinística\n"
        elif chain.lower() == "avalanche":
            result += "• Rede Avalanche com consenso rápido e finalidade instantânea\n"
            result += "• Subnets permitem escalabilidade customizada\n"
        
        # Recomendações baseadas nas métricas
        if any("tps" in series and series["tps"] and max(series["tps"]) > 100 for _ in [True]):
            result += "\n✅ **Recomendação:** Rede com boa capacidade de processamento\n"
        
        if anomalies and len(anomalies) > 2:
            result += "\n⚠️ **Atenção:** Múltiplas anomalias detectadas, proceder com cautela\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Erro na consulta de métricas: {e}")
        return FetchConfig.ADVISOR_ERROR_MESSAGE.format(error=str(e))

def get_tools() -> List[Tool]:
    """
    Retorna lista de ferramentas Fetch.ai para o agente
    
    Returns:
        Lista de Tools do LangChain
    """
    return [
        Tool(
            name="fetch.advice.trade_timing",
            func=fetch_advice_trade_timing_tool,
            description="Análise de timing para trading via Fetch.ai. Parâmetros: asset (str), pair (str, opcional), horizon ('intra'|'swing'|'pos'), window (str, ex: '30d')"
        ),
        Tool(
            name="fetch.advice.position_size",
            func=fetch_advice_position_size_tool, 
            description="Recomendação de tamanho de posição via Fetch.ai. Parâmetros: portfolio_value (float), risk_pct (float, ex: 0.01), vol_lookback_days (int), unit (str)"
        ),
        Tool(
            name="fetch.advice.fee_slip",
            func=fetch_advice_fee_slip_tool,
            description="Análise de fees e slippage via Fetch.ai. Parâmetros: chain (str), pair (str), amount_in (int), side ('buy'|'sell')"
        ),
        Tool(
            name="fetch.query.metrics",
            func=fetch_query_metrics_tool,
            description="Consulta métricas de rede via Fetch.ai. Parâmetros: chain (str), signals (list de str, ex: ['tps','fees','whales']), window (str, ex: '7d')"
        ),
    ]
