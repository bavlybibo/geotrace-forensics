from __future__ import annotations

import os

from .contracts import ForensicAgent
from .rule_based_agent import RuleBasedForensicAgent


class LocalLLMForensicAgent(RuleBasedForensicAgent):
    """Optional local-LLM adapter placeholder.

    It intentionally falls back to deterministic local-rule reasoning unless a future
    local model runner is wired in. This keeps evidence offline and avoids hidden network calls.
    """

    provider_name = "local-llm-optional-safe-fallback"


class RemoteLLMDisabledAgent(RuleBasedForensicAgent):
    """Remote LLM adapter guard.

    Remote providers are disabled by default. Enabling them should require explicit
    analyst configuration, evidence-handling policy review, and redaction controls.
    """

    provider_name = "remote-llm-disabled-by-default"

    def __init__(self) -> None:
        if os.getenv("GEOTRACE_REMOTE_LLM_ENABLED", "0").strip() != "1":
            raise RuntimeError("Remote LLM agents are disabled by default. Set GEOTRACE_REMOTE_LLM_ENABLED=1 only after policy approval.")


def build_forensic_agent(provider: str | None = None) -> ForensicAgent:
    """Create the configured forensic agent without changing UI code.

    Supported provider values:
    - local_rule/default: deterministic offline agent.
    - local_llm: optional local-LLM placeholder with safe fallback behavior.
    - remote_llm: blocked unless explicitly enabled by environment policy.
    """
    selected = (provider or os.getenv("GEOTRACE_AGENT_PROVIDER", "local_rule")).strip().lower()
    if selected in {"", "default", "local", "local_rule", "rule"}:
        return RuleBasedForensicAgent()
    if selected in {"local_llm", "local-llm"}:
        return LocalLLMForensicAgent()
    if selected in {"remote_llm", "remote-llm"}:
        return RemoteLLMDisabledAgent()
    raise ValueError(f"Unsupported GeoTrace agent provider: {selected}")
