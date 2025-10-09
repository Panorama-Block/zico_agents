#!/usr/bin/env python3
"""
Teste simples do Database Agent
"""

import os
import sys

# Adiciona o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from langchain_google_genai import ChatGoogleGenerativeAI
from src.agents.database.agent import DatabaseAgent
from src.agents.config import Config

def main():
    print("🧪 Testando Database Agent...")
    print("=" * 40)
    
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
    
    # Consulta de teste
    test_query = "Mostre-me os top 3 criptomoedas por preço"
    print(f"🔍 Testando consulta: {test_query}")
    print("-" * 40)
    
    try:
        # Executa a consulta
        result = database_agent.agent.invoke({
            "messages": [{"role": "user", "content": test_query}]
        })
        
        print("✅ Resultado:")
        print(result)
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 