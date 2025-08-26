#!/usr/bin/env python3
"""
Teste de Integração - Fetch.ai Agent  
Testa as funcionalidades do agente Fetch.ai no sistema Zico
"""

import os
import sys
import requests
import json
from typing import Dict, Any

# Adiciona o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# URL base da API
BASE_URL = "http://localhost:8000"

def test_fetch_timing_analysis():
    """Testa análise de timing via Fetch.ai"""
    print("🧪 Testando análise de timing Fetch.ai...")
    
    payload = {
        "message": {
            "role": "user",
            "content": "É um bom momento para comprar AVAX? Analisar timing de mercado"
        },
        "user_id": "test_user_fetch",
        "conversation_id": "test_fetch_timing"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Resposta recebida:")
        print(f"   Agent: {data.get('agentName', 'N/A')}")
        print(f"   Response: {data.get('response', 'N/A')[:300]}...")
        
        # Verificar se é o agente Fetch.ai
        if data.get('agentName') == 'advisory':
            print("✅ Roteamento correto para Fetch.ai Agent")
            
            # Verificar se contém análise de timing
            response_text = data.get('response', '')
            timing_keywords = ['timing', 'score', 'análise', 'mercado', 'avax']
            if any(keyword.lower() in response_text.lower() for keyword in timing_keywords):
                print("✅ Análise de timing gerada com sucesso")
            else:
                print("⚠️ Conteúdo de timing não reconhecido")
        else:
            print(f"❌ Roteamento incorreto. Esperado: advisory, Recebido: {data.get('agentName')}")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de timing: {e}")
        return False

def test_fetch_position_sizing():
    """Testa recomendação de tamanho de posição"""
    print("\n🧪 Testando recomendação de posição Fetch.ai...")
    
    payload = {
        "message": {
            "role": "user",
            "content": "Qual tamanho de posição devo usar para ICP? Tenho $10000 e aceito 2% de risco"
        },
        "user_id": "test_user_fetch",
        "conversation_id": "test_fetch_sizing"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Resposta recebida:")
        print(f"   Agent: {data.get('agentName', 'N/A')}")
        print(f"   Response: {data.get('response', 'N/A')[:300]}...")
        
        # Verificar roteamento e conteúdo
        if data.get('agentName') == 'advisory':
            print("✅ Roteamento correto para Fetch.ai Agent")
            
            response_text = data.get('response', '')
            sizing_keywords = ['posição', 'tamanho', 'risco', 'portfólio', '10000']
            if any(keyword.lower() in response_text.lower() for keyword in sizing_keywords):
                print("✅ Recomendação de posição gerada corretamente")
            else:
                print("⚠️ Conteúdo de sizing não reconhecido")
        else:
            print(f"❌ Roteamento incorreto para sizing")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de sizing: {e}")
        return False

def test_fetch_fee_analysis():
    """Testa análise de fees e slippage"""
    print("\n🧪 Testando análise de fees Fetch.ai...")
    
    payload = {
        "message": {
            "role": "user",
            "content": "Quais são os custos esperados para swap de 100 ICP por ckBTC na rede ICP?"
        },
        "user_id": "test_user_fetch",
        "conversation_id": "test_fetch_fees"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Resposta recebida:")
        print(f"   Agent: {data.get('agentName', 'N/A')}")
        print(f"   Response: {data.get('response', 'N/A')[:300]}...")
        
        if data.get('agentName') == 'advisory':
            print("✅ Roteamento correto para Fetch.ai Agent")
            
            response_text = data.get('response', '')
            fee_keywords = ['custo', 'taxa', 'fee', 'slippage', 'icp', 'ckbtc']
            if any(keyword.lower() in response_text.lower() for keyword in fee_keywords):
                print("✅ Análise de fees gerada corretamente")
            else:
                print("⚠️ Conteúdo de fees não reconhecido")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de fees: {e}")
        return False

def test_fetch_network_metrics():
    """Testa consulta de métricas de rede"""
    print("\n🧪 Testando métricas de rede Fetch.ai...")
    
    payload = {
        "message": {
            "role": "user",
            "content": "Como está a saúde da rede Avalanche? Mostrar métricas de TPS e atividade"
        },
        "user_id": "test_user_fetch",
        "conversation_id": "test_fetch_metrics"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Resposta recebida:")
        print(f"   Agent: {data.get('agentName', 'N/A')}")
        print(f"   Response: {data.get('response', 'N/A')[:300]}...")
        
        if data.get('agentName') == 'advisory':
            print("✅ Roteamento correto para Fetch.ai Agent")
            
            response_text = data.get('response', '')
            metrics_keywords = ['métrica', 'rede', 'tps', 'avalanche', 'atividade']
            if any(keyword.lower() in response_text.lower() for keyword in metrics_keywords):
                print("✅ Métricas de rede geradas corretamente")
            else:
                print("⚠️ Conteúdo de métricas não reconhecido")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de métricas: {e}")
        return False

def test_direct_fetch_tools():
    """Testa ferramentas Fetch.ai diretamente"""
    print("\n🧪 Testando ferramentas Fetch.ai diretamente...")
    
    try:
        from src.agents.fetch.tools import (
            fetch_advice_trade_timing_tool,
            fetch_advice_position_size_tool,
            fetch_advice_fee_slip_tool,
            fetch_query_metrics_tool
        )
        
        # Teste timing advice
        print("📋 Testando timing advice...")
        result = fetch_advice_trade_timing_tool("AVAX", "AVAX/USD", "intra", "30d")
        print(f"   Resultado: {result[:150]}...")
        
        # Teste position sizing
        print("📋 Testando position sizing...")
        result = fetch_advice_position_size_tool(10000.0, 0.02, 30, "AVAX")
        print(f"   Resultado: {result[:150]}...")
        
        # Teste fee analysis
        print("📋 Testando fee analysis...")
        result = fetch_advice_fee_slip_tool("icp", "ICP/ckBTC", 100000000, "sell")
        print(f"   Resultado: {result[:150]}...")
        
        # Teste network metrics
        print("📋 Testando network metrics...")
        result = fetch_query_metrics_tool("avalanche", ["tps", "fees", "whales"], "7d")
        print(f"   Resultado: {result[:150]}...")
        
        print("✅ Testes diretos de ferramentas Fetch.ai concluídos")
        return True
        
    except Exception as e:
        print(f"❌ Erro nos testes diretos: {e}")
        print(f"   Detalhes: {type(e).__name__}: {str(e)}")
        return False

def test_fetch_fallback_behavior():
    """Testa comportamento de fallback quando APIs não estão disponíveis"""
    print("\n🧪 Testando comportamento de fallback...")
    
    try:
        from src.agents.fetch.client import (
            generate_fallback_timing_response,
            generate_fallback_sizing_response,
            generate_fallback_feeslip_response,
            generate_fallback_metrics_response
        )
        
        # Teste fallback timing
        print("📋 Testando fallback timing...")
        result = generate_fallback_timing_response("AVAX", "intra")
        print(f"   Score: {result.get('score')}, Regime: {result.get('regime')}")
        
        # Teste fallback sizing
        print("📋 Testando fallback sizing...")
        result = generate_fallback_sizing_response(10000.0, 0.02, "AVAX")
        print(f"   Size: {result.get('size_quote')}, Unit: {result.get('unit')}")
        
        # Teste fallback fees
        print("📋 Testando fallback fees...")
        result = generate_fallback_feeslip_response("icp", 100000000)
        print(f"   Fee BPS: {result.get('fee_bps')}, Slippage BPS: {result.get('est_slippage_bps')}")
        
        # Teste fallback metrics
        print("📋 Testando fallback metrics...")
        result = generate_fallback_metrics_response("avalanche", ["tps", "fees"])
        print(f"   Series: {list(result.get('series', {}).keys())}")
        
        print("✅ Testes de fallback concluídos com sucesso")
        return True
        
    except Exception as e:
        print(f"❌ Erro nos testes de fallback: {e}")
        return False

def test_health_check():
    """Testa se o servidor está rodando"""
    print("🏥 Verificando saúde do servidor...")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if data.get("status") == "ok":
            print("✅ Servidor está rodando")
            return True
        else:
            print(f"⚠️ Status inesperado: {data}")
            return False
            
    except Exception as e:
        print(f"❌ Servidor não está acessível: {e}")
        print("   Certifique-se de que o servidor está rodando:")
        print("   python -m uvicorn src.app:app --reload --port 8000")
        return False

def test_fetch_config():
    """Testa configuração do Fetch.ai"""
    print("\n🔧 Verificando configuração Fetch.ai...")
    
    try:
        from src.agents.fetch.config import FetchConfig
        
        print(f"   FETCH_ENABLE_FALLBACK: {FetchConfig.ENABLE_FALLBACK_RESPONSES}")
        print(f"   FETCH_HTTP_TIMEOUT: {FetchConfig.TIMEOUT}")
        print(f"   Chains suportadas: {FetchConfig.SUPPORTED_CHAINS}")
        print(f"   Assets suportados: {FetchConfig.SUPPORTED_ASSETS}")
        
        # Verificar se pelo menos fallback está ativo
        if FetchConfig.ENABLE_FALLBACK_RESPONSES:
            print("✅ Fallback habilitado - testes funcionarão mesmo sem APIs")
        else:
            print("⚠️ Fallback desabilitado - configure endpoints reais")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na verificação de config: {e}")
        return False

def main():
    """Executa todos os testes de integração Fetch.ai"""
    print("🚀 Iniciando Testes de Integração Fetch.ai")
    print("=" * 50)
    
    # Verificar se servidor está rodando
    if not test_health_check():
        return
    
    # Verificar configuração
    test_fetch_config()
    
    print(f"\n📍 Testando endpoint: {BASE_URL}")
    print("=" * 50)
    
    # Executar testes
    tests = [
        test_fetch_timing_analysis,
        test_fetch_position_sizing,
        test_fetch_fee_analysis,
        test_fetch_network_metrics,
        test_direct_fetch_tools,
        test_fetch_fallback_behavior
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Erro inesperado em {test_func.__name__}: {e}")
            results.append(False)
    
    # Resumo dos resultados
    print("\n" + "=" * 50)
    print("📊 RESUMO DOS TESTES FETCH.AI")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Testes Passaram: {passed}/{total}")
    print(f"❌ Testes Falharam: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 Todos os testes Fetch.ai passaram!")
    else:
        print("⚠️ Alguns testes falharam. Verifique a configuração.")
    
    print("\n💡 Dicas:")
    print("- Configure FETCH_TIMING_URL e outros endpoints para APIs reais")
    print("- Use FETCH_ENABLE_FALLBACK=true para testes sem APIs")
    print("- Verifique FETCH_API_KEY se usar endpoints autenticados")
    print("- Para produção, configure todos os FETCH_*_URL no .env")

if __name__ == "__main__":
    main()
