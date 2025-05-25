# Compilar os contratos
forge build

# Rodar testes (alguns falharão porque precisam da rede Avalanche)
forge test

# Para testar com fork da Avalanche (se tiver RPC URL)
forge test --fork-url <AVALANCHE_RPC_URL>

# Deploy para uma rede
forge script script/Deploy.s.sol --rpc-url <RPC_URL> --private-key <PRIVATE_KEY>