# Agent ↔ Capability Contract

> Vocabulário oficial para todo agente Zico que dispara ações no Panorama backend. Pareia com o `@panorama/capability` shared package (cards Hugo #199–#210) e com os schemas/tools introduzidos nos cards Rizzi #69–#70.

**Audiência:** quem escreve prompts, ferramentas LangChain, ou novos agentes em `zico_agents/new_zico/src/agents/`.

---

## 1. Por que este contrato existe

Antes da refatoração, prompts de agente mencionavam protocolos diretamente — "I'll swap your USDC using Uniswap", "stake on Lido", "borrow from Benqi". Isso prendia o agente a nomes que o backend reescolhe em runtime e quebrava sempre que um provider entrava ou saía do registry.

A partir do Bloco 5 (lending/staking/liquidity migradas) o backend fala **capability**, não protocolo. O agente precisa fazer o mesmo:

- **User-facing text:** só fala capability (`"swap"`, `"liquidity pool"`, `"stake"`)
- **Tool calls:** emitem `CapabilityIntent`, não payload livre
- **Decisões:** consultam `/v1/capability/_discovery` antes de propor ação

---

## 2. Pipeline de tradução NL → Capability Call

```
┌────────────┐    ┌──────────┐    ┌──────────────────┐    ┌──────────┐
│  user NL   │───▶│  agent   │───▶│ CapabilityIntent │───▶│ backend  │
│  "swap     │    │ classify │    │ {capability,     │    │ POST     │
│   ETH USDC"│    │   +      │    │  action, payload,│    │ /v1/cap  │
└────────────┘    │ discover │    │  chain_id, ...}  │    └──────────┘
                  └──────────┘    └──────────────────┘
```

**Etapas que o agente DEVE seguir, nessa ordem:**

1. **Parse intent.** Classifica a NL em `(capability, action)`. Exemplos:
   - "swap 1 ETH for USDC" → `("swap", "prepare-swap")`
   - "add liquidity to ETH/USDC pool" → `("liquidity", "prepare-add")`
   - "stake my ETH" → `("staking", "prepare-stake")`
2. **Discovery.** Chama o tool `discover_capabilities` (card #69) passando o `chain_id` que o usuário está usando. Se a capability não está no snapshot OU não tem provider `healthy: true` naquele chain, o agente **não propõe a ação** — explica a indisponibilidade ao user.
3. **Build payload.** Monta o `payload` específico da action (formatos típicos: `tokenIn/tokenOut/amountIn` para swap, `poolId/amountA/amountB` para liquidity, `amount` para staking).
4. **Emit intent.** Constrói um `CapabilityIntent` (`src/models/capability_intent.py`, card #70) com `tenant_id`, `trace_id` herdados do contexto da conversa.
5. **Dispatch.** Dispatcher HTTP usa `intent.endpoint_path()` + `intent.to_capability_request()` para fazer `POST /v1/capability/<cap>/<action>` com o envelope camelCase que Hugo definiu.

---

## 3. Regras de output (HARD)

| Regra | Faça | Não faça |
|---|---|---|
| Vocabulário | "I'll prepare a swap for you" | "I'll use Uniswap to swap" |
| Recomendação | "swap is available on Base" | "Aerodrome is the best DEX on Base" |
| Falha de provider | "swap is temporarily unavailable on Base" | "Uniswap returned 503" |
| Routing/seleção | "the backend will pick the best route" | "I'll route through Multihop" |

**Por que:** o backend pode rolar providers de um sprint pro outro. Se o agente mencionar `aerodrome` num prompt cacheado e o registry trocar pra `uniswap` na semana seguinte, o agente vira mentiroso.

**Exceção autorizada:** explicações técnicas explícitas em modo debug/dev (`DEBUG=true`). Nunca em conversa de produção.

---

## 4. Tradução de erros — `ErrorCategory` → mensagem human-friendly

O backend retorna `CapabilityErrorResponse` com `error.category` (enum fechado). O agente traduz pra prosa antes de mostrar ao user.

| `category` | Mensagem sugerida ao user |
|---|---|
| `VALIDATION` | "I had trouble understanding the request — could you confirm the token and amount?" |
| `UNSUPPORTED_ROUTE` | "This swap isn't supported on `<chain>` — the pair may not exist there yet." |
| `INSUFFICIENT_LIQUIDITY` | "Not enough liquidity on-chain for that amount right now. Want to try a smaller size?" |
| `RATE_LIMITED` | "We're hitting upstream limits — please try again in a few seconds." |
| `PROVIDER_FAILURE` | "The on-chain provider failed and we couldn't fall back. I'll retry once and let you know." |
| `UNAVAILABLE` | "That capability is offline on `<chain>` right now. I'll let you know when it's back." |
| `INTERNAL` | "Something went wrong on our side — engineering has been notified." |

**Nunca** vaze stack traces, IDs de provider ou status codes HTTP no output user-facing. Esses ficam no `metadata.error` que vai pro log estruturado.

---

## 5. Onde está cada peça

| Peça | Arquivo | Card |
|---|---|---|
| `CapabilityIntent` schema | `src/models/capability_intent.py` | #70 |
| `discover_capabilities` tool | `src/integrations/panorama_gateway/capability_discovery.py` | #69 |
| Lista canônica de capability slugs | `panorama-block-backend/shared/capability/provider.types.ts` (`CAPABILITY_SLUGS`) | Hugo #200 |
| `CapabilityRequest<T>` envelope (wire) | `panorama-block-backend/shared/capability/envelope.types.ts` | Hugo #199 |
| Discovery handler | `panorama-block-backend/shared/capability/http/discovery.handler.ts` | Hugo #207 |
| `ErrorCategory` enum | `panorama-block-backend/shared/capability/errors.ts` | Hugo #201 |

---

## 6. Roteiro pra novos agents

Quando criar um novo agente que vai disparar ações:

1. Registre `discover_capabilities_tool` na lista de tools do agente.
2. Force o agente a chamar discovery antes de propor qualquer prepare-*.
3. Final step do agent SEMPRE retorna um `CapabilityIntent` (ou `None` se a capability não estiver disponível).
4. Escreva contract tests (modelo no card #71) que dado uma NL específica, assertam que o output:
   - Não contém nome de protocolo (`grep` por `uniswap|aerodrome|lido|benqi|moonwell` no output text)
   - É um `CapabilityIntent` válido pelo schema Pydantic
   - `(capability, action)` aparecem em algum cenário válido do discovery mock

---

## 7. FAQ

**Pode mencionar "DCA" se a capability é `automation`?**
Sim. "DCA", "limit order", "recurring buy" são *features* user-facing dentro da capability `automation`. O slug interno (`automation`) é detalhe de implementação que não precisa vazar.

**E se o discovery falhar (BE down)?**
O tool retorna `{ capabilities: [], error: "..." }` — o agente trata como "nada disponível" e pede pro user tentar de novo em alguns segundos. Não inventa providers.

**Como descobrir qual `action` usar?**
Cada capability tem um conjunto fechado de actions documentado nos docs específicos: `swap-capability.md`, `liquidity-capability.md`, `staking-capability.md` (em `panorama-block-backend/<svc>/docs/`). Esses são autoridade — quando bater na ambiguidade, leia o doc da capability.
