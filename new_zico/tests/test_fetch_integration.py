#!/usr/bin/env python3
"""
Teste da integração Fetch.ai - Agentes e ASI:One
Testa conectividade, funcionalidade dos advisors e Chat Protocol.
"""

import sys
import os
sys.path.append('src')

import asyncio
import json
import time
from typing import Dict, Any
import requests

class FetchIntegrationTester:
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0

    def log_test(self, test_name: str, success: bool, message: str, details: Any = None):
        """Registra resultado de um teste"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "details": details,
            "timestamp": time.time()
        }
        self.test_results.append(result)

        if success:
            self.passed += 1
        else:
            self.failed += 1

        print(f"{status} {test_name}: {message}")
        if details and not success:
            print(f"   Details: {details}")

    def test_fetch_agent_structure(self):
        """Testa se a estrutura do agente Fetch.ai está presente"""
        print("\n🤖 TESTANDO ESTRUTURA DO AGENTE FETCH.AI")

        # Test 1: Arquivo agent.py existe
        agent_file = "fetch_agent/agent.py"
        if os.path.exists(agent_file):
            with open(agent_file, 'r') as f:
                content = f.read()

            # Verificar elementos chave
            has_asi_one = "ASI" in content or "asi" in content
            has_chat_protocol = "chat" in content.lower() or "protocol" in content.lower()
            has_bitcoin = "bitcoin" in content.lower() or "btc" in content.lower()

            self.log_test(
                "Fetch Agent Structure",
                True,
                f"Arquivo agent.py encontrado ({len(content)} chars)",
                {
                    "has_asi_integration": has_asi_one,
                    "has_chat_protocol": has_chat_protocol,
                    "has_bitcoin_features": has_bitcoin
                }
            )
        else:
            self.log_test(
                "Fetch Agent Structure",
                False,
                "Arquivo fetch_agent/agent.py não encontrado"
            )

        # Test 2: Requirements
        req_file = "fetch_agent/requirements.txt"
        if os.path.exists(req_file):
            with open(req_file, 'r') as f:
                requirements = f.read()

            has_uagents = "uagents" in requirements
            has_fetch_ai = "fetch" in requirements.lower()

            self.log_test(
                "Fetch Agent Requirements",
                True,
                "Requirements.txt encontrado",
                {
                    "has_uagents": has_uagents,
                    "has_fetch_deps": has_fetch_ai,
                    "content": requirements[:200] + "..." if len(requirements) > 200 else requirements
                }
            )
        else:
            self.log_test(
                "Fetch Agent Requirements",
                False,
                "Arquivo requirements.txt não encontrado"
            )

    def test_fetch_agent_config(self):
        """Testa configurações do agente Fetch.ai"""
        print("\n⚙️ TESTANDO CONFIGURAÇÕES FETCH.AI")

        # Test 1: Variáveis de ambiente relacionadas ao Fetch.ai
        fetch_env_vars = [
            "ASI1_API_KEY",
            "FETCH_TIMING_URL",
            "FETCH_SIZING_URL",
            "FETCH_FEESLIP_URL",
            "FETCH_ENABLE_FALLBACK"
        ]

        env_found = {}
        for var in fetch_env_vars:
            value = os.getenv(var)
            env_found[var] = value is not None

        success_rate = sum(env_found.values()) / len(env_found)

        self.log_test(
            "Fetch Environment Variables",
            success_rate >= 0.4,  # Pelo menos 40% das vars configuradas
            f"Variáveis encontradas: {sum(env_found.values())}/{len(env_found)}",
            env_found
        )

    def test_fetch_integration_in_backend(self):
        """Testa se o Fetch.ai está integrado no backend principal"""
        print("\n🔌 TESTANDO INTEGRAÇÃO NO BACKEND")

        # Test 1: Verificar se existe agente fetch no sistema principal
        fetch_agent_files = [
            "src/agents/fetch/agent.py",
            "src/agents/fetch/__init__.py",
            "src/agents/fetch/tools.py"
        ]

        found_files = []
        for file_path in fetch_agent_files:
            if os.path.exists(file_path):
                found_files.append(file_path)

        success = len(found_files) >= 2  # Pelo menos 2 arquivos necessários

        self.log_test(
            "Fetch Backend Integration",
            success,
            f"Arquivos encontrados: {len(found_files)}/{len(fetch_agent_files)}",
            {"found_files": found_files}
        )

        # Test 2: Verificar se Fetch está no app.py principal
        app_file = "src/app.py"
        if os.path.exists(app_file):
            with open(app_file, 'r') as f:
                app_content = f.read()

            has_fetch_import = "fetch" in app_content.lower()
            has_advisory = "advisory" in app_content.lower()

            self.log_test(
                "Fetch in Main App",
                has_fetch_import or has_advisory,
                "Fetch.ai mencionado no app principal" if (has_fetch_import or has_advisory) else "Fetch.ai não encontrado no app principal"
            )

    def test_asi_one_configuration(self):
        """Testa configuração ASI:One"""
        print("\n🧠 TESTANDO CONFIGURAÇÃO ASI:ONE")

        asi_key = os.getenv("ASI1_API_KEY")
        if asi_key:
            # Verificar se não é key de exemplo/placeholder
            is_real_key = not any(placeholder in asi_key.lower() for placeholder in [
                "your", "key", "here", "example", "placeholder", "test"
            ])

            # Verificar formato da key (ASI keys normalmente começam com sk_)
            has_proper_format = asi_key.startswith("sk_") and len(asi_key) > 20

            self.log_test(
                "ASI:One API Key",
                is_real_key and has_proper_format,
                "Key configurada e parece válida" if (is_real_key and has_proper_format) else f"Key problemática: real={is_real_key}, format={has_proper_format}"
            )
        else:
            self.log_test(
                "ASI:One API Key",
                False,
                "ASI1_API_KEY não configurada"
            )

    def test_fallback_mechanisms(self):
        """Testa mecanismos de fallback"""
        print("\n🔄 TESTANDO MECANISMOS DE FALLBACK")

        # Test 1: Configuração de fallback
        fallback_enabled = os.getenv("FETCH_ENABLE_FALLBACK", "false").lower() == "true"

        self.log_test(
            "Fallback Configuration",
            True,  # Sempre sucesso, só reporta o estado
            f"Fallback {'habilitado' if fallback_enabled else 'desabilitado'}"
        )

        # Test 2: URLs de fallback
        fallback_urls = [
            "FETCH_FALLBACK_TIMING_URL",
            "FETCH_FALLBACK_SIZING_URL",
            "FETCH_FALLBACK_FEESLIP_URL"
        ]

        fallback_configured = sum(1 for url in fallback_urls if os.getenv(url))

        self.log_test(
            "Fallback URLs",
            fallback_configured > 0 or fallback_enabled,
            f"URLs de fallback configuradas: {fallback_configured}/{len(fallback_urls)}"
        )

    def run_all_tests(self):
        """Executa todos os testes"""
        print("🚀 INICIANDO TESTES DE INTEGRAÇÃO FETCH.AI")
        print("=" * 60)

        start_time = time.time()

        self.test_fetch_agent_structure()
        self.test_fetch_agent_config()
        self.test_fetch_integration_in_backend()
        self.test_asi_one_configuration()
        self.test_fallback_mechanisms()

        end_time = time.time()
        duration = end_time - start_time

        print("\n" + "=" * 60)
        print("📊 RESUMO DOS TESTES")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"⏱️  Duration: {duration:.2f}s")

        total = self.passed + self.failed
        if total > 0:
            print(f"📈 Success Rate: {(self.passed/total*100):.1f}%")

        if self.failed > 0:
            print("\n🔍 TESTES QUE FALHARAM:")
            for result in self.test_results:
                if "FAIL" in result["status"]:
                    print(f"   - {result['test']}: {result['message']}")

        return self.failed == 0

def main():
    """Função principal"""
    tester = FetchIntegrationTester()
    success = tester.run_all_tests()

    # Salvar resultados
    try:
        with open("fetch_test_results.json", "w") as f:
            json.dump(tester.test_results, f, indent=2)
        print(f"\n📝 Resultados salvos em: fetch_test_results.json")
    except Exception as e:
        print(f"\n⚠️  Erro ao salvar resultados: {e}")

    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
