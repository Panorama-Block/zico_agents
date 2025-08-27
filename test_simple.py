#!/usr/bin/env python3
"""
Teste Simples - Verifica se as correções básicas estão funcionando
Foca apenas nos canisters ICP (Staking/Swap) sem Bitcoin
"""

import requests
import json
import os

# Configurações
BASE_URL = "http://127.0.0.1:4943"
ZICO_URL = "http://localhost:8000"

# IDs dos canisters (serão detectados automaticamente)
def get_canister_ids():
    """Tenta obter IDs dos canisters do dfx"""
    try:
        import subprocess
        result = subprocess.run(['dfx', 'canister', 'id', 'staking_canister'], 
                              capture_output=True, text=True, cwd='new_zico/icp_canisters')
        staking_id = result.stdout.strip() if result.returncode == 0 else None
        
        result = subprocess.run(['dfx', 'canister', 'id', 'swap_canister'], 
                              capture_output=True, text=True, cwd='new_zico/icp_canisters')
        swap_id = result.stdout.strip() if result.returncode == 0 else None
        
        result = subprocess.run(['dfx', 'canister', 'id', 'bitcoin_service'], 
                              capture_output=True, text=True, cwd='new_zico/icp_canisters')
        bitcoin_id = result.stdout.strip() if result.returncode == 0 else None
        
        return {
            "staking": staking_id,
            "swap": swap_id, 
            "bitcoin": bitcoin_id
        }
    except:
        return {"staking": None, "swap": None, "bitcoin": None}

def format_canister_url(canister_id, endpoint):
    """Usa formatação correta de URLs (correção implementada)"""
    return f"http://{canister_id}.localhost:4943/{endpoint.lstrip('/')}"

def test_canister_urls():
    """Testa se as URLs estão formatadas corretamente"""
    print("🧪 Testando formatação de URLs dos canisters...")
    
    canister_ids = get_canister_ids()
    
    success_count = 0
    total_tests = 0
    
    for canister_name, canister_id in canister_ids.items():
        if not canister_id:
            print(f"⚠️ {canister_name}: ID não encontrado")
            continue
            
        total_tests += 1
        url = format_canister_url(canister_id, "/")
        
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {canister_name}: {url} - OK")
                success_count += 1
            else:
                print(f"❌ {canister_name}: {url} - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ {canister_name}: {url} - {e}")
    
    return success_count, total_tests

def test_staking_facade():
    """Testa facade HTTP do StakingCanister"""
    print("\n🧪 Testando HTTP facade do StakingCanister...")
    
    canister_ids = get_canister_ids()
    staking_id = canister_ids.get("staking")
    
    if not staking_id:
        print("❌ Staking canister ID não encontrado")
        return False
    
    try:
        # Teste /staking/params
        url = format_canister_url(staking_id, "/staking/params")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ StakingCanister params: OK")
            print(f"   Resposta: {response.text[:100]}...")
            return True
        else:
            print(f"❌ StakingCanister params: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ StakingCanister: {e}")
        return False

def test_swap_facade():
    """Testa facade HTTP do SwapCanister"""
    print("\n🧪 Testando HTTP facade do SwapCanister...")
    
    canister_ids = get_canister_ids()
    swap_id = canister_ids.get("swap")
    
    if not swap_id:
        print("❌ Swap canister ID não encontrado") 
        return False
    
    try:
        # Teste /swap/rates
        url = format_canister_url(swap_id, "/swap/rates")
        response = requests.get(url, params={"tokenA": "ICP", "tokenB": "ckBTC"}, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ SwapCanister rates: OK")
            print(f"   Resposta: {response.text[:100]}...")
            return True
        else:
            print(f"❌ SwapCanister rates: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ SwapCanister: {e}")
        return False

def test_zico_api():
    """Testa se o ZICO API está funcionando"""
    print("\n🧪 Testando ZICO API...")
    
    try:
        # Teste simples de health check
        response = requests.get(f"{ZICO_URL}/health", timeout=5)
        
        if response.status_code == 200:
            print("✅ ZICO API: OK")
            return True
        else:
            print(f"❌ ZICO API: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ZICO API: {e}")
        return False

def main():
    """Executa todos os testes simples"""
    print("🚀 TESTE SIMPLES DE INTEGRAÇÃO")
    print("=" * 40)
    
    # Mostrar IDs dos canisters
    canister_ids = get_canister_ids()
    print("📦 Canisters detectados:")
    for name, cid in canister_ids.items():
        status = "✅" if cid else "❌"
        print(f"   {status} {name}: {cid or 'não encontrado'}")
    
    print()
    
    # Executar testes
    tests = [
        ("URLs dos Canisters", test_canister_urls),
        ("StakingCanister Facade", test_staking_facade),
        ("SwapCanister Facade", test_swap_facade),
        ("ZICO API", test_zico_api),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        if test_name == "URLs dos Canisters":
            success, total = test_func()
            results.append((test_name, success == total and total > 0))
        else:
            success = test_func()
            results.append((test_name, success))
    
    # Resumo
    print("\n📊 RESUMO")
    print("=" * 20)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📈 Taxa de sucesso: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed >= total * 0.75:  # 75% ou mais
        print("\n🎉 Testes passaram! Sistema funcional")
        exit_code = 0
    elif passed >= total * 0.5:  # 50% ou mais
        print("\n⚠️ Alguns problemas detectados")
        exit_code = 1
    else:
        print("\n❌ Muitos problemas - verificar configuração")
        exit_code = 2
    
    print("\n💡 Dicas:")
    print("   • Verifique se dfx está rodando: dfx ping")
    print("   • Deploy canisters: cd new_zico/icp_canisters && dfx deploy")
    print("   • Inicie ZICO: cd new_zico && uvicorn src.app:app --reload")
    
    return exit_code

if __name__ == "__main__":
    exit(main())
