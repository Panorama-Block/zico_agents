from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langgraph_supervisor import create_supervisor
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import TypedDict, Literal, List, Any, Dict, Optional
import logging

from src.agents.config import Config
from src.models.chatMessage import AgentType, MessageRole

# Agents
from src.agents.crypto_data.agent import CryptoDataAgent

logger = logging.getLogger(__name__)


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class ConversationState(TypedDict):
    """State for LangGraph conversation flow"""
    messages: List[ChatMessage]
    current_agent: Optional[str]
    agent_history: List[Dict[str, Any]]
    context: Dict[str, Any]
    user_id: str
    conversation_id: str


class Supervisor:
    def __init__(self, llm: ChatGoogleGenerativeAI):
        self.llm = llm
        self.embeddings = Config.get_embeddings()
        
        # Initialize agents
        self.crypto_data_agent = CryptoDataAgent(llm)
        
        # Create the supervisor graph
        self.supervisor_graph = self._create_supervisor_graph()
        
        # Compile the graph
        self.app = self.supervisor_graph.compile()

    def _create_supervisor_graph(self) -> StateGraph:
        """Create the LangGraph state graph for supervisor"""
        
        # Define the state graph
        workflow = StateGraph(ConversationState)
        
        # Add nodes for different agents
        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("crypto_agent", self._crypto_agent_node)
        workflow.add_node("general_agent", self._general_agent_node)
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "supervisor",
            self._route_to_agent,
            {
                "crypto_agent": "crypto_agent",
                "general_agent": "general_agent",
                "end": END
            }
        )
        
        # Add edges from agents back to supervisor or end
        workflow.add_edge("crypto_agent", "supervisor")
        workflow.add_edge("general_agent", "supervisor")
        
        # Set entry point
        workflow.set_entry_point("supervisor")
        
        return workflow

    def _supervisor_node(self, state: ConversationState) -> ConversationState:
        """Supervisor node that analyzes the message and determines routing"""
        try:
            # Get the latest user message
            latest_message = state["messages"][-1] if state["messages"] else None
            
            if not latest_message or latest_message["role"] != "user":
                # No user message, end conversation
                return state
            
            # Analyze the message content
            content = latest_message["content"].lower()
            
            # Update context based on message content
            context_updates = {}
            if any(word in content for word in ["bitcoin", "eth", "crypto", "price", "market", "nft", "defi"]):
                context_updates["crypto_related"] = True
            if any(word in content for word in ["hello", "hi", "how are you", "weather", "joke"]):
                context_updates["general_related"] = True
            
            # Update state context
            state["context"].update(context_updates)
            
            # Add supervisor analysis to agent history
            state["agent_history"].append({
                "agent": "supervisor",
                "action": "message_analysis",
                "context_updates": context_updates,
                "timestamp": "now"
            })
            
            return state
            
        except Exception as e:
            logger.error(f"Error in supervisor node: {e}")
            return state

    def _route_to_agent(self, state: ConversationState) -> str:
        """Route to appropriate agent based on message content and context"""
        try:
            latest_message = state["messages"][-1] if state["messages"] else None
            
            if not latest_message:
                return "end"
            
            content = latest_message["content"].lower()
            context = state["context"]
            
            # Check if crypto-related
            if (context.get("crypto_related") or 
                any(word in content for word in ["bitcoin", "eth", "crypto", "price", "market", "nft", "defi", "floor price", "tvl"])):
                return "crypto_agent"
            
            # Check if general conversation
            if (context.get("general_related") or 
                any(word in content for word in ["hello", "hi", "how are you", "weather", "joke", "help"])):
                return "general_agent"
            
            # Default to general agent
            return "general_agent"
            
        except Exception as e:
            logger.error(f"Error in routing: {e}")
            return "general_agent"

    def _crypto_agent_node(self, state: ConversationState) -> ConversationState:
        """Crypto agent node"""
        try:
            # Get the latest user message
            latest_message = state["messages"][-1] if state["messages"] else None
            
            if not latest_message:
                return state
            
            # Convert messages to LangChain format
            langchain_messages = []
            for msg in state["messages"][-5:]:  # Last 5 messages for context
                if msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "system":
                    langchain_messages.append(SystemMessage(content=msg["content"]))
            
            # Add system context
            context_str = ""
            if state["context"].get("crypto_related"):
                context_str = "This is a cryptocurrency-related query. Use appropriate crypto tools."
            
            if context_str:
                langchain_messages.insert(0, SystemMessage(content=context_str))
            
            # Get response from crypto agent
            response = self.crypto_data_agent.agent.invoke({"messages": langchain_messages})
            
            # Add agent response to messages
            agent_message = {
                "role": "assistant",
                "content": response.get("output", "I couldn't process that crypto query."),
                "agent": "crypto_agent"
            }
            state["messages"].append(agent_message)
            
            # Update current agent
            state["current_agent"] = "crypto_agent"
            
            # Add to agent history
            state["agent_history"].append({
                "agent": "crypto_agent",
                "action": "crypto_query_processed",
                "timestamp": "now"
            })
            
            return state
            
        except Exception as e:
            logger.error(f"Error in crypto agent node: {e}")
            # Add error message
            error_message = {
                "role": "assistant",
                "content": "Sorry, I encountered an error processing your crypto query. Please try again.",
                "agent": "crypto_agent"
            }
            state["messages"].append(error_message)
            return state

    def _general_agent_node(self, state: ConversationState) -> ConversationState:
        """General agent node for non-crypto queries"""
        try:
            # Get the latest user message
            latest_message = state["messages"][-1] if state["messages"] else None
            
            if not latest_message:
                return state
            
            # Create a simple response for general queries
            content = latest_message["content"].lower()
            
            if any(word in content for word in ["hello", "hi"]):
                response_content = "Hello! I'm your AI assistant. I can help you with cryptocurrency queries and general questions. What would you like to know?"
            elif any(word in content for word in ["how are you"]):
                response_content = "I'm doing well, thank you for asking! I'm here to help you with your questions."
            elif any(word in content for word in ["weather"]):
                response_content = "I don't have access to real-time weather data, but I can help you with cryptocurrency information and other questions!"
            elif any(word in content for word in ["joke"]):
                response_content = "Why did the cryptocurrency go to therapy? Because it had too many emotional ups and downs! 😄"
            else:
                response_content = "I'm here to help! I specialize in cryptocurrency information, but I can also assist with general questions. What would you like to know?"
            
            # Add agent response to messages
            agent_message = {
                "role": "assistant",
                "content": response_content,
                "agent": "general_agent"
            }
            state["messages"].append(agent_message)
            
            # Update current agent
            state["current_agent"] = "general_agent"
            
            # Add to agent history
            state["agent_history"].append({
                "agent": "general_agent",
                "action": "general_query_processed",
                "timestamp": "now"
            })
            
            return state
            
        except Exception as e:
            logger.error(f"Error in general agent node: {e}")
            # Add error message
            error_message = {
                "role": "assistant",
                "content": "Sorry, I encountered an error. Please try again.",
                "agent": "general_agent"
            }
            state["messages"].append(error_message)
            return state

    def invoke(self, messages: List[ChatMessage], user_id: str = "anonymous", conversation_id: str = "default") -> dict:
        """Invoke the supervisor with messages"""
        try:
            # Prepare initial state
            initial_state: ConversationState = {
                "messages": messages,
                "current_agent": None,
                "agent_history": [],
                "context": {},
                "user_id": user_id,
                "conversation_id": conversation_id
            }
            
            # Run the graph
            result = self.app.invoke(initial_state)
            
            # Extract the final response
            final_messages = result.get("messages", [])
            final_agent = result.get("current_agent", "supervisor")
            
            # Get the last assistant message
            last_assistant_message = None
            for msg in reversed(final_messages):
                if msg["role"] == "assistant":
                    last_assistant_message = msg
                    break
            
            response_content = last_assistant_message["content"] if last_assistant_message else "No response generated"
            
            return {
                "messages": final_messages,
                "agent": final_agent,
                "response": response_content,
                "context": result.get("context", {}),
                "agent_history": result.get("agent_history", [])
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