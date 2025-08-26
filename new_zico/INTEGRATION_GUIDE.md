# Guia de Integração - ICP e Fetch.ai

Este documento descreve como integrar e usar os novos módulos ICP e Fetch.ai no sistema Zico.

## 📋 Visão Geral

O sistema agora possui dois novos agentes especializados:

1. **ICP Agent**: Operações no Internet Computer Protocol (staking e swap)
2. **Fetch.ai Agent**: Análises de mercado e conselhos de trading

## 🏗️ Arquitetura

```
Chat → Supervisor → {ICP Agent | Fetch.ai Agent} → Ferramentas → Resultado
```

### Fluxo ICP
```
Usuário: "Quero fazer stake de 5 ICP por 30 dias"
↓
Supervisor roteia para icp_agent
↓
icp_agent usa ferramenta icp.plan_stake
↓
Retorna plano Candid para frontend assinar via Plug
```

### Fluxo Fetch.ai
```
Usuário: "É um bom momento para comprar AVAX?"
↓
Supervisor roteia para fetch_agent  
↓
fetch_agent usa ferramenta fetch.advice.trade_timing
↓
Retorna análise de timing e recomendações
```

## 🚀 Setup e Configuração

### 1. Instalar Dependências

As dependências já estão incluídas no `requirements.txt` existente:
- `requests` para HTTP
- `langchain` e `langgraph` para agentes

### 2. Configurar Variáveis de Ambiente

Copie `env.example` para `.env` e configure:

```bash
cp env.example .env
```

**Configurações ICP mínimas:**
```env
ICP_STAKING_CANISTER_ID=seu_canister_id_aqui
ICP_SWAP_CANISTER_ID=seu_canister_id_aqui
```

**Configurações Fetch.ai mínimas:**
```env
FETCH_TIMING_URL=https://seu-endpoint-timing.com
FETCH_API_KEY=sua_chave_aqui
FETCH_ENABLE_FALLBACK=true
```

### 3. Deploy dos Canisters ICP

```bash
cd icp_canisters
dfx start --background
dfx deploy
```

Anote os IDs dos canisters e atualize no `.env`.

### 4. Testar Integração

```bash
# Iniciar servidor
python -m uvicorn src.app:app --reload --port 8000

# Testar ICP
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {"role": "user", "content": "Criar plano para stake de 5 ICP por 30 dias"},
    "user_id": "test_user"
  }'

# Testar Fetch.ai
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {"role": "user", "content": "Analisar timing de mercado para AVAX"},
    "user_id": "test_user"
  }'
```

## 🎯 Casos de Uso

### ICP Agent

**Comandos aceitos:**
- "Fazer stake de X ICP por Y dias"
- "Mostrar status dos meus stakes"
- "Planejar swap de ICP para ckBTC"
- "Consultar taxas ICP/ckETH"
- "Retirar stake ID 123"

**Exemplos de resposta:**
```json
{
  "agentName": "icp",
  "response": "🎯 Plano de Staking Criado...",
  "metadata": {
    "type": "IC_STAKE_PLAN",
    "canisterId": "xxx-xxx",
    "method": "start_staking",
    "args_candid": "(record { amount_e8s = 500000000; duration_s = 2592000; })"
  }
}
```

### Fetch.ai Agent

**Comandos aceitos:**
- "É bom momento para comprar AVAX?"
- "Que tamanho de posição usar para ICP?"
- "Analisar custos de swap AVAX/USDC"
- "Métricas da rede Avalanche"

**Exemplos de resposta:**
```json
{
  "agentName": "advisory",
  "response": "⏰ Análise de Timing - AVAX\n\nAssessment: ✅ Favorável (Score: 0.72)..."
}
```

## 🔧 Ferramentas Disponíveis

### ICP Tools

1. **icp.describe_canister**: Documentação de canisters
2. **icp.plan_stake**: Geração de planos de staking
3. **icp.query_stake_status**: Status de stakes ativos
4. **icp.plan_swap**: Geração de planos de swap
5. **icp.query_rates**: Consulta de taxas

### Fetch.ai Tools

1. **fetch.advice.trade_timing**: Análise de timing
2. **fetch.advice.position_size**: Tamanho de posição
3. **fetch.advice.fee_slip**: Análise de custos
4. **fetch.query.metrics**: Métricas de rede

## 💡 Exemplos de Integração

### 1. Staking ICP Completo

```python
# Via chat API
response = requests.post("http://localhost:8000/chat", json={
    "message": {
        "role": "user", 
        "content": "Quero fazer stake de 10 ICP por 60 dias"
    },
    "user_id": "user123"
})

# Resposta contém plano Candid
plan = response.json()["metadata"]
# Frontend usa plan["args_candid"] para assinar via Plug
```

