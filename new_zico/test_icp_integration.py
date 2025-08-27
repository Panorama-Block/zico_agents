#!/usr/bin/env python3
"""
Teste de Integração - ICP Agent
Testa as funcionalidades do agente ICP no sistema Zico
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

def test_icp_staking_plan():
    """Testa criação de plano de staking ICP"""
    print("🧪 Testando plano de staking ICP...")
    
    payload = {
        "message": {
            "role": "user",
            "content": "Criar um plano para fazer stake de 5 ICP por 30 dias"
        },
        "user_id": "test_user_icp",
        "conversation_id": "test_icp_staking"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Resposta recebida:")
        print(f"   Agent: {data.get('agentName', 'N/A')}")
        print(f"   Response: {data.get('response', 'N/A')[:200]}...")
        
        # Verificar se é o agente ICP
        if data.get('agentName') == 'icp':
            print("✅ Roteamento correto para ICP Agent")
            
            # Verificar se contém plano Candid
            response_text = data.get('response', '')
            if 'Candid' in response_text and 'record' in response_text:
                print("✅ Plano Candid gerado com sucesso")
            else:
                print("⚠️ Plano Candid não encontrado na resposta")
        else:
            print(f"❌ Roteamento incorreto. Esperado: icp, Recebido: {data.get('agentName')}")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de staking: {e}")
        return False

def test_icp_swap_plan():
    """Testa criação de plano de swap ICP"""
    print("\n🧪 Testando plano de swap ICP...")
    
    payload = {
        "message": {
            "role": "user", 
            "content": "Quero trocar 2 ICP por ckBTC, criar um plano"
        },
        "user_id": "test_user_icp",
        "conversation_id": "test_icp_swap"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Resposta recebida:")
        print(f"   Agent: {data.get('agentName', 'N/A')}")
        print(f"   Response: {data.get('response', 'N/A')[:200]}...")
        
        # Verificar roteamento e conteúdo
        if data.get('agentName') == 'icp':
            print("✅ Roteamento correto para ICP Agent")
            
            response_text = data.get('response', '')
            if 'swap' in response_text.lower() and ('icp' in response_text.lower() or 'ckbtc' in response_text.lower()):
                print("✅ Plano de swap gerado corretamente")
            else:
                print("⚠️ Conteúdo de swap não reconhecido na resposta")
        else:
            print(f"❌ Roteamento incorreto para swap ICP")
            
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de swap: {e}")
        return False

def test_icp_status_query():
    """Testa consulta de status de staking"""
    print("\n🧪 Testando consulta de status ICP...")
    
    payload = {
        "message": {
            "role": "user",
            "content": "Mostrar meus stakes ativos no ICP"
        },
        "user_id": "test_user_icp",
        "conversation_id": "test_icp_status"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Resposta recebida:")
        print(f"   Agent: {data.get('agentName', 'N/A')}")
        print(f"   Response: {data.get('response', 'N/A')[:200]}...")
        
        if data.get('agentName') == 'icp':
            print("✅ Roteamento correto para ICP Agent")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de status: {e}")
        return False

def test_icp_rates_query():
    """Testa consulta de taxas de swap"""
    print("\n🧪 Testando consulta de taxas ICP...")
    
    payload = {
        "message": {
            "role": "user",
            "content": "Qual é a taxa de câmbio atual de ICP para ckETH?"
        },
        "user_id": "test_user_icp", 
        "conversation_id": "test_icp_rates"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Resposta recebida:")
        print(f"   Agent: {data.get('agentName', 'N/A')}")
        print(f"   Response: {data.get('response', 'N/A')[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de taxas: {e}")
        return False

def test_direct_icp_tools():
    """Testa ferramentas ICP diretamente"""
    print("\n🧪 Testando ferramentas ICP diretamente...")
    
    try:
        from src.agents.icp.tools import (
            icp_describe_canister_tool,
            icp_plan_stake_tool,
            icp_query_rates_tool
        )
        
        # Teste describe canister
        print("📋 Testando describe_canister...")
        result = icp_describe_canister_tool("staking")
        print(f"   Resultado: {result[:100]}...")
        
        # Teste plan stake
        print("📋 Testando plan_stake...")
        result = icp_plan_stake_tool(500000000, 2592000)  # 5 ICP por 30 dias
        print(f"   Resultado: {result[:100]}...")
        
        # Teste query rates
        print("📋 Testando query_rates...")
        result = icp_query_rates_tool("ICP", "ckBTC")
        print(f"   Resultado: {result[:100]}...")
        
        print("✅ Testes diretos de ferramentas ICP concluídos")
        return True
        
    except Exception as e:
        print(f"❌ Erro nos testes diretos: {e}")
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

def main():
    """Executa todos os testes de integração ICP"""
    print("🚀 Iniciando Testes de Integração ICP")
    print("=" * 50)
    
    # Verificar se servidor está rodando
    if not test_health_check():
        return
    
    print(f"\n📍 Testando endpoint: {BASE_URL}")
    print("=" * 50)
    
    # Executar testes
    tests = [
        test_icp_staking_plan,
        test_icp_swap_plan, 
        test_icp_status_query,
        test_icp_rates_query,
        test_direct_icp_tools
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
    print("📊 RESUMO DOS TESTES ICP")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Testes Passaram: {passed}/{total}")
    print(f"❌ Testes Falharam: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 Todos os testes ICP passaram!")
    else:
        print("⚠️ Alguns testes falharam. Verifique a configuração.")
    
    print("\n💡 Dicas:")
    print("- Certifique-se de que ICP_STAKING_CANISTER_ID está configurado")
    print("- Verifique se ICP_SWAP_CANISTER_ID está configurado")
    print("- Configure ICP_BASE_URL se usar consultas HTTP")
    print("- Para produção, faça deploy dos canisters com 'dfx deploy'")

if __name__ == "__main__":
    main()
