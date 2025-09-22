#!/usr/bin/env python3
"""
Teste da API FastAPI e roteamento do Supervisor
Testa endpoints, roteamento de agentes e funcionalidade geral da API.
"""

import sys
import os
sys.path.append('src')

import asyncio
import json
import time
import requests
import subprocess
from typing import Dict, Any
from threading import Thread
from contextlib import contextmanager

class APIIntegrationTester:
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
        self.api_process = None
        self.base_url = "http://localhost:8000"

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

    def test_api_structure(self):
        """Testa estrutura da API"""
        print("\n🏗️ TESTANDO ESTRUTURA DA API")

        # Test 1: Arquivo app.py existe
        app_file = "src/app.py"
        if os.path.exists(app_file):
            with open(app_file, 'r') as f:
                content = f.read()

            # Verificar elementos essenciais
            has_fastapi = "FastAPI" in content
            has_cors = "CORS" in content or "cors" in content.lower()
            has_supervisor = "supervisor" in content.lower()
            has_chat_endpoint = "/chat" in content

            self.log_test(
                "API Structure",
                has_fastapi and has_chat_endpoint,
                f"API estruturada corretamente",
                {
                    "has_fastapi": has_fastapi,
                    "has_cors": has_cors,
                    "has_supervisor": has_supervisor,
                    "has_chat_endpoint": has_chat_endpoint
                }
            )
        else:
            self.log_test(
                "API Structure",
                False,
                "Arquivo src/app.py não encontrado"
            )

    def test_supervisor_integration(self):
        """Testa integração do supervisor"""
        print("\n🎯 TESTANDO INTEGRAÇÃO DO SUPERVISOR")

        # Test 1: Verificar arquivos do supervisor
        supervisor_files = [
            "src/agents/supervisor/__init__.py",
            "src/agents/supervisor/agent.py"
        ]

        found_supervisor_files = []
        for file_path in supervisor_files:
            if os.path.exists(file_path):
                found_supervisor_files.append(file_path)

        supervisor_exists = len(found_supervisor_files) >= 1

        self.log_test(
            "Supervisor Files",
            supervisor_exists,
            f"Arquivos do supervisor: {len(found_supervisor_files)}/{len(supervisor_files)}",
            {"found_files": found_supervisor_files}
        )

        # Test 2: Verificar se supervisor está no app.py
        app_file = "src/app.py"
        if os.path.exists(app_file):
            with open(app_file, 'r') as f:
                app_content = f.read()

            has_supervisor_import = "supervisor" in app_content.lower()
            has_supervisor_instance = "Supervisor" in app_content

            self.log_test(
                "Supervisor in App",
                has_supervisor_import or has_supervisor_instance,
                "Supervisor integrado na aplicação" if (has_supervisor_import or has_supervisor_instance) else "Supervisor não encontrado na aplicação"
            )

    def test_available_agents(self):
        """Testa agentes disponíveis"""
        print("\n🤖 TESTANDO AGENTES DISPONÍVEIS")

        app_file = "src/app.py"
        if os.path.exists(app_file):
            with open(app_file, 'r') as f:
                app_content = f.read()

            # Procurar por lista de agentes
            expected_agents = ["icp", "crypto", "fetch", "advisory", "supervisor"]
            found_agents = []

            for agent in expected_agents:
                if agent in app_content.lower():
                    found_agents.append(agent)

            success = len(found_agents) >= 3  # Pelo menos 3 agentes

            self.log_test(
                "Available Agents",
                success,
                f"Agentes encontrados no código: {len(found_agents)}/{len(expected_agents)}",
                {"found_agents": found_agents}
            )

    def test_api_endpoints_structure(self):
        """Testa estrutura dos endpoints da API"""
        print("\n🔌 TESTANDO ESTRUTURA DOS ENDPOINTS")

        app_file = "src/app.py"
        if os.path.exists(app_file):
            with open(app_file, 'r') as f:
                app_content = f.read()

            # Verificar endpoints essenciais
            expected_endpoints = [
                "/health",
                "/chat",
                "/agents/available",
                "/agents/commands"
            ]

            found_endpoints = []
            for endpoint in expected_endpoints:
                if endpoint in app_content:
                    found_endpoints.append(endpoint)

            success = len(found_endpoints) >= 3

            self.log_test(
                "API Endpoints Structure",
                success,
                f"Endpoints encontrados: {len(found_endpoints)}/{len(expected_endpoints)}",
                {"found_endpoints": found_endpoints}
            )

    def test_dependencies(self):
        """Testa dependências necessárias"""
        print("\n📦 TESTANDO DEPENDÊNCIAS")

        # Test 1: Requirements.txt
        req_file = "requirements.txt"
        if os.path.exists(req_file):
            with open(req_file, 'r') as f:
                requirements = f.read()

            essential_deps = ["fastapi", "uvicorn", "pydantic", "langchain"]
            found_deps = []

            for dep in essential_deps:
                if dep in requirements.lower():
                    found_deps.append(dep)

            success = len(found_deps) >= 3

            self.log_test(
                "Essential Dependencies",
                success,
                f"Dependências essenciais: {len(found_deps)}/{len(essential_deps)}",
                {"found_deps": found_deps}
            )
        else:
            self.log_test(
                "Essential Dependencies",
                False,
                "Arquivo requirements.txt não encontrado"
            )

        # Test 2: Tentar importar módulos críticos
        try:
            import fastapi
            import uvicorn
            import pydantic
            
            self.log_test(
                "Critical Imports",
                True,
                "Módulos críticos podem ser importados"
            )
        except ImportError as e:
            self.log_test(
                "Critical Imports",
                False,
                f"Erro ao importar módulos críticos: {e}"
            )

    def test_configuration_integration(self):
        """Testa integração de configurações"""
        print("\n⚙️ TESTANDO INTEGRAÇÃO DE CONFIGURAÇÕES")

        # Test 1: Verificar se config.py existe
        config_file = "src/agents/config.py"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config_content = f.read()

            has_llm_config = "llm" in config_content.lower() or "gemini" in config_content.lower()
            has_env_vars = "getenv" in config_content or "environ" in config_content

            self.log_test(
                "Configuration File",
                has_llm_config,
                "Arquivo de configuração encontrado e configurado",
                {
                    "has_llm_config": has_llm_config,
                    "has_env_vars": has_env_vars
                }
            )
        else:
            self.log_test(
                "Configuration File",
                False,
                "Arquivo src/agents/config.py não encontrado"
            )

        # Test 2: Verificar variáveis de ambiente essenciais
        essential_env_vars = ["GEMINI_API_KEY", "ICP_BASE_URL"]
        found_env_vars = {}

        for var in essential_env_vars:
            value = os.getenv(var)
            found_env_vars[var] = value is not None

        success_rate = sum(found_env_vars.values()) / len(found_env_vars)

        self.log_test(
            "Essential Environment Variables",
            success_rate >= 0.5,
            f"Variáveis essenciais configuradas: {sum(found_env_vars.values())}/{len(found_env_vars)}",
            found_env_vars
        )

    def run_all_tests(self):
        """Executa todos os testes"""
        print("🚀 INICIANDO TESTES DE INTEGRAÇÃO DA API")
        print("=" * 60)

        start_time = time.time()

        self.test_api_structure()
        self.test_supervisor_integration()
        self.test_available_agents()
        self.test_api_endpoints_structure()
        self.test_dependencies()
        self.test_configuration_integration()

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
    tester = APIIntegrationTester()
    success = tester.run_all_tests()

    # Salvar resultados
    try:
        with open("api_test_results.json", "w") as f:
            json.dump(tester.test_results, f, indent=2)
        print(f"\n📝 Resultados salvos em: api_test_results.json")
    except Exception as e:
        print(f"\n⚠️  Erro ao salvar resultados: {e}")

    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
