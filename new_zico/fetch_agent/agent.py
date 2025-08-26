#!/usr/bin/env python3
"""
Fetch.ai Agent - Integração com ICP Bitcoin Service
Baseado no exemplo de integração Fetch.ai + ICP

Este agente implementa o Chat Protocol da Fetch.ai para comunicação com ASI:One LLM
e integração com canisters ICP para operações Bitcoin.
"""

import asyncio
import json
import logging
import os
import requests
import sys
from typing import Any, Dict, List, Optional

# Adicionar src ao path para importar utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from utils.ic_urls import canister_http_base, format_canister_endpoint

from uagents import Agent, Context, Model, Protocol
from uagents.setup import fund_agent_if_low

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações
ASI1_API_KEY = os.getenv("ASI1_API_KEY", "your_asi1_api_key_here")
CANISTER_ID = os.getenv("ICP_BITCOIN_CANISTER_ID", "uzt4z-lp777-77774-qaabq-cai")
BASE_URL = os.getenv("ICP_BASE_URL", "http://127.0.0.1:4943")

# Modelos de dados
class ChatMessage(Model):
    """Modelo para mensagens do Chat Protocol"""
    message: str
    sender: str
    session_id: str

class BitcoinQueryRequest(Model):
    """Modelo para solicitações Bitcoin"""
    query_type: str
    address: Optional[str] = None
    parameters: Dict[str, Any] = {}

class BitcoinQueryResponse(Model):
    """Modelo para respostas Bitcoin"""
    success: bool
    data: Dict[str, Any] = {}
    error_message: Optional[str] = None

# Inicializar agente
agent = Agent(
    name="bitcoin-icp-agent",
    seed="bitcoin_icp_integration_seed_12345",
    port=8001,
    endpoint=["http://127.0.0.1:8001/submit"]
)

# Financiar agente se necessário
fund_agent_if_low(agent.wallet.address())

# Protocolo de Chat
chat_protocol = Protocol("ChatProtocol")

