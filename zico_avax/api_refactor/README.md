# 🚀 Zico Swap API - Avalanche

Uma API completa para operações de swap na rede Avalanche, suportando o protocolo **Trader Joe**.

## ✨ Características

- 🔄 **Swap de Tokens**: Suporte completo para swaps entre tokens ERC-20
- 🏆 **Preços em Tempo Real**: Obtém preços atualizados do Trader Joe
- 🚀 **Execução de Swaps**: Executa swaps via smart wallet do frontend
- 📊 **Preços em Tempo Real**: Integração com CoinGecko para preços de mercado
- 🔐 **Segurança**: Autenticação por assinatura de smart wallet (sem chaves privadas)
- ⚡ **Performance**: Cache inteligente e rate limiting
- 🛡️ **Segurança**: Middleware de validação e sanitização
- 🚫 **Sem Chaves Privadas**: API não armazena ou usa chaves privadas

## 🏗️ Arquitetura

```
zico_avax/api_refactor/
├── config/
│   └── constants.js          # Configurações e constantes
├── services/
│   ├── traderJoeService.js   # Serviço para Trader Joe
│   └── priceService.js       # Serviço de preços (CoinGecko)
├── middleware/
│   └── auth.js               # Middleware de autenticação
├── routes/
│   ├── swapRoutes.js         # Rotas de swap
│   └── priceRoutes.js        # Rotas de preços
├── index.js                  # Servidor principal
├── package.json              # Dependências
├── env.example               # Exemplo de variáveis de ambiente
└── README.md                 # Esta documentação
```

## 🚀 Instalação

### 1. Clone o repositório
```bash
cd zico_avax/api_refactor
```

### 2. Instale as dependências
```bash
npm install
```

### 3. Configure as variáveis de ambiente
```bash
cp env.example .env
```

Edite o arquivo `.env` com suas configurações:
```env
# Configurações da Rede Avalanche
RPC_URL_AVALANCHE=https://api.avax.network/ext/bc/C/rpc
RPC_URL_FUJI=https://api.avax-test.network/ext/bc/C/rpc

# Endereço da Wallet (opcional, para operações de leitura)
WALLET_ADDRESS=your_wallet_address_here

# Chaves de API (opcionais)
TRADER_JOE_API_KEY=your_traderjoe_api_key_here
COINGECKO_API_KEY=your_coingecko_api_key_here

# Configurações de Segurança
JWT_SECRET=your_jwt_secret_here
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100

# Configurações do Servidor
PORT=3001
NODE_ENV=development
```

### 4. Execute a API
```bash
# Modo desenvolvimento
npm run dev

# Modo produção
npm start
```

## 📡 Endpoints

### 🔄 Swap Routes

#### Obter Preço - Trader Joe
```http
POST /swap/price/traderjoe
Content-Type: application/json

{
  "address": "0x...",
  "signature": "0x...",
  "message": "timestamp:1234567890",
  "timestamp": 1234567890,
  "tokenIn": "0x...",
  "tokenOut": "0x...",
  "amountIn": "1000000000000000000"
}
```



#### Obter Preço (Comparação)
```http
POST /swap/price/compare
Content-Type: application/json

{
  "address": "0x...",
  "signature": "0x...",
  "message": "timestamp:1234567890",
  "timestamp": 1234567890,
  "tokenIn": "0x...",
  "tokenOut": "0x...",
  "amountIn": "1000000000000000000"
}
```

#### Executar Swap - Trader Joe
```http
POST /swap/execute/traderjoe
Content-Type: application/json

{
  "address": "0x...",
  "signature": "0x...",
  "message": "timestamp:1234567890",
  "timestamp": 1234567890,
  "tokenIn": "0x...",
  "tokenOut": "0x...",
  "amountIn": "1000000000000000000",
  "slippage": 1.0
}
```



#### Executar Swap (Trader Joe)
```http
POST /swap/execute/best
Content-Type: application/json

{
  "address": "0x...",
  "signature": "0x...",
  "message": "timestamp:1234567890",
  "timestamp": 1234567890,
  "tokenIn": "0x...",
  "tokenOut": "0x...",
  "amountIn": "1000000000000000000",
  "slippage": 1.0
}
```

#### Obter Cotação Detalhada
```http
POST /swap/quote
Content-Type: application/json

{
  "address": "0x...",
  "signature": "0x...",
  "message": "timestamp:1234567890",
  "timestamp": 1234567890,
  "tokenIn": "0x...",
  "tokenOut": "0x...",
  "amountIn": "1000000000000000000",
  "slippage": 1.0
}
```

#### Listar Tokens Comuns
```http
GET /swap/tokens/common
```

#### Opções de Slippage
```http
GET /swap/slippage/options
```

### 💰 Price Routes

#### Preços dos Tokens Comuns da Avalanche
```http
GET /price/avalanche/common?vs_currency=usd
```

#### Preço de Token Específico
```http
GET /price/coingecko/bitcoin?vs_currency=usd
```

#### Preço de Token da Rede Avalanche
```http
GET /price/avalanche/token/0x...?vs_currency=usd
```

#### Histórico de Preços
```http
GET /price/history/bitcoin?vs_currency=usd&days=7
```

#### Informações do Token
```http
GET /price/token/bitcoin
```

#### Tendências de Mercado
```http
GET /price/trending?vs_currency=usd
```

#### Estatísticas Globais
```http
GET /price/global?vs_currency=usd
```

#### Preços em Lote
```http
POST /price/batch
Content-Type: application/json

{
  "address": "0x...",
  "signature": "0x...",
  "message": "timestamp:1234567890",
  "timestamp": 1234567890,
  "tokenIds": ["bitcoin", "ethereum", "avalanche-2"],
  "vs_currency": "usd"
}
```