### 2. Análise de Mercado

```python
# Via chat API  
response = requests.post("http://localhost:8000/chat", json={
    "message": {
        "role": "user",
        "content": "Analisar timing para swing trade em AVAX com janela de 30 dias"
    },
    "user_id": "user123"
})

# Resposta contém análise formatada
analysis = response.json()["response"]
```

### 3. Fluxo Combinado

```python
# 1. Análise de mercado via Fetch.ai
timing_response = requests.post("http://localhost:8000/chat", json={
    "message": {"role": "user", "content": "É bom momento para ICP?"},
    "user_id": "user123"
})

# 2. Se favorável, criar plano via ICP Agent
if "Favorável" in timing_response.json()["response"]:
    stake_response = requests.post("http://localhost:8000/chat", json={
        "message": {"role": "user", "content": "Criar plano stake 5 ICP 30 dias"},
        "user_id": "user123"  
    })
    
    # 3. Frontend executa plano retornado
    plan = stake_response.json()["metadata"]
```

## 🔒 Segurança

### ICP
- Transações sempre assinadas no frontend via Plug/II
- Backend apenas gera "planos" (não executa)
- Validação de parâmetros nos tools
- Limites configuráveis via env vars

### Fetch.ai
- Fallbacks automáticos quando APIs indisponíveis
- Timeout configurável para HTTP calls
- Dados sintéticos quando endpoints falham
- Rate limiting implícito via timeout

## 📊 Monitoramento

### Logs
```python
import logging
logger = logging.getLogger("zico.agents")

# Logs automáticos incluem:
# - Chamadas de ferramentas ICP/Fetch
# - Tempos de resposta HTTP
# - Fallbacks ativados
# - Erros de validação
```

### Métricas
- Uso de ferramentas por agente
- Taxa de sucesso/erro das APIs
- Tempo de resposta médio
- Planos gerados vs executados

## 🧪 Testes

### Testes Unitários

```bash
# Testes de ferramentas ICP
python -m pytest tests/test_icp_tools.py

# Testes de ferramentas Fetch.ai  
python -m pytest tests/test_fetch_tools.py

# Testes de integração
python -m pytest tests/test_agents_integration.py
```

### Testes de API

```bash
# Usar scripts existentes
python test_api.py

# Novos endpoints de teste
python test_icp_integration.py
python test_fetch_integration.py
```

## 🚨 Troubleshooting

### Problemas Comuns

1. **ICP Canister não encontrado**
   - Verificar `ICP_STAKING_CANISTER_ID` no .env
   - Confirmar deploy com `dfx canister status`

2. **Fetch.ai timeout**
   - Verificar `FETCH_TIMING_URL` no .env
   - Ativar fallback: `FETCH_ENABLE_FALLBACK=true`

3. **Agent não responde**
   - Verificar logs do supervisor
   - Confirmar imports dos novos agentes

### Debug

```bash
# Logs detalhados
LOG_LEVEL=DEBUG python -m uvicorn src.app:app --reload

# Testar ferramentas isoladamente
python -c "
from src.agents.icp.tools import icp_plan_stake_tool
print(icp_plan_stake_tool(500000000, 2592000))
"

# Testar Fetch.ai
python -c "
from src.agents.fetch.tools import fetch_advice_trade_timing_tool  
print(fetch_advice_trade_timing_tool('AVAX', 'AVAX/USD', 'intra'))
"
```

## 🔄 Atualizações Futuras

### Roadmap ICP
- [ ] Suporte para mais tokens (SNS tokens)
- [ ] Governança via NNS integration
- [ ] Batch operations
- [ ] Advanced staking strategies

### Roadmap Fetch.ai
- [ ] Mais advisors especializados
- [ ] Machine learning predictions
- [ ] Portfolio optimization
- [ ] Real-time alerts

### Integração
- [ ] Fluxos automáticos (análise → ação)
- [ ] Dashboard de performance
- [ ] Backtesting de estratégias
- [ ] Multi-chain orchestration

## 📞 Suporte

Para dúvidas:
1. Verificar logs em `/var/log/zico_agent/`
2. Consultar documentação dos canisters
3. Testar com fallbacks ativados
4. Validar configurações de ambiente

## 📚 Referências

- [Internet Computer Documentation](https://internetcomputer.org/docs/)
- [Fetch.ai uAgents](https://docs.fetch.ai/uAgents/)
- [LangGraph Multi-Agent](https://langchain-ai.github.io/langgraph/)
- [Plug Wallet Integration](https://docs.plugwallet.ooo/)