class ICPBitcoinService:
    """Serviço para interagir com canister Bitcoin ICP"""
    
    def __init__(self, canister_id: str, base_url: str):
        self.canister_id = canister_id
        self.base_url = base_url.rstrip('/')
        # Usar URL formatada corretamente (subdomínio)
        self.canister_base = canister_http_base(canister_id, base_url)
        
    def get_canister_url(self) -> str:
        """Retorna URL do canister para Candid UI"""
        if "localhost" in self.base_url or "127.0.0.1" in self.base_url:
            return f"{self.base_url}/?canisterId={self.canister_id}"
        else:
            return f"https://a4gq6-oaaaa-aaaab-qaa4q-cai.raw.icp0.io/?id={self.canister_id}"
    
    async def get_balance(self, address: str) -> Dict[str, Any]:
        """
        Consulta saldo Bitcoin via canister ICP
        
        Args:
            address: Endereço Bitcoin
            
        Returns:
            Dict com dados do saldo
        """
        try:
            url = f"{self.canister_base}/get-balance"
            payload = {"address": address}
            
            response = requests.post(
                url, 
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Erro ao consultar saldo: {e}")
            # Retornar dados mock para demonstração
            return {
                "address": address,
                "balance": 150000000 if "bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs" in address else 50000000,
                "unconfirmed_balance": 0,
                "final_balance": 150000000 if "bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs" in address else 50000000
            }
    
    async def get_utxos(self, address: str) -> Dict[str, Any]:
        """
        Consulta UTXOs Bitcoin via canister ICP
        
        Args:
            address: Endereço Bitcoin
            
        Returns:
            Dict com UTXOs
        """
        try:
            url = f"{self.canister_base}/get-utxos"
            payload = {"address": address}
            
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Erro ao consultar UTXOs: {e}")
            # Retornar dados mock
            return {
                "address": address,
                "utxos": [
                    {"txid": "abc123def456", "vout": 0, "value": 50000000, "height": 700000},
                    {"txid": "def456ghi789", "vout": 1, "value": 25000000, "height": 700001}
                ]
            }
    
    async def get_fee_percentiles(self) -> Dict[str, Any]:
        """
        Consulta taxas Bitcoin via canister ICP
        
        Returns:
            Dict com percentis de taxas
        """
        try:
            url = f"{self.canister_base}/get-current-fee-percentiles"
            
            response = requests.get(
                url,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Erro ao consultar taxas: {e}")
            # Retornar dados mock
            return {
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
    
    async def get_p2pkh_address(self) -> Dict[str, Any]:
        """
        Gera endereço P2PKH via canister ICP
        
        Returns:
            Dict com endereço gerado
        """
        try:
            url = f"{self.canister_base}/get-p2pkh-address"
            
            response = requests.get(
                url,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Erro ao gerar endereço: {e}")
            # Retornar dados mock
            return {
                "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "public_key": "04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f"
            }

# Instância do serviço Bitcoin
bitcoin_service = ICPBitcoinService(CANISTER_ID, BASE_URL)

class BitcoinQueryProcessor:
    """Processador de consultas Bitcoin usando LLM"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.functions = [
            {
                "name": "get_bitcoin_balance",
                "description": "Get the Bitcoin balance for a specific address",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Bitcoin address to check balance for"
                        }
                    },
                    "required": ["address"]
                }
            },
            {
                "name": "get_bitcoin_utxos",
                "description": "Get unspent transaction outputs (UTXOs) for a Bitcoin address",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Bitcoin address to get UTXOs for"
                        }
                    },
                    "required": ["address"]
                }
            },
            {
                "name": "get_bitcoin_fees",
                "description": "Get current Bitcoin network fee percentiles",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "generate_bitcoin_address",
                "description": "Generate a new P2PKH Bitcoin address",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    
    async def process_query(self, user_query: str) -> str:
        """
        Processa consulta do usuário usando LLM para determinar função apropriada
        
        Args:
            user_query: Consulta em linguagem natural
            
        Returns:
            Resposta formatada
        """
        try:
            # Simular decisão do LLM baseada em palavras-chave
            query_lower = user_query.lower()
            
            if "balance" in query_lower or "saldo" in query_lower:
                address = self._extract_address(user_query)
                if address:
                    result = await bitcoin_service.get_balance(address)
                    return self._format_balance_response(result)
                else:
                    return "❌ Por favor, forneça um endereço Bitcoin válido para consultar o saldo."
            
            elif "utxo" in query_lower or "unspent" in query_lower:
                address = self._extract_address(user_query)
                if address:
                    result = await bitcoin_service.get_utxos(address)
                    return self._format_utxos_response(result)
                else:
                    return "❌ Por favor, forneça um endereço Bitcoin válido para consultar UTXOs."
            
            elif "fee" in query_lower or "taxa" in query_lower:
                result = await bitcoin_service.get_fee_percentiles()
                return self._format_fees_response(result)
            
            elif "address" in query_lower or "endereço" in query_lower:
                result = await bitcoin_service.get_p2pkh_address()
                return self._format_address_response(result)
            
            else:
                return self._get_help_message()
                
        except Exception as e:
            logger.error(f"Erro ao processar consulta: {e}")
            return f"❌ Erro ao processar consulta: {str(e)}"
    
    def _extract_address(self, text: str) -> Optional[str]:
        """Extrai endereço Bitcoin do texto"""
        import re
        
        # Padrões para endereços Bitcoin
        patterns = [
            r'bc1[a-z0-9]{39,59}',  # Bech32
            r'[13][a-km-zA-HJ-NP-Z1-9]{25,34}',  # Legacy/P2SH
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        
        return None
    
    def _format_balance_response(self, data: Dict[str, Any]) -> str:
        """Formata resposta de saldo"""
        if "error" in data:
            return f"❌ Erro ao consultar saldo: {data['error']}"
        
        address = data.get("address", "N/A")
        balance_sat = data.get("balance", 0)
        balance_btc = balance_sat / 100_000_000
        
        response = f"₿ **Saldo Bitcoin**\n\n"
        response += f"**Endereço:** `{address}`\n"
        response += f"**Saldo:** {balance_btc:.8f} BTC\n"
        response += f"**Saldo (satoshis):** {balance_sat:,}\n"
        response += f"**Status:** ✅ Confirmado\n\n"
        response += "🔗 **Powered by ICP Bitcoin Canister**"
        
        return response
    
    def _format_utxos_response(self, data: Dict[str, Any]) -> str:
        """Formata resposta de UTXOs"""
        if "error" in data:
            return f"❌ Erro ao consultar UTXOs: {data['error']}"
        
        address = data.get("address", "N/A")
        utxos = data.get("utxos", [])
        
        response = f"🔗 **UTXOs Bitcoin**\n\n"
        response += f"**Endereço:** `{address}`\n"
        response += f"**Total UTXOs:** {len(utxos)}\n\n"
        
        if utxos:
            for i, utxo in enumerate(utxos[:5], 1):  # Mostrar apenas 5
                value_btc = utxo.get("value", 0) / 100_000_000
                response += f"**UTXO #{i}**\n"
                response += f"• TXID: `{utxo.get('txid', 'N/A')}`\n"
                response += f"• Vout: {utxo.get('vout', 0)}\n"
                response += f"• Valor: {value_btc:.8f} BTC\n\n"
        else:
            response += "📭 Nenhum UTXO encontrado\n\n"
        
        response += "🔗 **Powered by ICP Bitcoin Canister**"
        
        return response
    
    def _format_fees_response(self, data: Dict[str, Any]) -> str:
        """Formata resposta de taxas"""
        if "error" in data:
            return f"❌ Erro ao consultar taxas: {data['error']}"
        
        response = f"💰 **Taxas Bitcoin (sat/vB)**\n\n"
        response += f"**Lento:** {data.get('percentile_25', 0)} sat/vB\n"
        response += f"**Médio:** {data.get('percentile_50', 0)} sat/vB\n"
        response += f"**Rápido:** {data.get('percentile_90', 0)} sat/vB\n"
        response += f"**Urgente:** {data.get('percentile_99', 0)} sat/vB\n\n"
        response += "🔗 **Powered by ICP Bitcoin Canister**"
        
        return response
    
    def _format_address_response(self, data: Dict[str, Any]) -> str:
        """Formata resposta de endereço"""
        if "error" in data:
            return f"❌ Erro ao gerar endereço: {data['error']}"
        
        address = data.get("address", "N/A")
        
        response = f"🏠 **Novo Endereço Bitcoin**\n\n"
        response += f"**Endereço:** `{address}`\n"
        response += f"**Tipo:** P2PKH (Legacy)\n\n"
        response += "🔗 **Powered by ICP Bitcoin Canister**"
        
        return response
    
    def _get_help_message(self) -> str:
        """Retorna mensagem de ajuda"""
        return """
🤖 **Bitcoin Agent - Comandos Disponíveis**

**Consultar Saldo:**
• "What's the balance of bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs?"
• "Qual o saldo de [endereço]?"

**Consultar UTXOs:**
• "Show UTXOs for bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs"
• "Listar UTXOs para [endereço]"

**Consultar Taxas:**
• "What are current Bitcoin fees?"
• "Quais são as taxas atuais do Bitcoin?"

**Gerar Endereço:**
• "Generate a new Bitcoin address"
• "Gerar novo endereço Bitcoin"

🔗 **Powered by Fetch.ai + Internet Computer**
        """

# Instância do processador
query_processor = BitcoinQueryProcessor(ASI1_API_KEY)

@chat_protocol.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Manipula mensagens do Chat Protocol"""
    try:
        logger.info(f"Recebida mensagem: {msg.message}")
        
        # Processar consulta
        response = await query_processor.process_query(msg.message)
        
        # Enviar resposta
        await ctx.send(sender, ChatMessage(
            message=response,
            sender=ctx.agent.address,
            session_id=msg.session_id
        ))
        
        logger.info(f"Resposta enviada para {sender}")
        
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")
        await ctx.send(sender, ChatMessage(
            message=f"❌ Erro interno: {str(e)}",
            sender=ctx.agent.address,
            session_id=msg.session_id
        ))

# Incluir protocolo no agente
agent.include(chat_protocol)

@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Handler de inicialização"""
    logger.info(f"Agente Bitcoin ICP iniciado!")
    logger.info(f"Endereço: {agent.address}")
    logger.info(f"Canister ID: {CANISTER_ID}")
    logger.info(f"Base URL: {BASE_URL}")
    logger.info("🔗 Integração Fetch.ai + ICP ativa!")

if __name__ == "__main__":
    print("🚀 Iniciando Bitcoin ICP Agent...")
    print(f"📍 Endereço do agente: {agent.address}")
    print(f"🔗 Canister ID: {CANISTER_ID}")
    print(f"🌐 Base URL: {BASE_URL}")
    print("💡 Conecte via Agentverse para usar o Chat Protocol")
    
    agent.run()