### 🏥 Health & Info Routes

#### Health Check
```http
GET /health
```

#### Informações da API
```http
GET /info
```

#### Status da Rede
```http
GET /network/status
```

#### Configurações
```http
GET /config
```

## 🔐 Autenticação

A API usa autenticação por assinatura de smart wallet. Para autenticar uma requisição:

1. **Crie uma mensagem**: `timestamp:1234567890`
2. **Assine com sua smart wallet do frontend**
3. **Inclua no body**:
   - `address`: Endereço da sua wallet
   - `signature`: Assinatura da mensagem
   - `message`: Mensagem assinada
   - `timestamp`: Timestamp da mensagem

### Exemplo de Autenticação (JavaScript)

```javascript
// Em produção, a assinatura viria do smart wallet do frontend
async function createAuthenticatedRequest() {
  const timestamp = Date.now();
  const message = `timestamp:${timestamp}`;
  
  // A assinatura é feita pelo smart wallet do frontend
  // Aqui simulamos apenas para exemplo
  const signature = await smartWallet.signMessage(message);
  
  const requestBody = {
    address: smartWallet.address,
    signature: signature,
    message: message,
    timestamp: timestamp,
    // ... outros parâmetros
  };
  
  return requestBody;
}
```

## 🪙 Tokens Suportados

### Tokens Comuns da Avalanche
- **AVAX** (Wrapped AVAX)
- **USDC** (USD Coin)
- **USDT** (Tether)
- **DAI** (Dai Stablecoin)
- **WETH** (Wrapped Ethereum)
- **JOE** (Trader Joe Token)

- **LINK** (Chainlink)
- **UNI** (Uniswap)

## 🔧 Configuração

### Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `RPC_URL_AVALANCHE` | RPC da rede Avalanche | `https://api.avax.network/ext/bc/C/rpc` |
| `RPC_URL_FUJI` | RPC da testnet Fuji | `https://api.avax-test.network/ext/bc/C/rpc` |
| `WALLET_ADDRESS` | Endereço da wallet (opcional) | Opcional |

| `PORT` | Porta do servidor | `3001` |
| `NODE_ENV` | Ambiente de execução | `development` |

### Configurações de Segurança

| Configuração | Valor | Descrição |
|--------------|-------|-----------|
| Rate Limit | 100 req/15min | Limite global de requisições |
| Signature Expiry | 5 minutos | Tempo de validade da assinatura |
| Max Amount | 1M AVAX | Valor máximo para swaps |
| Min Amount | 0.000001 AVAX | Valor mínimo para swaps |

## 🧪 Testes

### Teste Básico da API
```bash
# Health check
curl http://localhost:3001/health

# Informações da API
curl http://localhost:3001/info

# Status da rede
curl http://localhost:3001/network/status
```

### Teste de Swap (requer autenticação)
```bash
# Obter preço
curl -X POST http://localhost:3001/swap/price/traderjoe \
  -H "Content-Type: application/json" \
  -d '{
    "address": "0x...",
    "signature": "0x...",
    "message": "timestamp:1234567890",
    "timestamp": 1234567890,
    "tokenIn": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",
    "tokenOut": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
    "amountIn": "1000000000000000000"
  }'
```

**Nota**: A assinatura deve vir do smart wallet do frontend. Em produção, não é necessário configurar chaves privadas na API.

## 📊 Monitoramento

### Logs
A API registra todas as requisições e erros no console. Em produção, configure um sistema de logging adequado.

### Métricas
- **Uptime**: `/health`
- **Status da rede**: `/network/status`
- **Estatísticas do cache**: `/price/cache/stats`

## 🚨 Troubleshooting

### Erros Comuns

#### "Rate limit excedido"
- Aguarde o período de rate limiting
- Use autenticação para limites mais altos

#### "Assinatura inválida"
- Verifique se a mensagem está correta
- Confirme se o timestamp não expirou
- Use a wallet correta para assinar

#### "Rede incorreta"
- Verifique se está usando a Chain ID correta
- Confirme se o RPC está funcionando

#### "Token não encontrado"
- Verifique se o endereço do token está correto
- Confirme se o token existe na rede Avalanche

### Debug
Para debug detalhado, defina `NODE_ENV=development` no arquivo `.env`.

## 🔒 Segurança

### Boas Práticas
- ✅ **NUNCA** compartilhe chaves privadas
- ✅ **NÃO** configure chaves privadas na API (use smart wallets do frontend)
- ✅ Use HTTPS em produção
- ✅ Configure CORS adequadamente
- ✅ Monitore logs de acesso
- ✅ Atualize dependências regularmente

### Configurações de Segurança
- Helmet para headers de segurança
- Rate limiting para prevenir abuso
- Validação de entrada
- Sanitização de dados
- Timeout em requisições externas

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 📞 Suporte

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Documentação**: [Wiki](https://github.com/your-repo/wiki)
- **Email**: support@yourdomain.com

## 🙏 Agradecimentos

- **Trader Joe** - Protocolo de swap principal

- **CoinGecko** - Dados de preços
- **Avalanche** - Rede blockchain
- **Ethers.js** - Biblioteca Ethereum

---

**⚠️ Aviso**: Esta API é para fins educacionais e de desenvolvimento. Use em produção por sua conta e risco. Sempre teste em testnet antes de usar na mainnet.

**🔐 Segurança**: A API não armazena chaves privadas. Todas as transações são assinadas pelo smart wallet do frontend e enviadas como transações assinadas.
