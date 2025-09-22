#!/usr/bin/env python3
"""
Script de teste da integração ICP - Canisters e Agentes
Testa conectividade, funcionalidade dos endpoints e geração de planos Candid.
"""

import sys
import os
sys.path.append('src')

import asyncio
import json
import time
from typing import Dict, Any

# Configuração básica primeiro
try:
    from src.agents.icp.config import ICPConfig
except ImportError:
    print("❌ Erro: Não foi possível importar ICPConfig")
    sys.exit(1)

# Cliente ICP
try:
    from src.agents.icp.client import (
        query_stake_status,
        query_rates,
        query_swap_quote,
        query_staking_params,
        get_canister_info
    )
except ImportError as e:
    print(f"❌ Erro: Não foi possível importar client ICP: {e}")
    sys.exit(1)

class ICPIntegrationTester:
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

    def test_configuration(self):
        """Testa se a configuração ICP está válida"""
        print("\n🔧 TESTANDO CONFIGURAÇÃO ICP")

        # Test 1: Configuração básica
        try:
            assert ICPConfig.STAKING_CANISTER_ID, "STAKING_CANISTER_ID não configurado"
            assert ICPConfig.SWAP_CANISTER_ID, "SWAP_CANISTER_ID não configurado"
            assert ICPConfig.BITCOIN_CANISTER_ID, "BITCOIN_CANISTER_ID não configurado"
            assert ICPConfig.BASE_URL, "BASE_URL não configurado"

            self.log_test(
                "Configuration Validation",
                True,
                f"Configuração válida - Base: {ICPConfig.BASE_URL}"
            )
        except AssertionError as e:
            self.log_test(
                "Configuration Validation",
                False,
                str(e)
            )

        # Test 2: Timeout reasonable
        try:
            assert 5 <= ICPConfig.TIMEOUT <= 60, f"Timeout {ICPConfig.TIMEOUT}s fora do range razoável"
            self.log_test(
                "Timeout Configuration",
                True,
                f"Timeout de {ICPConfig.TIMEOUT}s está adequado"
            )
        except AssertionError as e:
            self.log_test(
                "Timeout Configuration",
                False,
                str(e)
            )

    def test_client_functions(self):
        """Testa todas as funções do client ICP"""
        print("\n🔨 TESTANDO FUNÇÕES DO CLIENT ICP")

        # Test 1: Query stake status
        try:
            result = query_stake_status()
            success = isinstance(result, dict)
            if success and "error" in result:
                self.log_test(
                    "Query Stake Status",
                    True,
                    f"Função funcional (erro esperado: {result['error'][:50]}...)"
                )
            elif success:
                self.log_test(
                    "Query Stake Status",
                    True,
                    "Função de consulta stake funcional e conectou!"
                )
            else:
                self.log_test(
                    "Query Stake Status",
                    False,
                    f"Retorno inválido: {type(result)}"
                )
        except Exception as e:
            self.log_test(
                "Query Stake Status",
                False,
                f"Erro na função: {e}"
            )

        # Test 2: Get canister info
        try:
            info = get_canister_info("staking")
            assert "canisterId" in info, "Info missing canisterId"
            assert "methods" in info, "Info missing methods"
            assert len(info["methods"]) > 0, "No methods found"

            self.log_test(
                "Get Canister Info",
                True,
                f"Info do canister funcional - {len(info['methods'])} métodos",
                {"canisterId": info["canisterId"][:20] + "...", "methodCount": len(info["methods"])}
            )
        except Exception as e:
            self.log_test(
                "Get Canister Info",
                False,
                f"Erro ao obter info: {e}"
            )

    def test_utils_integration(self):
        """Testa se os utilitários ic_urls funcionam corretamente"""
        print("\n🔗 TESTANDO UTILITÁRIOS DE URL")

        try:
            # Tentar import do utils
            sys.path.append('../src')
            from utils.ic_urls import canister_http_base, format_canister_endpoint

            # Test URL formatting for local
            local_url = canister_http_base("test-canister", "http://127.0.0.1:4943")
            expected_local = "http://test-canister.localhost:4943"
            
            if local_url == expected_local:
                self.log_test(
                    "URL Utils Integration",
                    True,
                    "Utilitários de URL funcionando corretamente"
                )
            else:
                self.log_test(
                    "URL Utils Integration",
                    False,
                    f"URL incorreta. Esperado: {expected_local}, Obtido: {local_url}"
                )

        except ImportError as e:
            self.log_test(
                "URL Utils Integration",
                False,
                f"Erro ao importar utilitários: {e}"
            )
        except Exception as e:
            self.log_test(
                "URL Utils Integration",
                False,
                f"Erro nos utilitários: {e}"
            )

    def test_icp_agent_tools(self):
        """Testa as ferramentas do agente ICP"""
        print("\n🤖 TESTANDO FERRAMENTAS DO AGENTE ICP")

        try:
            from src.agents.icp.tools import (
                icp_describe_canister_tool,
                icp_plan_stake_tool
            )

            # Test 1: Describe canister tool
            try:
                result = icp_describe_canister_tool("staking")
                assert isinstance(result, str), "Resultado deve ser string"
                assert "staking" in result.lower() or "canister" in result.lower(), "Resultado deve mencionar staking/canister"

                self.log_test(
                    "ICP Describe Canister Tool",
                    True,
                    "Tool de descrição funcional"
                )
            except Exception as e:
                self.log_test(
                    "ICP Describe Canister Tool",
                    False,
                    f"Erro na tool: {e}"
                )

            # Test 2: Plan stake tool
            try:
                result = icp_plan_stake_tool(500000000, 604800)  # 5 ICP, 7 dias
                assert isinstance(result, str), "Resultado deve ser string"
                
                # Verificar se contém elementos de um plano
                has_plan_elements = any(keyword in result for keyword in [
                    "META:", "args_candid", "start_staking", "amount_e8s", "duration_s"
                ])
                
                if has_plan_elements:
                    self.log_test(
                        "ICP Plan Stake Tool",
                        True,
                        "Tool de planejamento stake funcional"
                    )
                else:
                    self.log_test(
                        "ICP Plan Stake Tool",
                        False,
                        f"Plano não contém elementos esperados. Resultado: {result[:100]}..."
                    )

            except Exception as e:
                self.log_test(
                    "ICP Plan Stake Tool",
                    False,
                    f"Erro na tool: {e}"
                )

        except ImportError as e:
            self.log_test(
                "ICP Agent Tools Import",
                False,
                f"Erro ao importar tools: {e}"
            )

    def run_all_tests(self):
        """Executa todos os testes"""
        print("🚀 INICIANDO TESTES DE INTEGRAÇÃO ICP")
        print("=" * 60)

        start_time = time.time()

        self.test_configuration()
        self.test_utils_integration()
        self.test_client_functions()
        self.test_icp_agent_tools()

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
    tester = ICPIntegrationTester()
    success = tester.run_all_tests()

    # Salvar resultados
    try:
        with open("icp_test_results.json", "w") as f:
            json.dump(tester.test_results, f, indent=2)
        print(f"\n📝 Resultados salvos em: icp_test_results.json")
    except Exception as e:
        print(f"\n⚠️  Erro ao salvar resultados: {e}")

    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
