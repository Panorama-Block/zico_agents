from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseLanguageModel

from src.models.chatMessage import ChatMessage, AgentResponse, AgentType, MessageRole
from src.agents.config import Config


class BaseAgent(ABC):
    """Base class for all agents in the multi-agent system"""
    
    def __init__(self, name: str, agent_type: AgentType, llm: BaseLanguageModel, description: str = ""):
        self.name = name
        self.agent_type = agent_type
        self.llm = llm
        self.description = description
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Agent state
        self.is_active = True
        self.created_at = datetime.utcnow()
        self.last_used = None
        self.usage_count = 0
        
        # Performance metrics
        self.response_times = []
        self.success_count = 0
        self.error_count = 0
        
        self.logger.info(f"Initialized agent {name} of type {agent_type}")
    
    @abstractmethod
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> AgentResponse:
        """Process a message and return a response"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return list of agent capabilities"""
        pass
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Determine if this agent can handle the given message"""
        # Default implementation - can be overridden by subclasses
        return True
    
    def get_confidence_score(self, message: str, context: Dict[str, Any] = None) -> float:
        """Get confidence score for handling this message (0.0 to 1.0)"""
        # Default implementation - can be overridden by subclasses
        return 0.5
    
    def prepare_context_messages(self, context: Dict[str, Any] = None) -> List[SystemMessage]:
        """Prepare context messages for the LLM"""
        context_messages = []
        
        if context:
            # Add relevant context information
            if context.get("crypto_related"):
                context_messages.append(SystemMessage(
                    content="This conversation involves cryptocurrency-related topics."
                ))
            
            if context.get("user_preferences"):
                context_messages.append(SystemMessage(
                    content=f"User preferences: {context['user_preferences']}"
                ))
            
            if context.get("conversation_history"):
                context_messages.append(SystemMessage(
                    content=f"Previous context: {context['conversation_history']}"
                ))
        
        return context_messages
    
    def create_agent_response(
        self, 
        content: str, 
        success: bool = True, 
        error_message: Optional[str] = None,
        metadata: Dict[str, Any] = None,
        tools_used: List[str] = None,
        next_agent: Optional[str] = None,
        requires_followup: bool = False
    ) -> AgentResponse:
        """Create a standardized agent response"""
        return AgentResponse(
            content=content,
            agent_name=self.name,
            agent_type=self.agent_type,
            success=success,
            error_message=error_message,
            metadata=metadata or {},
            tools_used=tools_used or [],
            next_agent=next_agent,
            requires_followup=requires_followup,
            timestamp=datetime.utcnow()
        )
    
    def update_metrics(self, response_time: float, success: bool):
        """Update agent performance metrics"""
        self.response_times.append(response_time)
        self.last_used = datetime.utcnow()
        self.usage_count += 1
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        # Keep only last 100 response times
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        success_rate = self.success_count / self.usage_count if self.usage_count > 0 else 0
        
        return {
            "name": self.name,
            "agent_type": self.agent_type.value,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "average_response_time": avg_response_time,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_active": self.is_active
        }
    
    def activate(self):
        """Activate the agent"""
        self.is_active = True
        self.logger.info(f"Agent {self.name} activated")
    
    def deactivate(self):
        """Deactivate the agent"""
        self.is_active = False
        self.logger.info(f"Agent {self.name} deactivated")
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.response_times = []
        self.success_count = 0
        self.error_count = 0
        self.usage_count = 0
        self.logger.info(f"Reset metrics for agent {self.name}")
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get comprehensive agent information"""
        return {
            "name": self.name,
            "type": self.agent_type.value,
            "description": self.description,
            "capabilities": self.get_capabilities(),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "performance_metrics": self.get_performance_metrics()
        }


class AgentRegistry:
    """Registry for managing all agents in the system"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent"""
        if agent.name in self.agents:
            self.logger.warning(f"Agent {agent.name} already registered, overwriting")
        
        self.agents[agent.name] = agent
        self.logger.info(f"Registered agent {agent.name}")
    
    def unregister_agent(self, agent_name: str) -> bool:
        """Unregister an agent"""
        if agent_name in self.agents:
            del self.agents[agent_name]
            self.logger.info(f"Unregistered agent {agent_name}")
            return True
        return False
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """Get agent by name"""
        return self.agents.get(agent_name)
    
    def get_active_agents(self) -> List[BaseAgent]:
        """Get all active agents"""
        return [agent for agent in self.agents.values() if agent.is_active]
    
    def get_agents_by_type(self, agent_type: AgentType) -> List[BaseAgent]:
        """Get agents by type"""
        return [agent for agent in self.agents.values() if agent.agent_type == agent_type]
    
    def find_best_agent(self, message: str, context: Dict[str, Any] = None) -> Optional[BaseAgent]:
        """Find the best agent to handle a message"""
        best_agent = None
        best_score = 0.0
        
        for agent in self.get_active_agents():
            if agent.can_handle(message, context):
                confidence = agent.get_confidence_score(message, context)
                if confidence > best_score:
                    best_score = confidence
                    best_agent = agent
        
        return best_agent
    
    def get_all_agents_info(self) -> List[Dict[str, Any]]:
        """Get information about all agents"""
        return [agent.get_agent_info() for agent in self.agents.values()]
    
    def get_agent_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all agents"""
        total_agents = len(self.agents)
        active_agents = len(self.get_active_agents())
        total_usage = sum(agent.usage_count for agent in self.agents.values())
        total_success = sum(agent.success_count for agent in self.agents.values())
        
        return {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "total_usage": total_usage,
            "total_success": total_success,
            "overall_success_rate": total_success / total_usage if total_usage > 0 else 0,
            "agents": self.get_all_agents_info()
        }


# Global agent registry
agent_registry = AgentRegistry() 