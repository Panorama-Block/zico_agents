#!/usr/bin/env python3
"""
Teste da API do Database Agent
"""

import requests
import json

def test_api():
    """Testa a API do sistema."""
    
    print("🌐 Testando API do Zico Agent...")
    print("=" * 40)
    
    # URL base da API
    base_url = "http://localhost:8000"
    
    # Teste 1: Health check
    print("🔍 Teste 1: Health check")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.json()}")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    print("-" * 40)
    
    # Teste 2: Chat com consulta de banco
    print("🔍 Teste 2: Chat com consulta de banco")
    
    test_data = {
        "messages": [
            {
                "role": "user",
                "content": "Mostre-me os top 5 criptomoedas por preço"
            }
        ]
    }
    
    try:
        response = requests.post(f"{base_url}/chat", json=test_data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Resposta da API:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Erro: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Erro: Não foi possível conectar à API.")
        print("Certifique-se de que o servidor está rodando com:")
        print("python -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    print("-" * 40)
    
    # Teste 3: Outras consultas
    print("🔍 Teste 3: Outras consultas")
    
    queries = [
        "Qual é o preço do Bitcoin?",
        "Quantas transações temos na base?",
        "Mostre-me o floor price das NFTs"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n📝 Consulta {i}: {query}")
        
        test_data = {
            "messages": [
                {
                    "role": "user",
                    "content": query
                }
            ]
        }
        
        try:
            response = requests.post(f"{base_url}/chat", json=test_data)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Agente: {result.get('agent', 'N/A')}")
                print(f"📄 Resposta: {result.get('response', 'N/A')[:200]}...")
            else:
                print(f"❌ Erro: {response.text}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_api() 