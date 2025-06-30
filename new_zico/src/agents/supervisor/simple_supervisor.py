import logging
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.config import Config
from src.agents.crypto_data.agent import CryptoDataAgent

logger = logging.getLogger(__name__)


class SimpleSupervisor:
    """Simplified supervisor that routes messages to appropriate agents"""
    
    def __init__(self, llm):
        self.llm = llm
        self.crypto_agent = CryptoDataAgent(llm)
        
    def _is_crypto_query(self, message: str) -> bool:
        """Determine if a message is crypto-related"""
        crypto_keywords = [
            "bitcoin", "eth", "crypto", "price", "market", "nft", "defi", 
            "floor price", "tvl", "token", "coin", "blockchain", "wallet"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in crypto_keywords)
    
    def _get_general_response(self, message: str) -> str:
        """Generate a response for general queries"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["hello", "hi"]):
            return "Hello! I'm your AI assistant. I can help you with cryptocurrency queries and general questions. What would you like to know?"
        elif any(word in message_lower for word in ["how are you"]):
            return "I'm doing well, thank you for asking! I'm here to help you with your questions."
        elif any(word in message_lower for word in ["weather"]):
            return "I don't have access to real-time weather data, but I can help you with cryptocurrency information and other questions!"
        elif any(word in message_lower for word in ["joke"]):
            return "Why did the cryptocurrency go to therapy? Because it had too many emotional ups and downs! 😄"
        else:
            return "I'm here to help! I specialize in cryptocurrency information, but I can also assist with general questions. What would you like to know?"
    
    def invoke(self, messages: List[Dict[str, str]], user_id: str = "anonymous", conversation_id: str = "default") -> Dict[str, Any]:
        """Process messages and route to appropriate agent"""
        try:
            # Get the latest user message
            if not messages:
                return {
                    "messages": messages,
                    "agent": "supervisor",
                    "response": "No messages to process.",
                    "context": {},
                    "agent_history": []
                }
            
            latest_message = messages[-1]
            if latest_message["role"] != "user":
                return {
                    "messages": messages,
                    "agent": "supervisor",
                    "response": "No user message to process.",
                    "context": {},
                    "agent_history": []
                }
            
            user_content = latest_message["content"]
            
            # Determine which agent to use
            if self._is_crypto_query(user_content):
                # Route to crypto agent
                logger.info("Routing to crypto agent")
                
                # Convert messages to LangChain format
                langchain_messages = []
                for msg in messages[-5:]:  # Last 5 messages for context
                    if msg["role"] == "user":
                        langchain_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "system":
                        langchain_messages.append(SystemMessage(content=msg["content"]))
                
                # Add system context
                langchain_messages.insert(0, SystemMessage(
                    content="This is a cryptocurrency-related query. Use appropriate crypto tools."
                ))
                
                # Get response from crypto agent
                try:
                    response = self.crypto_agent.agent.invoke({"messages": langchain_messages})
                    response_content = response.get("output", "I couldn't process that crypto query.")
                except Exception as e:
                    logger.error(f"Error in crypto agent: {e}")
                    response_content = "Sorry, I encountered an error processing your crypto query. Please try again."
                
                # Add response to messages
                messages.append({
                    "role": "assistant",
                    "content": response_content,
                    "agent": "crypto_agent"
                })
                
                return {
                    "messages": messages,
                    "agent": "crypto_agent",
                    "response": response_content,
                    "context": {"crypto_related": True},
                    "agent_history": [{"agent": "crypto_agent", "action": "crypto_query_processed"}]
                }
                
            else:
                # Handle general queries
                logger.info("Handling general query")
                response_content = self._get_general_response(user_content)
                
                # Add response to messages
                messages.append({
                    "role": "assistant",
                    "content": response_content,
                    "agent": "general_agent"
                })
                
                return {
                    "messages": messages,
                    "agent": "general_agent",
                    "response": response_content,
                    "context": {"general_related": True},
                    "agent_history": [{"agent": "general_agent", "action": "general_query_processed"}]
                }
                
        except Exception as e:
            logger.error(f"Error in supervisor invoke: {e}", exc_info=True)
            return {
                "messages": messages,
                "agent": "supervisor",
                "response": "Sorry, I encountered an error processing your request. Please try again.",
                "context": {},
                "agent_history": []
            } 