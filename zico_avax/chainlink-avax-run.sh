# Compilar os contratos
forge build

# Rodar testes (alguns falharão porque precisam da rede Avalanche)
forge test

# Deploy para uma rede
forge script script/Deploy.s.sol --rpc-url $RPC_URL --private-key $PRIVATE_KEY --broadcast