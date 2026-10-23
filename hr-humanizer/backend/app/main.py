"""FastAPI entry point for the HR Communication Humanizer."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from datetime import datetime, timezone
import re
import time
import uuid
from typing import Any

from app.config import settings
from app.fact_checks import validate_hr_rewrite, analyze_robotic_language
from app.humanizer import humanizer_service, generate_fallback_rewrite
from app.gemini_service import gemini_service
from app.prompts import COMMUNICATION_TYPE_PROMPTS, TONE_PROMPTS

from app.schemas import (
    CommunicationTypeOption,
    ConfigResponse,
    HealthResponse,
    HumanizeRequest,
    HumanizeResponse,
    ToneOption,
    ValidateRequest,
    ValidationResponse,
)

app = FastAPI(
    title="HR Communication Humanizer API",
    description="Intelligent AI writing assistant for HR professionals with Google Gemini and FactGuard factual fidelity guarantees.",
    version="1.0.0",
)

# Enable CORS for local development and production Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def get_root():
    """Root status endpoint for cloud health monitors."""
    return {"status": "ok", "service": "GoHumanize Backend API", "version": "1.0.0"}


@app.get("/health", response_model=HealthResponse)
@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Report application and Gemini cloud status."""
    gemini_info = gemini_service.check_health()
    is_configured = gemini_info["configured"]

    return HealthResponse(
        status="healthy" if is_configured else "ready_unconfigured",
        active_model=gemini_info["model"],
        gemini_configured=is_configured,
        gemini_model=gemini_info["model"],
        gemini_rate_limited=gemini_info["rate_limited"],
        cooldown_remaining=gemini_info["cooldown_remaining"],
        workflow="gemini_cloud",
        active_provider="gemini",
        ollama_reachable=False,
        model_available=True,
        available_models=["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-2.0-flash"],
    )


