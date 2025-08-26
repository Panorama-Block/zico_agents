#!/bin/bash

# Script de Deploy dos Canisters ICP
# Deploy automatizado dos canisters de staking, swap e Bitcoin

echo "🚀 Iniciando deploy dos canisters ICP..."
echo "=================================================="

# Verificar se DFX está instalado
if ! command -v dfx &> /dev/null; then
    echo "❌ DFX não está instalado. Instale com:"
    echo "sh -ci \"$(curl -fsSL https://internetcomputer.org/install.sh)\""
    exit 1
fi

echo "✅ DFX encontrado: $(dfx --version)"

# Navegar para diretório dos canisters
cd icp_canisters || exit 1

echo "📁 Diretório atual: $(pwd)"

# Verificar se replica está rodando
if ! dfx ping &> /dev/null; then
    echo "🔄 Iniciando replica local..."
    dfx start --clean --background
    
    # Aguardar replica inicializar
    echo "⏳ Aguardando replica inicializar..."
    sleep 10
    
    # Verificar novamente
    if ! dfx ping &> /dev/null; then
        echo "❌ Falha ao iniciar replica local"
        exit 1
    fi
else
    echo "✅ Replica local já está rodando"
fi

echo "🔧 Fazendo deploy dos canisters..."

# Deploy do canister de staking
echo "📦 Deploying staking canister..."
STAKING_RESULT=$(dfx deploy staking 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ Staking canister deployed successfully"
    STAKING_ID=$(echo "$STAKING_RESULT" | grep -o 'rdmx6-jaaaa-aaaah-qdrva-cai\|[a-z0-9-]*' | head -1)
    echo "   Canister ID: $STAKING_ID"
else
    echo "❌ Failed to deploy staking canister"
    echo "$STAKING_RESULT"
fi

# Deploy do canister de swap
echo "📦 Deploying swap canister..."
SWAP_RESULT=$(dfx deploy swap 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ Swap canister deployed successfully"
    SWAP_ID=$(echo "$SWAP_RESULT" | grep -o 'rdmx6-jaaaa-aaaah-qdrva-cai\|[a-z0-9-]*' | head -1)
    echo "   Canister ID: $SWAP_ID"
else
    echo "❌ Failed to deploy swap canister"
    echo "$SWAP_RESULT"
fi

# Deploy do canister Bitcoin
echo "📦 Deploying bitcoin canister..."
BITCOIN_RESULT=$(dfx deploy bitcoin 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ Bitcoin canister deployed successfully"
    BITCOIN_ID=$(echo "$BITCOIN_RESULT" | grep -o 'rdmx6-jaaaa-aaaah-qdrva-cai\|[a-z0-9-]*' | head -1)
    echo "   Canister ID: $BITCOIN_ID"
else
    echo "❌ Failed to deploy bitcoin canister"
    echo "$BITCOIN_RESULT"
fi

echo ""
echo "=================================================="
echo "🎉 Deploy concluído!"
echo "=================================================="

# Mostrar URLs dos canisters
echo "📋 URLs dos Canisters (Candid UI):"

if [ ! -z "$STAKING_ID" ]; then
    echo "🥩 Staking: http://127.0.0.1:4943/?canisterId=rdmx6-jaaaa-aaaah-qdrva-cai&id=$STAKING_ID"
fi

if [ ! -z "$SWAP_ID" ]; then
    echo "🔄 Swap: http://127.0.0.1:4943/?canisterId=rdmx6-jaaaa-aaaah-qdrva-cai&id=$SWAP_ID"
fi

if [ ! -z "$BITCOIN_ID" ]; then
    echo "₿ Bitcoin: http://127.0.0.1:4943/?canisterId=rdmx6-jaaaa-aaaah-qdrva-cai&id=$BITCOIN_ID"
fi

echo ""
echo "🔧 Configurações para .env:"
echo "=========================="
echo "ICP_STAKING_CANISTER_ID=${STAKING_ID:-rdmx6-jaaaa-aaaah-qdrva-cai}"
echo "ICP_SWAP_CANISTER_ID=${SWAP_ID:-rdmx6-jaaaa-aaaah-qdrva-cai}" 
echo "ICP_BITCOIN_CANISTER_ID=${BITCOIN_ID:-rdmx6-jaaaa-aaaah-qdrva-cai}"
echo "ICP_BASE_URL=http://127.0.0.1:4943"

echo ""
echo "🧪 Testes básicos:"
echo "=================="

# Testar canister Bitcoin se deployed
if [ ! -z "$BITCOIN_ID" ]; then
    echo "🔍 Testando Bitcoin canister..."
    
    # Testar endpoint raiz
    echo "   Testando endpoint root..."
    BITCOIN_URL="http://$BITCOIN_ID.localhost:4943/"
    curl -s "$BITCOIN_URL" | head -100
    
    echo ""
    echo "   Testando get-balance..."
    curl -X POST -H "Content-Type: application/json" \
         -d '{"address": "bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs"}' \
         "http://$BITCOIN_ID.localhost:4943/get-balance" 2>/dev/null | head -100
fi

echo ""
echo "📚 Próximos passos:"
echo "==================="
echo "1. Copie os IDs dos canisters para seu arquivo .env"
echo "2. Teste os endpoints via Candid UI"
echo "3. Execute os testes de integração:"
echo "   python test_icp_integration.py"
echo "4. Inicie o agente Fetch.ai standalone:"
echo "   cd fetch_agent && python agent.py"

echo ""
echo "🌐 Para deploy na mainnet:"
echo "=========================="
echo "dfx deploy --network ic"

echo ""
echo "✅ Deploy script concluído!"
