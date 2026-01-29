time curl -X POST "https://colettogs-zico-agent.hf.space/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "content": "What is avalanche?"
    },
    "user_id": "test_user"
  }'