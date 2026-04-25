"""AI-agent extension points for GeoTrace.

The default implementation is deterministic and local. Future cloud/local LLM
adapters should implement the same protocol without changing UI code.
"""

from .contracts import AgentRequest, AgentResponse, ForensicAgent
from .rule_based_agent import RuleBasedForensicAgent
from .factory import LocalLLMForensicAgent, RemoteLLMDisabledAgent, build_forensic_agent

__all__ = ["AgentRequest", "AgentResponse", "ForensicAgent", "RuleBasedForensicAgent", "LocalLLMForensicAgent", "RemoteLLMDisabledAgent", "build_forensic_agent"]
