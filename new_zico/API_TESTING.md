# Zico Agent API – cURL Testing Guide

This document provides ready-to-use `curl` commands to test the Zico Agent API, covering both crypto and database agents, as well as conversation management endpoints.

---

## 1. Health Check

```bash
curl -X GET "http://localhost:8000/health"
```

---

## 2. Chat Endpoint – Ask the Agents

### a. Ask the Crypto Agent

**Get the price of Bitcoin:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "content": "What is the price of Bitcoin?"
    },
    "user_id": "user123",
    "conversation_id": "crypto-conv-1"
  }'
```

**Get the market cap of Ethereum:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "content": "What is the market cap of Ethereum?"
    },
    "user_id": "user123",
    "conversation_id": "crypto-conv-1"
  }'
```

**Get the floor price of Bored Apes NFT:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "content": "What is the floor price of Bored Apes?"
    },
    "user_id": "user123",
    "conversation_id": "crypto-conv-1"
  }'
```

---

### b. Ask the Database Agent

**Show the top 5 cryptocurrencies by price:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "content": "List me the tables available on the database"
    },
    "user_id": "user123",
    "conversation_id": "conversation_0"
  }'
```

**How many active addresses are there?**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "content": "How many active addresses are there?"
    },
    "user_id": "user123",
    "conversation_id": "db-conv-1"
  }'
```

**List all cryptocurrencies with price above $1000:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "content": "List all cryptocurrencies with price above $1000"
    },
    "user_id": "user123",
    "conversation_id": "db-conv-1"
  }'
```

---

### c. General/Assistant Queries

**Ask a general question:**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "content": "Tell me a joke"
    },
    "user_id": "user123",
    "conversation_id": "general-conv-1"
  }'
```

---

## 3. Conversation Management

**Get all messages from a conversation:**
```bash
curl -X GET "http://localhost:8000/chat/messages?conversation_id=crypto-conv-1&user_id=user123"
```

**Clear all messages in a conversation:**
```bash
curl -X GET "http://localhost:8000/chat/clear?conversation_id=crypto-conv-1&user_id=user123"
```

**Get all conversation IDs for a user:**
```bash
curl -X GET "http://localhost:8000/chat/conversations?user_id=user123"
```

**Get all user IDs:**
```bash
curl -X GET "http://localhost:8000/chat/users"
```

**Create a new conversation for a user:**
```bash
curl -X POST "http://localhost:8000/chat/conversations?user_id=user123"
```

**Delete a conversation:**
```bash
curl -X DELETE "http://localhost:8000/chat/conversations/crypto-conv-1?user_id=user123"
```

---

## 4. Example Response

A typical response from the `/chat` endpoint:
```json
{
  "response": "The current price of Bitcoin is $43,250.50",
  "agent": "crypto_agent"
}
```

---

## 5. Tips

- Change `user_id` and `conversation_id` as needed for your tests.
- For multi-turn conversations, use the same `conversation_id`.
- The `role` in the message should be `"user"` for user questions.

---

Feel free to copy and adapt these queries for your own testing and development! 