#!/usr/bin/env python3
"""
Script de Teste Rápido - Validação das Correções

Testa rapidamente se as principais correções estão funcionando:
1. URLs formatadas corretamente
2. Parser JSON do BitcoinService  
3. HTTP facades dos canisters
4. ZICO chat endpoint

Uso:
    python test_quick.py
"""

import requests
import json
import sys
import os
from typing import Dict, Any

# Configurações
BASE_URL = os.getenv("ICP_BASE_URL", "http://127.0.0.1:4943")
ZICO_URL = os.getenv("ZICO_URL", "http://localhost:8000")

CANISTER_IDS = {
    "bitcoin": os.getenv("ICP_BITCOIN_CANISTER_ID", "uzt4z-lp777-77774-qaabq-cai"),
    "staking": os.getenv("ICP_STAKING_CANISTER_ID", "ujk4p-kk777-77774-qaabr-cai"),
    "swap": os.getenv("ICP_SWAP_CANISTER_ID", "ukd4g-ll777-77774-qaabs-cai")
}

def format_canister_url(canister_id: str, endpoint: str) -> str:
    """Formata URL do canister (correção aplicada)"""
    if "localhost" in BASE_URL or "127.0.0.1" in BASE_URL:
        port = "4943"
        if ":" in BASE_URL:
            port = BASE_URL.split(":")[-1]
        return f"http://{canister_id}.localhost:{port}/{endpoint.lstrip('/')}"
    else:
        return f"https://{canister_id}.icp0.io/{endpoint.lstrip('/')}"

def test_bitcoin_parser():
    """Testa parser JSON corrigido"""
    print("🧪 Testando parser JSON do BitcoinService...")
    
    try:
        url = format_canister_url(CANISTER_IDS["bitcoin"], "/get-balance")
        test_address = "bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs"
        
        response = requests.post(
            url,
            json={"address": test_address},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("address") == test_address:
                print(f"✅ Parser JSON funcionando: {data}")
                return True
            else:
                print(f"⚠️ Parser retornou endereço diferente: {data}")
                return False
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_staking_facade():
    """Testa HTTP facade do StakingCanister"""
    print("🧪 Testando HTTP facade do StakingCanister...")
    
    try:
        # Teste parâmetros
        url = format_canister_url(CANISTER_IDS["staking"], "/staking/params")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ StakingCanister /staking/params: {data}")
            return True
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_swap_facade():
    """Testa HTTP facade do SwapCanister"""
    print("🧪 Testando HTTP facade do SwapCanister...")
    
    try:
        # Teste rates
        url = format_canister_url(CANISTER_IDS["swap"], "/swap/rates")
        
        response = requests.get(
            url,
            params={"tokenA": "ICP", "tokenB": "ckBTC"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SwapCanister /swap/rates: {data}")
            return True
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_zico_stake_plan():
    """Testa geração de plano de stake via ZICO"""
    print("🧪 Testando ZICO - Plano de Stake...")
    
    try:
        response = requests.post(
            f"{ZICO_URL}/chat",
            json={
                "message": {
                    "role": "user",
                    "content": "Fazer stake de 5 ICP por 7 dias"
                },
                "user_id": "test_user",
                "conversation_id": "test_conv"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", "")
            
            if "||META:" in response_text:
                print("✅ ZICO gerou plano de stake com META")
                # Extrair e validar META
                try:
                    meta_start = response_text.find("||META: ") + 8
                    meta_end = response_text.find("||", meta_start)
                    meta_json = response_text[meta_start:meta_end]
                    meta_data = json.loads(meta_json)
                    
                    if meta_data.get("type") == "IC_STAKE_PLAN":
                        print(f"   📋 Plano válido: {meta_data.get('summary')}")
                        print(f"   🏷️ Candid: {meta_data.get('args_candid')}")
                        return True
                    else:
                        print(f"   ⚠️ Tipo de plano inesperado: {meta_data.get('type')}")
                        return False
                except Exception as e:
                    print(f"   ❌ Erro ao parsear META: {e}")
                    return False
            else:
                print(f"⚠️ ZICO respondeu sem META: {response_text[:200]}...")
                return False
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_zico_swap_plan():
    """Testa geração de plano de swap via ZICO"""
    print("🧪 Testando ZICO - Plano de Swap...")
    
    try:
        response = requests.post(
            f"{ZICO_URL}/chat",
            json={
                "message": {
                    "role": "user",
                    "content": "Trocar 2 ICP por ckBTC"
                },
                "user_id": "test_user",
                "conversation_id": "test_conv_2"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", "")
            
            if "||META:" in response_text:
                print("✅ ZICO gerou plano de swap com META")
                return True
            else:
                print(f"⚠️ ZICO respondeu sem META: {response_text[:200]}...")
                return False
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def main():
    """Executa todos os testes rápidos"""
    print("🚀 TESTE RÁPIDO DE INTEGRAÇÃO")
    print("=" * 50)
    print(f"🔗 Base URL: {BASE_URL}")
    print(f"🤖 ZICO URL: {ZICO_URL}")
    print(f"📦 Canisters: {CANISTER_IDS}")
    print()
    
    tests = [
        ("BitcoinService Parser JSON", test_bitcoin_parser),
        ("StakingCanister HTTP Facade", test_staking_facade),
        ("SwapCanister HTTP Facade", test_swap_facade),
        ("ZICO Stake Plan Generation", test_zico_stake_plan),
        ("ZICO Swap Plan Generation", test_zico_swap_plan),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        print("-" * 30)
        success = test_func()
        results.append((test_name, success))
        print()
    
    # Resumo
    print("📊 RESUMO DOS TESTES")
    print("=" * 30)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📈 Taxa de sucesso: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("✅ Sistema pronto para uso")
        sys.exit(0)
    elif passed >= total // 2:
        print("\n⚠️ ALGUNS TESTES FALHARAM")
        print("🔧 Verifique configuração e logs")
        sys.exit(1)
    else:
        print("\n❌ MUITOS TESTES FALHARAM")
        print("🚨 Sistema necessita correções")
        sys.exit(2)

if __name__ == "__main__":
    main()
