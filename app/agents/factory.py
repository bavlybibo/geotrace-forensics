from __future__ import annotations

import os

from .contracts import AgentRequest, AgentResponse, ForensicAgent
from .local_llm_runner import run_local_llm_command
from .rule_based_agent import RuleBasedForensicAgent


class LocalLLMForensicAgent(RuleBasedForensicAgent):
    """Optional local-LLM adapter with deterministic fallback.

    Set GEOTRACE_LOCAL_LLM_COMMAND to a local executable that reads JSON from
    stdin and prints guarded JSON.  GeoTrace never sends evidence to a remote
    provider from this adapter.  If the command is absent, invalid, slow, or
    fails schema validation, the safe rule-based agent remains the source of
    truth and the model warning is appended to the caveats.
    """

    provider_name = "local-llm-command-with-rule-fallback"

    def analyze_evidence(self, request: AgentRequest) -> AgentResponse:
        fallback = super().analyze_evidence(request)
        result = run_local_llm_command(request)
        if result.response is None:
            caveats = list(fallback.caveats)
            for warning in result.warnings[:3]:
                if warning and warning not in caveats:
                    caveats.append(warning)
            return AgentResponse(
                summary=fallback.summary,
                recommended_actions=fallback.recommended_actions,
                caveats=caveats[:8],
                confidence=fallback.confidence,
                provider=self.provider_name + " -> " + fallback.provider,
            )

        # Keep the local LLM conservative by blending it with deterministic
        # safeguards and never letting it overrule lower-confidence evidence.
        actions = list(result.response.recommended_actions)
        for action in fallback.recommended_actions:
            if action not in actions:
                actions.append(action)
        caveats = list(result.response.caveats)
        for caveat in fallback.caveats:
            if caveat not in caveats:
                caveats.append(caveat)
        blended_confidence = min(max(result.response.confidence, 0), max(fallback.confidence + 8, fallback.confidence))
        return AgentResponse(
            summary=result.response.summary,
            recommended_actions=actions[:8],
            caveats=caveats[:8],
            confidence=blended_confidence,
            provider=result.response.provider + " + deterministic-safeguards",
        )


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
    - local_llm: optional local-LLM command adapter with deterministic fallback.
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