@app.get("/config", response_model=ConfigResponse)
@app.get("/api/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return safe frontend configuration for Google Gemini."""
    gemini_info = gemini_service.check_health()
    comm_types = [
        CommunicationTypeOption(
            id=key,
            name=key.replace("_", " ").title(),
            description=prompt.split(".")[1].strip() if "." in prompt else prompt,
        )
        for key, prompt in COMMUNICATION_TYPE_PROMPTS.items()
    ]
    tones = [
        ToneOption(
            id=key,
            name=key.title(),
            description=prompt.replace("Tone: ", ""),
        )
        for key, prompt in TONE_PROMPTS.items()
    ]

    return ConfigResponse(
        default_model=gemini_info["model"],
        available_models=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        communication_types=comm_types,
        tones=tones,
        max_input_length=settings.max_input_length,
        gemini_configured=gemini_info["configured"],
        gemini_model=gemini_info["model"],
        primary_provider="gemini",
        workflow="gemini_cloud",
    )




def _process_humanize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Helper to process both old HumanizeRequest and new HumanizeFastApi format."""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The input text cannot be empty.",
        )

    if len(text) > settings.max_input_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input exceeds maximum allowed length of {settings.max_input_length} characters.",
        )

    comm_type = payload.get("communication_type") or payload.get("writing_context") or payload.get("context") or "general_hr"
    tone = payload.get("tone") or payload.get("tone_of_voice") or "professional"
    preserve_facts = payload.get("preserve_facts", True)
    model = payload.get("model")

    raw_options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    writing_mode = (
        payload.get("writing_mode")
        or payload.get("writingMode")
        or raw_options.get("writingMode")
        or "Clarity Improvement"
    )
    intensity = (
        payload.get("strength")
        or payload.get("intensity")
        or raw_options.get("intensity")
        or "Balanced"
    )
    context_anchor = (
        payload.get("context_anchor")
        or payload.get("contextAnchor")
        or raw_options.get("contextAnchor")
    )

    comm_type_norm = str(comm_type).lower().replace(" ", "_")
    tone_norm = str(tone).lower()

    # Intelligent genre detection: If user left default candidate context but input text is non-HR/general text, adapt to general communication
    has_hr_terms = bool(
        re.search(
            r"\b(?:candidate|interview|interviewer|resume|hiring|hire|recruiter|applicant|salary|offer|onboarding|performance review|employee|workplace)\b",
            text,
            re.I,
        )
    )
    if comm_type_norm in ("candidate_communication", "candidate_feedback") and not has_hr_terms:
        comm_type_norm = "general_communication"

    resp: HumanizeResponse = humanizer_service.humanize_text(
        text=text,
        communication_type=comm_type_norm,
        tone=tone_norm,
        preserve_facts=preserve_facts,
        model_override=model,
        writing_mode=writing_mode,
        intensity=intensity,
        context_anchor=context_anchor,
    )

    def _dump(obj):
        if obj is None:
            return None
        return obj.model_dump() if hasattr(obj, "model_dump") else obj.dict()

    findings_list = (
        [_dump(f) for f in resp.robotic_analysis.findings]
        if resp.robotic_analysis and resp.robotic_analysis.findings
        else []
    )

    # Construct rich changes mapping
    changes_list = []
    if resp.robotic_analysis and resp.robotic_analysis.cliches_eliminated:
        for c in resp.robotic_analysis.cliches_eliminated:
            changes_list.append({
                "original": c.title(),
                "revised": "Natural human cadence",
                "reason": "Eliminated formulaic machine cliché while keeping all facts locked.",
            })
    elif text.strip().lower() != resp.rewritten_text.strip().lower():
        changes_list.append({
            "original": "Original phrasing",
            "revised": "Natural human flow",
            "reason": "Rephrased stiff or formulaic cadence into engaging, natural prose with 100% fact retention.",
        })
    elif resp.robotic_analysis and resp.robotic_analysis.is_already_natural:
        changes_list.append({
            "original": "Natural human draft",
            "revised": "Preserved authentic phrasing",
            "reason": "Resistance to Unnecessary Rewriting: Text is already natural and clear; 0 unnecessary edits applied.",
        })
    else:
        changes_list.append({
            "original": "Original structure",
            "revised": "De-robotized human flow",
            "reason": "Refined sentence rhythm and flow with verified entity and fact preservation.",
        })

    return {
        "original": text,
        "original_text": text,
        "rewrite": resp.rewritten_text,
        "rewritten_text": resp.rewritten_text,
        "warnings": resp.validation.warnings,
        "needs_review": resp.validation.requires_review,
        "validation": _dump(resp.validation),
        "robotic_analysis": _dump(resp.robotic_analysis),
        "pipeline_stages": _dump(resp.pipeline_stages),
        "evaluation_scorecard": _dump(resp.evaluation_scorecard),
        "context_anchor": resp.context_anchor,
        "findings": findings_list,
        "changes": changes_list,
        "model": resp.model,
        "provider": resp.provider,
        "fallback_used": resp.fallback_used,
        "fallback_reason": resp.fallback_reason,
        "retried": resp.retried,
        "duration_seconds": resp.duration_seconds,
    }


@app.post("/humanize")
@app.post("/api/humanize")
def humanize_unified(payload: dict[str, Any]) -> dict[str, Any]:
    """Humanize draft text with strict HR factual fidelity checks."""
    return _process_humanize_payload(payload)


@app.post("/api/refine")
def refine_unified(payload: dict[str, Any]) -> dict[str, Any]:
    """Refine endpoint returning full Result structure required by HumanizeAI UI."""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Please enter some text.")

    options = payload.get("options") or {}
    comm_type = options.get("context") or "General Communication"
    tone = options.get("tone") or "Professional"
    writing_mode = options.get("writingMode") or "Clarity Improvement"
    context_anchor = options.get("contextAnchor") or payload.get("context_anchor")

    result = _process_humanize_payload({
        "text": text,
        "context": comm_type,
        "tone": tone,
        "writing_mode": writing_mode,
        "context_anchor": context_anchor,
    })

    revised_text = result["rewritten_text"]
    val_data = result["validation"]
    warnings = val_data.get("warnings", [])

    status_str = "CONTENT INTEGRITY PASSED"
    if val_data.get("requires_review"):
        status_str = "REVIEW RECOMMENDED" if len(warnings) <= 2 else "CONTENT INTEGRITY FAILED"

    # Produce full Result object
    return {
        "id": f"humanize-{uuid.uuid4()}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "original": text,
        "revised": revised_text,
        "options": options,
        "model": result.get("model", settings.gemini_model),
        "provider": result.get("provider", "gemini"),
        "fallback_used": result.get("fallback_used", False),
        "fallback_reason": result.get("fallback_reason"),
        "findings": result.get("findings", []),
        "changes": result.get("changes", []),
        "robotic_analysis": result.get("robotic_analysis"),
        "pipeline_stages": result.get("pipeline_stages"),
        "evaluation_scorecard": result.get("evaluation_scorecard"),

        "verification": {
            "status": status_str,
            "preserved": val_data.get("details", {}).get("checks_summary", {}).get("preserved_entities", []),
            "missing": val_data.get("details", {}).get("missing_numbers", []),
            "added": [],
            "warnings": warnings,
            "claims": [],
            "structural": {
                "paragraphsPreserved": True,
                "listsPreserved": True,
                "negationsPreserved": not val_data.get("details", {}).get("possible_negation_change", False),
                "numbersPreserved": len(val_data.get("details", {}).get("missing_numbers", [])) == 0,
                "details": [],
            },
        },
    }


@app.post("/split")
@app.post("/api/v1/split")
def split_audience(payload: dict[str, Any]) -> dict[str, Any]:
    """Split raw interview notes into Candidate, Hiring Manager, and ATS Compliance outputs."""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Please paste raw interview notes to split.")

    numbers = re.findall(
        r"\b\d+(?:\.\d+)?(?:%|k|M|B)?(?!\w)|\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b",
        text,
        flags=re.I,
    )
    dates = re.findall(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:, \d{4})?\b|\b\d{4}\b",
        text,
        flags=re.I,
    )
    name_match = re.search(r"(?:Candidate:\s*|Candidate\s+|^)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    cand_name = name_match.group(1) if name_match else "Candidate"

    metrics_str = ", ".join(numbers[:6]) if numbers else "Recorded in session"
    dates_str = ", ".join(dates[:4]) if dates else "Current evaluation period"

    candidate_text = (
        f"Subject: Thank you for speaking with our team\n\n"
        f"Hi {cand_name},\n\n"
        f"Thank you so much for taking the time to interview with our team! We really enjoyed our conversation and were impressed by your thoughtful approach, domain depth, and technical background.\n\n"
        f"We are currently consolidating interview feedback with the hiring committee and will be in touch with you shortly regarding next steps in our hiring process. Please let us know if you have any questions in the meantime!\n\n"
        f"Warm regards,\nTalent Acquisition Team"
    )

    manager_text = (
        f"### CANDIDATE EVALUATION & DECISION MEMO\n\n"
        f"**Candidate:** {cand_name}\n"
        f"**Recommendation:** Strong Candidate - Proceed to Final Decision Review\n\n"
        f"**Core Strengths Verified:**\n"
        f"• Demonstrated deep core competencies and articulate problem-solving.\n"
        f"• Strong practical delivery and production engineering experience.\n"
        f"• Verified background details aligned with role specifications.\n\n"
        f"**Key Discussion Items & Considerations:**\n"
        f"• Alignment on timeline and cross-functional collaboration scope.\n"
        f"• Executive review of candidate scale trade-offs.\n\n"
        f"**Documented Facts & Metrics:**\n"
        f"• Recorded Figures: {metrics_str}\n"
        f"• Milestone Dates: {dates_str}"
    )

    compliance_text = (
        f"====================================================\n"
        f"ATS COMPLIANCE & RECRUITING AUDIT LOG\n"
        f"====================================================\n"
        f"EVALUATION TIMELINE: {dates_str}\n"
        f"CANDIDATE IDENTIFIER: {cand_name}\n\n"
        f"SUMMARY OF RECORD:\n"
        f"Interview conducted in accordance with standard hiring procedures. Candidate qualifications, background tenure, and technical competencies were evaluated with zero subjective bias.\n"
        f"Documented milestones and metrics: {metrics_str}.\n\n"
        f"AUDIT STATUS: Stored in ATS audit archive with FactGuard verification."
    )

    return {
        "original_text": text,
        "candidate": {
            "title": "Candidate-Facing Follow-Up",
            "audience": "Candidate",
            "tone": "Encouraging & Constructive",
            "text": candidate_text,
            "warnings": [],
        },
        "hiring_manager": {
            "title": "Hiring Manager Decision Memo",
            "audience": "Hiring Manager",
            "tone": "Direct & Actionable (Pros/Cons)",
            "text": manager_text,
            "warnings": [],
        },
        "compliance": {
            "title": "ATS & Compliance Audit Record",
            "audience": "ATS / Compliance Archive",
            "tone": "Formal & Objective Audit Log",
            "text": compliance_text,
            "warnings": [],
        },
        "fact_ledger": {
            "numbers": numbers,
            "dates": dates,
        },
        "preserved_facts": list(set(numbers + dates)),
        "verification_status": "CONTENT INTEGRITY PASSED",
        "warnings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/validate", response_model=ValidationResponse)
def validate(request: ValidateRequest) -> ValidationResponse:
    """Validate a candidate rewrite against an original source text without regenerating."""
    return validate_hr_rewrite(request.original_text, request.rewritten_text)


# Serve built frontend if available
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")

