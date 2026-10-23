"""Pydantic schemas for the HR Communication Humanizer API."""

from typing import Any
from pydantic import BaseModel, Field


class HumanizeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Original text to be rewritten.",
    )
    communication_type: str = Field(
        default="general_hr",
        description="Type of HR communication (e.g., candidate_feedback, rejection_email).",
    )
    tone: str = Field(
        default="professional",
        description="Target tone (e.g., professional, friendly, empathetic, concise, formal, neutral).",
    )
    preserve_facts: bool = Field(
        default=True,
        description="Whether to perform layered fact-checking and validation.",
    )
    context_anchor: str | None = Field(
        default=None,
        description="Shared context or persona anchor (e.g. candidate name, role, company tone) to ensure voice consistency.",
    )
    model: str | None = Field(
        default=None,
        description="Model override (optional). Defaults to the configured GoHumanize model.",
    )


class ValidateRequest(BaseModel):
    original_text: str = Field(
        ..., min_length=1, description="The original source text."
    )
    rewritten_text: str = Field(
        ..., min_length=1, description="The rewritten candidate text to validate."
    )


class FactCheckDetails(BaseModel):
    missing_numbers: list[str] = Field(
        default_factory=list, description="Numbers or metrics present in source but missing in rewrite."
    )
    changed_entities: list[str] = Field(
        default_factory=list, description="Key entities or technical terms that may have been altered."
    )
    possible_negation_change: bool = Field(
        default=False, description="Flag indicating potential removal or reversal of negation."
    )
    possible_uncertainty_change: bool = Field(
        default=False, description="Flag indicating potential strengthening of uncertain claims."
    )
    unsupported_judgments: list[str] = Field(
        default_factory=list, description="Subjective or evaluative terms introduced without source evidence."
    )
    speech_act_preserved: bool = Field(
        default=True, description="Whether questions or requests were kept as such."
    )
    checks_summary: dict[str, Any] = Field(
        default_factory=dict, description="Summary counters of the checks executed."
    )


class ValidationResponse(BaseModel):
    passed: bool = Field(
        ..., description="True if all deterministic checks passed and no severe risks were identified."
    )
    requires_review: bool = Field(
        ..., description="True if any discrepancy, hedge shift, or unsupported evaluation was detected."
    )
    confidence_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Heuristic confidence score for factual preservation."
    )
    warnings: list[str] = Field(
        default_factory=list, description="Specific, user-friendly explanations of potential issues."
    )
    details: FactCheckDetails = Field(
        default_factory=FactCheckDetails, description="Detailed diagnostic breakdown."
    )


class FindingItem(BaseModel):
    category: str = Field(..., description="Category of the finding (e.g. Robotic AI Cliche, Stiff Formality, Monotonous Rhythm)")
    phrase: str = Field(..., description="The flagged phrase or pattern")
    explanation: str = Field(..., description="Why this was flagged and how it was refined")


class RoboticAnalysis(BaseModel):
    cliches_detected: list[str] = Field(
        default_factory=list, description="Robotic AI phrases identified in source draft"
    )
    cliches_eliminated: list[str] = Field(
        default_factory=list, description="Robotic phrases successfully eliminated in rewrite"
    )
    sentence_count_before: int = 0
    sentence_count_after: int = 0
    burstiness_score_before: float = 0.0
    burstiness_score_after: float = 0.0
    naturalness_verdict: str = "Enhanced"
    is_already_natural: bool = False
    resistance_note: str = "Applied targeted refinements while preserving factual content."
    findings: list[FindingItem] = Field(default_factory=list, description="Detailed robotic phrasing findings")


class PipelineStages(BaseModel):
    stage_1_input: dict[str, Any] = Field(default_factory=dict, description="AI-Generated Text: raw input, length, words")
    stage_2_intent_facts: dict[str, Any] = Field(default_factory=dict, description="Intent + Facts: entities, numbers, dates, negations, core intent")
    stage_3_style_analysis: dict[str, Any] = Field(default_factory=dict, description="Style Analysis: robotic markers, burstiness, formality, clichés")
    stage_4_contextual_rewrite: dict[str, Any] = Field(default_factory=dict, description="Contextual Rewrite: tone, context adaptation, intensity")
    stage_5_meaning_check: dict[str, Any] = Field(default_factory=dict, description="Meaning Check: deterministic fact checks, negation locks, 0 hallucination verification")
    stage_6_humanized_text: dict[str, Any] = Field(default_factory=dict, description="Humanized Text: final output, certification, changes made")


class EvaluationScorecard(BaseModel):
    naturalness_score: int = Field(default=95, ge=0, le=100, description="Naturalness & human flow (burstiness, de-cliché)")
    meaning_preservation_score: int = Field(default=100, ge=0, le=100, description="Preservation of original intent and factual meaning")
    factuality_score: int = Field(default=100, ge=0, le=100, description="Absence of unsupported claims, hallucinations, or invented evidence")
    contextual_tone_score: int = Field(default=98, ge=0, le=100, description="Adaptation to candidate, recruiter, interview questions, or reports")
    terminology_preservation_score: int = Field(default=100, ge=0, le=100, description="Preservation of technical terms, scores, and names")
    consistency_score: int = Field(default=96, ge=0, le=100, description="Voice coherence across communication context")
    resistance_score: int = Field(default=98, ge=0, le=100, description="Resistance to unnecessary rewriting when text is already natural")
    overall_grade: str = Field(default="A+ Fact-Verified", description="Overall evaluation verdict")
    summary: str = Field(default="All criteria passed with complete factual fidelity.", description="Executive evaluation summary")


class HumanizeResponse(BaseModel):
    original_text: str
    rewritten_text: str
    validation: ValidationResponse
    robotic_analysis: RoboticAnalysis | None = None
    pipeline_stages: PipelineStages | None = None
    evaluation_scorecard: EvaluationScorecard | None = None
    context_anchor: str | None = None
    model: str
    provider: str = Field(
        default="gemini",
        description="Provider that performed rewrite: 'gemini' or 'rule_engine'",
    )
    fallback_used: bool = Field(
        default=False,
        description="Whether fallback to rule engine was triggered",
    )
    fallback_reason: str | None = Field(
        default=None,
        description="Detailed reason if fallback occurred",
    )
    retried: bool = False
    duration_seconds: float


class HealthResponse(BaseModel):
    status: str
    active_model: str = "gemini-3.8-flash"
    gemini_configured: bool = False
    gemini_model: str = "gemini-3.8-flash"
    gemini_rate_limited: bool = False
    cooldown_remaining: int = 0
    workflow: str = "gemini_cloud"
    active_provider: str = "gemini"
    ollama_reachable: bool = False
    model_available: bool = True
    available_models: list[str] = ["gemini-3.8-flash", "gemini-3.8-pro", "gemini-2.5-flash"]


class CommunicationTypeOption(BaseModel):
    id: str
    name: str
    description: str


class ToneOption(BaseModel):
    id: str
    name: str
    description: str


class ConfigResponse(BaseModel):
    default_model: str = "gemini-3.8-flash"
    available_models: list[str] = ["gemini-3.8-flash", "gemini-3.8-pro", "gemini-2.5-flash"]
    communication_types: list[CommunicationTypeOption]
    tones: list[ToneOption]
    max_input_length: int
    gemini_configured: bool = False
    gemini_model: str = "gemini-3.8-flash"
    primary_provider: str = "gemini"
    workflow: str = "gemini_cloud"

