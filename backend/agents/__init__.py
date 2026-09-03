"""
Finance Controller — Agents Package
===================================

Provides the Stage 2 AI Investigator Agent, domain investigation tools,
and candidate explanation output validation routines.
"""

from backend.agents.investigator import InvestigatorAgent
from backend.agents.output_validator import validate_agent_explanation, CandidateExplanationPayload
from backend.agents.tools import (
    FuzzyNameTool,
    ExpandedDateWindowTool,
    ChargebackEvidenceTool,
    MissingInvoiceTool,
    DuplicateDetectorTool,
)

__all__ = [
    "InvestigatorAgent",
    "validate_agent_explanation",
    "CandidateExplanationPayload",
    "FuzzyNameTool",
    "ExpandedDateWindowTool",
    "ChargebackEvidenceTool",
    "MissingInvoiceTool",
    "DuplicateDetectorTool",
]
