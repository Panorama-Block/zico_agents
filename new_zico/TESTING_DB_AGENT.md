# Guia de Teste do Database Agent

Este guia mostra como testar o agente de banco de dados do sistema Zico.

## 🚀 Como Testar

### 1. Teste Simples (Recomendado para começar)

```bash
cd new_zico
python test_db_simple.py
```

Este script testa uma consulta básica no database agent.

### 2. Teste Completo

```bash
cd new_zico
python test_db_agent.py
```

Este script testa múltiplas consultas diferentes no database agent.

### 3. Teste via API REST

Primeiro, certifique-se de que o servidor está rodando:

```bash
cd new_zico
python -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

Em outro terminal, execute o teste da API:

```bash
cd new_zico
python test_api.py
```

### 4. Teste Completo com Todos os Cenários

```bash
cd new_zico
python test_database_agent.py
```

Este script testa:
- Ferramentas de banco diretamente
- Agente completo
- Endpoint da API

## 🔧 Pré-requisitos

1. **API Key do Gemini configurada**:
   ```bash
   export GEMINI_API_KEY="sua_chave_aqui"
   ```

2. **Dependências instaladas**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Servidor rodando** (para testes de API):
   ```bash
   python -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
   ```

## 📊 Tipos de Consultas Testadas

### Consultas Básicas
- "Mostre-me os top 5 criptomoedas por preço"
- "Qual é o preço do Bitcoin?"
- "Quantas transações temos na base?"

### Consultas com Agregação
- "Qual é o preço médio do Bitcoin nos últimos 30 dias?"
- "Qual é o volume total de transações hoje?"
- "Qual é a capitalização de mercado total?"

### Consultas Temporais
- "Quantas transações ocorreram ontem?"
- "Mostre-me as transações dos últimos 7 dias"

### Consultas com Filtros
- "Liste todas as criptomoedas com preço acima de $1000"
- "Qual é o preço mais alto e mais baixo do Bitcoin?"

### Consultas NFT
- "Mostre-me o floor price das coleções NFT"
- "Quantos holders existem para cada coleção NFT?"

## 🐛 Solução de Problemas

### Erro: "GEMINI_API_KEY não está configurada"
```bash
export GEMINI_API_KEY="sua_chave_aqui"
```

### Erro: "Não foi possível conectar à API"
Certifique-se de que o servidor está rodando:
```bash
python -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
```

### Erro: "ModuleNotFoundError"
Certifique-se de estar no diretório correto:
```bash
cd new_zico
```

### Erro: "Could not connect to ClickHouse database"
Isso é normal! O sistema usa dados mock quando o banco não está disponível.

## 📈 Interpretando os Resultados

### Respostas Esperadas

1. **Consulta bem-sucedida**:
   ```
   ✅ Resposta: Mock result for query: SELECT name, price FROM crypto_prices LIMIT 5
   bitcoin,50000
   ethereum,3000
   cardano,1.50
   ```

2. **Erro de consulta**:
   ```
   ❌ Erro: ERROR: Cannot answer this question with available data
   ```

3. **Consulta perigosa rejeitada**:
   ```
   ❌ Erro: Error: Generated SQL query contains potentially dangerous operations
   ```

### Logs de Debug

O sistema gera logs detalhados:
- `Processing query: [consulta]`
- `Generated SQL: [sql_gerado]`
- `Query result: [resultado]`

## 🔍 Testes Unitários

Para executar os testes unitários:

```bash
cd new_zico
pytest tests/unit/test_database_tools.py -v
```

## 📝 Exemplos de Uso

### Via cURL

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Mostre-me os top 5 criptomoedas por preço"
      }
    ]
  }'
```

### Via Python

```python
import requests

response = requests.post("http://localhost:8000/chat", json={
    "messages": [
        {
            "role": "user",
            "content": "Qual é o preço do Bitcoin?"
        }
    ]
})

print(response.json())
```

## 🎯 Próximos Passos

1. Configure um banco ClickHouse real para dados reais
2. Adicione mais tipos de consultas
3. Implemente cache para consultas frequentes
4. Adicione autenticação e autorização
5. Implemente rate limiting

## 📞 Suporte

Se encontrar problemas:
1. Verifique os logs do servidor
2. Confirme se a API key está configurada
3. Teste com consultas simples primeiro
4. Verifique se todas as dependências estão instaladas 