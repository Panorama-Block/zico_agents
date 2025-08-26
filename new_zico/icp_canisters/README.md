# ICP Canisters - Staking e Swap

Este projeto contém os canisters Motoko para funcionalidades de staking e swap no protocolo Internet Computer.

## Estrutura do Projeto

```
icp_canisters/
├── dfx.json                 # Configuração do projeto DFX
├── src/
│   ├── staking/
│   │   └── main.mo         # Canister de staking
│   └── swap/
│       └── main.mo         # Canister de swap
├── staking.did             # Interface Candid do staking
├── swap.did                # Interface Candid do swap
└── README.md               # Este arquivo
```

## Funcionalidades

### Staking Canister

**Tokens Suportados:**
- ICP (5.0% APY)
- ckBTC (4.5% APY)  
- ckETH (6.0% APY)
- CHAT (8.0% APY)

**Métodos Principais:**
- `start_staking(amount_e8s, duration_s)` - Inicia um stake
- `get_stake_status(user)` - Consulta stakes do usuário
- `withdraw_stake(stake_id)` - Retira stake após vencimento
- `params()` - Parâmetros de staking

**Características:**
- Armazenamento estável persistente
- Cálculo de recompensas baseado em tempo
- Validação de parâmetros mínimos/máximos
- Sistema de autorização por Principal

### Swap Canister

**Pares Suportados:**
- ICP/ckBTC
- ICP/ckETH  
- ICP/CHAT

**Métodos Principais:**
- `quote(pair, amount_in)` - Cotação de swap
- `create_swap(pair, amount_in, min_out)` - Executa swap
- `get_rates(pair)` - Taxa de câmbio atual
- `list_swaps(user, cursor)` - Histórico de swaps

**Características:**
- Modelo AMM (Automated Market Maker)
- Fórmula de produto constante
- Proteção contra slippage
- Cálculo de impacto no preço
- Pools de liquidez inicializados

## Deployment

### Pré-requisitos

1. **Instalar DFX:**
```bash
sh -ci "$(curl -fsSL https://internetcomputer.org/install.sh)"
```

2. **Verificar instalação:**
```bash
dfx --version
```

### Deploy Local

1. **Iniciar replica local:**
```bash
dfx start --background
```

2. **Deploy dos canisters:**
```bash
dfx deploy
```

3. **Verificar status:**
```bash
dfx canister status staking
dfx canister status swap
```

### Deploy na Mainnet

1. **Configurar identidade:**
```bash
dfx identity new production
dfx identity use production
```

2. **Deploy na IC:**
```bash
dfx deploy --network ic
```

## Testes

### Teste Staking

```bash
# Iniciar stake de 5 ICP por 30 dias
dfx canister call staking start_staking '(500_000_000, 2_592_000)'

# Consultar status
dfx canister call staking get_stake_status '(null)'

# Retirar stake (após vencimento)
dfx canister call staking withdraw_stake '(1)'
```

### Teste Swap

```bash
# Cotação ICP -> ckBTC
dfx canister call swap quote '(record {tokenA=variant {ICP}; tokenB=variant {ckBTC}}, 100_000_000)'

# Executar swap
dfx canister call swap create_swap '(record {tokenA=variant {ICP}; tokenB=variant {ckBTC}}, 100_000_000, 2_000_000)'

# Ver histórico
dfx canister call swap list_swaps '(principal "rdmx6-jaaaa-aaaah-qdrva-cai", null)'
```

## Configuração de Produção

### Variáveis de Ambiente

```bash
# IDs dos canisters (após deploy)
export ICP_STAKING_CANISTER_ID="canister_id_aqui"
export ICP_SWAP_CANISTER_ID="canister_id_aqui"

# Base URL para consultas HTTP (opcional)
export ICP_BASE_URL="https://ic0.app"

# Timeouts e limites
export ICP_HTTP_TIMEOUT="15"
export ICP_DEFAULT_MAX_SLIPPAGE_BPS="200"
```

### Monitoramento

```bash
# Status dos canisters
dfx canister status staking --network ic
dfx canister status swap --network ic

# Logs (se configurado)
dfx canister logs staking --network ic
```

## Integração com Backend

Os canisters são integrados ao backend Python através dos módulos:
- `src/agents/icp/tools.py` - Ferramentas de integração
- `src/agents/icp/client.py` - Cliente HTTP para queries
- `src/agents/icp/agent.py` - Agente LangGraph

## Segurança

### Considerações Importantes

1. **Autorização:** Apenas o owner do stake pode retirar
2. **Validação:** Parâmetros são validados antes da execução  
3. **Proteção:** Swaps têm proteção contra slippage
4. **Armazenamento:** Estado persistente em stable storage
5. **Upgrades:** Suporte a upgrades com migração de estado

### Auditoria

- Teste todas as operações em testnet primeiro
- Verifique permissões e autorizações
- Monitore reservas dos pools
- Implemente limits de transação se necessário

## Troubleshooting

### Problemas Comuns

1. **Erro de memória:**
```bash
dfx canister call <canister> __get_candid_interface_tmp_hack
```

2. **Estado inconsistente:**
```bash
dfx canister stop <canister>
dfx canister start <canister>
```

3. **Upgrade com problemas:**
```bash
dfx canister install <canister> --mode reinstall
```

## Desenvolvimento

### Estrutura do Código

- **Tipos:** Definidos no topo de cada arquivo
- **Estado:** Variáveis stable para persistência  
- **Métodos:** Separados entre query e update
- **Helpers:** Funções auxiliares privadas

### Boas Práticas

- Use tipos Nat/Int para valores monetários
- Implemente validação rigorosa
- Mantenha estado mínimo necessário
- Teste upgrades cuidadosamente
- Documente interfaces Candid

### Extensões Futuras

- Suporte a mais tokens
- Pools de liquidez dinâmicos  
- Governança on-chain
- Integração com ICRC-1
- Métricas e analytics
