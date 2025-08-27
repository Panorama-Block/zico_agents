#!/usr/bin/env python3
"""
Teste específico do Database Agent
"""

import os
import sys
import json

# Adiciona o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from langchain_google_genai import ChatGoogleGenerativeAI
from src.agents.database.agent import DatabaseAgent
from src.agents.config import Config

def test_database_queries():
    """Testa diferentes tipos de consultas no database agent."""
    
    print("🧪 Testando Database Agent com diferentes consultas...")
    print("=" * 60)
    
    # Verifica se a API key está configurada
    if not Config.GEMINI_API_KEY:
        print("❌ Erro: GEMINI_API_KEY não está configurada!")
        print("Configure a variável de ambiente GEMINI_API_KEY")
        return
    
    # Inicializa o LLM
    llm = ChatGoogleGenerativeAI(
        model=Config.GEMINI_MODEL,
        temperature=0,
        google_api_key=Config.GEMINI_API_KEY
    )
    
    # Cria o agente
    print("🔧 Criando Database Agent...")
    database_agent = DatabaseAgent(llm)
    
    # Lista de consultas para testar
    test_queries = [
        {
            "query": "Quais informações de crypto eu tenho no meu banco de dados?",
            "description": "Consulta de schema"
        },
        {
            "query": "Quais as redes de crypto o meu banco tem acesso?",
            "description": "Consulta com agregação temporal"
        }
    ]
    
    print(f"📊 Testando {len(test_queries)} consultas diferentes...")
    print()
    
    for i, test_case in enumerate(test_queries, 1):
        query = test_case["query"]
        description = test_case["description"]
        
        print(f"🔍 Teste {i}: {description}")
        print(f"📝 Consulta: {query}")
        print("-" * 50)
        
        try:
            # Executa a consulta
            result = database_agent.agent.invoke({
                "messages": [{"role": "user", "content": query}]
            })
            
            # Extrai a resposta
            if hasattr(result, 'messages') and result.messages:
                response = result.messages[-1].content
            else:
                response = str(result)
            
            print(f"✅ Resposta: {response}")
            
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print()
        print("=" * 60)
        print()

def test_database_tools_directly():
    """Testa as ferramentas de banco de dados diretamente."""
    
    print("🔧 Testando ferramentas de banco de dados diretamente...")
    print("=" * 60)
    
    from src.agents.database.tools import search_database
    
    # Testa algumas consultas diretamente
    direct_queries = [
        "Mostre-me os top 3 criptomoedas",
        "Qual é o preço do Bitcoin?",
        "Quantas transações temos na base?",
        "Mostre-me o floor price das NFTs"
    ]
    
    for i, query in enumerate(direct_queries, 1):
        print(f"🔍 Consulta direta {i}: {query}")
        print("-" * 40)
        
        try:
            result = search_database(query)
            print(f"✅ Resultado: {result}")
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print()
        print("=" * 60)
        print()

if __name__ == "__main__":
    print("🧪 TESTE COMPLETO DO DATABASE AGENT")
    print("=" * 60)
    print()
    
    # Teste 1: Ferramentas diretamente
    test_database_tools_directly()
    
    print("\n" + "=" * 60)
    print()
    
    # Teste 2: Agente completo
    test_database_queries()
    
    print("\n✅ Testes concluídos!") 