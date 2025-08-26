# Bitcoin ICP Agent - Fetch.ai Integration

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:internetcomputer](https://img.shields.io/badge/internetcomputer-9370DB)
![tag:bitcoin](https://img.shields.io/badge/bitcoin-FF6C49)
![tag:chatprotocol](https://img.shields.io/badge/chatprotocol-3D8BD3)

Um agente AI que pode verificar saldos de carteira Bitcoin e realizar operações blockchain usando consultas em linguagem natural. Construído usando o framework uAgents e integrado com Internet Computer para operações Bitcoin seguras.

## 🌟 Funcionalidades

- **Verificação de Saldo**: Consulta saldos de endereços Bitcoin em tempo real (BTC Testnet)
- **Análise de UTXO**: Obter saídas de transação não gastas detalhadas para qualquer endereço
- **Monitoramento de Taxas**: Acessar percentis de taxas atuais da rede Bitcoin
- **Linguagem Natural**: Entende consultas Bitcoin conversacionais
- **Integração ICP**: Operações seguras através do Internet Computer Protocol
- **Dados em Tempo Real**: Informações blockchain ao vivo e dados de rede

## 🚀 Setup Rápido

### 1. Pré-requisitos

```bash
# Instalar Python 3.8+
python3 --version

# Instalar DFX (DFINITY SDK)
sh -ci "$(curl -fsSL https://internetcomputer.org/install.sh)"

# Verificar instalação
dfx --version
```

### 2. Configurar Projeto

```bash
# Clonar e navegar para o diretório
cd fetch_agent

# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt
```

### 3. Deploy do Canister ICP

```bash
# Navegar para canisters ICP
cd ../icp_canisters

# Iniciar replica local
dfx start --clean --background

# Deploy do canister Bitcoin
dfx deploy bitcoin

# Anotar o Canister ID retornado
```

### 4. Configurar Variáveis

```bash
# Criar arquivo .env
cat > .env << EOF
ASI1_API_KEY=your_asi1_api_key_here
ICP_BITCOIN_CANISTER_ID=your_canister_id_here
ICP_BASE_URL=http://127.0.0.1:4943
EOF
```

### 5. Executar Agente

```bash
# Voltar para diretório do agente
cd ../fetch_agent

# Executar agente
python agent.py
```

## 🔑 Obter Chave ASI:One

1. Acesse https://asi1.ai/
2. Faça login com sua conta Google ou Fetch Wallet
3. Navegue para Workbench
4. Selecione Developer no menu lateral
5. Clique em Create New para gerar nova chave API
6. Copie a chave gerada
7. Substitua `ASI1_API_KEY` no arquivo .env

## 💬 Exemplos de Uso

### Consultas de Saldo (BTC Testnet)

```
"What's the balance of address bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs?"
"Can you check how many bitcoins are in bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs?"
"Show me the balance of this Bitcoin wallet: bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs"
```

### Consultas de UTXO

```
"What UTXOs are available for address bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs?"
"List unspent outputs for bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs"
"Do I have any unspent transactions for bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs?"
```

### Consultas de Taxas

```
"What are the current Bitcoin fee percentiles?"
"Show me the latest fee percentile distribution"
"How much are the Bitcoin network fees right now?"
```

### Geração de Endereços

```
"Generate a new Bitcoin address"
"Create a P2PKH address for me"
"I need a new Bitcoin wallet address"
```

## 🔗 Conectar com Agentverse

### Passo 1: Executar Agente Local

```bash
python agent.py
```

O agente exibirá:
```
🚀 Iniciando Bitcoin ICP Agent...
📍 Endereço do agente: agent1qdla8t5m3wm7tnua69jjv3p4cr4ugmzmcj95jy9vrh4209scxs02qlxwt0g
🔗 Canister ID: your_canister_id
🌐 Base URL: http://127.0.0.1:4943
💡 Conecte via Agentverse para usar o Chat Protocol
```

### Passo 2: Conectar Mailbox

1. Acesse https://agentverse.ai/agents
2. Encontre seu agente na lista
3. Clique em "Mailbox Connect"
4. Configure mailbox para comunicação

### Passo 3: Testar Chat

1. Clique em "Agent Profile"
2. Selecione "Chat with Agent"
3. Digite suas consultas Bitcoin
4. Teste os exemplos acima

## 🛠️ Desenvolvimento

### Estrutura do Código

```
fetch_agent/
├── agent.py              # Agente principal Fetch.ai
├── requirements.txt      # Dependências Python
├── README.md            # Este arquivo
└── .env                 # Configurações (criar)
```

### Classes Principais

- **ICPBitcoinService**: Interface com canister ICP
- **BitcoinQueryProcessor**: Processamento de consultas com LLM
- **ChatMessage**: Modelo para Chat Protocol

### Personalizando

```python
# Adicionar nova função Bitcoin
async def custom_bitcoin_operation(self, params):
    """Sua operação customizada"""
    try:
        # Implementar lógica
        result = await self.some_operation(params)
        return self._format_response(result)
    except Exception as e:
        return f"❌ Erro: {e}"

# Registrar no processador
self.functions.append({
    "name": "custom_operation",
    "description": "Descrição da operação",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Parâmetro 1"}
        },
        "required": ["param1"]
    }
})
```

## 🧪 Testes

### Testar Canister Local

```bash
# Verificar status do canister
dfx canister status bitcoin

# Testar endpoint diretamente
curl -X POST \
  "http://127.0.0.1:4943/bitcoin/get-balance" \
  -H "Content-Type: application/json" \
  -d '{"address": "bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs"}'
```

### Testar Agente

```bash
# Executar em modo debug
python agent.py --debug

# Logs detalhados
tail -f agent.log
```

## 🚨 Troubleshooting

### Problemas Comuns

1. **Agente não inicia**
   ```bash
   # Verificar dependências
   pip install -r requirements.txt
   
   # Verificar versão Python
   python --version  # Deve ser 3.8+
   ```

2. **Canister não responde**
   ```bash
   # Verificar se DFX está rodando
   dfx ping
   
   # Redeploy se necessário
   dfx deploy bitcoin --mode reinstall
   ```

3. **ASI:One não conecta**
   - Verificar chave API no .env
   - Confirmar que agente está rodando
   - Testar conexão de rede

### Logs e Debug

```bash
# Ativar logs detalhados
export LOG_LEVEL=DEBUG
python agent.py

# Verificar logs do DFX
dfx logs bitcoin
```

## 📚 Recursos Técnicos

- **Framework**: uAgents (Fetch.ai)
- **LLM Integration**: ASI1 AI
- **Blockchain**: Bitcoin Testnet
- **Protocol**: Internet Computer Protocol (ICP)
- **Language**: Python 3.8+

## 🌐 Deploy em Produção

### Preparar para Mainnet

1. **Configurar Mainnet IC**
   ```bash
   # Deploy na IC mainnet
   dfx deploy --network ic bitcoin
   ```

2. **Atualizar configurações**
   ```bash
   # .env para produção
   ICP_BASE_URL=https://ic0.app
   ICP_BITCOIN_CANISTER_ID=your_mainnet_canister_id
   ```

3. **Publicar no Agentverse**
   - Upload do código do agente
   - Configurar README completo
   - Adicionar tags relevantes
   - Testar funcionalidades

## 🤝 Contribuindo

1. Fork o repositório
2. Crie branch para feature (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para branch (`git push origin feature/nova-funcionalidade`)
5. Abra Pull Request

## 📄 Licença

Este projeto está sob licença MIT. Veja `LICENSE` para detalhes.

## 🔗 Links Úteis

- [Fetch.ai Documentation](https://docs.fetch.ai/)
- [Internet Computer Documentation](https://internetcomputer.org/docs/)
- [uAgents Framework](https://github.com/fetchai/uAgents)
- [ASI:One Platform](https://asi1.ai/)
- [Bitcoin Testnet](https://testnet.help/)

---

**Powered by Fetch.ai and Internet Computer | Built for Agentverse**

🚀 Ready to revolutionize Bitcoin operations with AI agents!
