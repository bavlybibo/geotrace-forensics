from __future__ import annotations

"""Backward-compatible import wrapper for the refactored AI package."""

from .ai import AI_PROVIDER_NAME, BatchAIFinding, case_level_summary, run_ai_batch_assessment

__all__ = ["AI_PROVIDER_NAME", "BatchAIFinding", "case_level_summary", "run_ai_batch_assessment"]
