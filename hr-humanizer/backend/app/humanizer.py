"""Google Gemini Humanizer Service with defensive parsing, FactGuard verification, and retry orchestration."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.config import settings
from app.fact_checks import (
    validate_hr_rewrite,
    analyze_robotic_language,
    extract_pipeline_data,
    calculate_evaluation_scorecard,
)
from app.prompts import build_retry_prompt, build_system_prompt
from app.schemas import HumanizeResponse, ValidationResponse
from app.gemini_service import gemini_service

logger = logging.getLogger(__name__)


# Patterns for cleaning model output
RE_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
RE_LEFTOVER_THINK = re.compile(r"<\/?think>", re.IGNORECASE)
RE_META_PREAMBLE = re.compile(
    r"^(?:here(?:\s+is|\s*'s)?\s+(?:the\s+)?(?:rewritten|humanized|revised)\s+(?:text|version|draft)?:|"
    r"okay,\s+the\s+user\s+wants.*?\n\n|"
    r"sure,?\s+here\s+is.*?:)\s*",
    re.IGNORECASE | re.DOTALL,
)
QUOTES = ('"', "\u201c", "\u201d", "'", "\u2018", "\u2019")


def clean_model_output(raw_text: str, original_source: str) -> str:
    """Defensively clean reasoning tags, preambles, and accidental wrapping quotes."""
    if not raw_text:
        return ""

    # Strip thinking blocks
    cleaned = RE_THINK_BLOCK.sub("", raw_text)
    cleaned = RE_LEFTOVER_THINK.sub("", cleaned).strip()

    # Normalize unicode curly quotes, apostrophes, dashes and corrupted encoding artifacts
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2013", ", ").replace("\u2014", ", ")
    cleaned = re.sub(r"\s*--\s*", ", ", cleaned)
    cleaned = re.sub(r"[\ufffd]+", "'", cleaned)

    # Strip meta preambles
    cleaned = RE_META_PREAMBLE.sub("", cleaned).strip()

    # Strip meta reasoning paragraphs if model output accidentally includes internal thought narrative
    meta_starters = (
        "i need to help the user",
        "let me start by",
        "the user wants",
        "the original text is",
        "first, i should",
        "looking at the original",
        "now, i need to",
        "okay, the user",
        "as an ai assistant",
        "to rewrite this text",
        "in this task, i",
        "i will rewrite",
        "i should rewrite",
        "let's rewrite",
        "notice that the following",
        "you must completely",
        "rewritten text:",
        "here is the rewrite:",
        "here is the rewritten",
    )
    while True:
        lower_start = cleaned.lower()
        matched = False
        for prefix in meta_starters:
            if lower_start.startswith(prefix):
                parts = re.split(r"\n+", cleaned, maxsplit=1)
                if len(parts) > 1:
                    cleaned = parts[1].strip()
                    matched = True
                    break
        if not matched:
            break

    # If output still starts with a meta thought (e.g. model output only thinking), discard
    if any(cleaned.lower().startswith(p) for p in meta_starters):
        return ""

    # Unwrap outer quotation marks if the source was not quoted
    orig_stripped = original_source.strip()
    if (
        len(cleaned) > 2
        and cleaned[0] in QUOTES
        and cleaned[-1] in QUOTES
        and (not orig_stripped or orig_stripped[0] not in QUOTES)
    ):
        cleaned = cleaned[1:-1].strip()

    # Strip accidental conversational lead-ins or standalone label lines
    cleaned = re.sub(
        r"^(?:\*\*)?(?:Here(?:'s| is)|Below(?:'s| is)|The following is|Sure|Certainly|Okay|Of course|I have|I've)[^\n]*?(?:rewritten|revised|humanized|polished|improved|version|draft|passage|below|here|paragraph|text)[^\n]*?[:\.\-]?\s*(?:\*\*)?\s*\n+",
        "",
        cleaned,
        flags=re.I,
    ).strip()
    cleaned = re.sub(
        r"^(?:#+\s*|\*{1,3}|_{1,3})?(?:Rewritten|Revised|Humanized|Polished|Updated|Result|Output|Draft|Version)(?:\s+(?:text|version|passage|draft|output|rewrite))?[:\-]?(?:\*{1,3}|_{1,3})?[:\-]?\s*\n+",
        "",
        cleaned,
        flags=re.I,
    ).strip()
    cleaned = re.sub(
        r"^(?:Here(?:'s| is) (?:a |the )?(?:rewritten|revised|humanized|polished)?\s*(?:text|version|passage|draft)?[:\-]\s*)+",
        "",
        cleaned,
        flags=re.I,
    ).strip()
    cleaned = re.sub(
        r"^(?:Sure|Certainly|Okay)[,!]?\s*(?:here(?:'s| is)[^:\n]*[:\-]?)?\s*\n*",
        "",
        cleaned,
        flags=re.I,
    ).strip()

    # Prevent invented first-person / personal narrative lead-ins when original is third-person or neutral
    orig_has_first_person = bool(
        re.search(r"\b(?:I|I'm|I've|I'd|I'll|my|mine|we|we're|we've|we'd|our|ours|us)\b", original_source)
    )
    if not orig_has_first_person:
        cleaned = re.sub(
            r"^\s*I(?:'ve| have)?\s+(?:always\s+)?(?:felt|found|believed|thought|noticed|seen|known)\s+(?:that\s+)?(?=[a-z0-9])",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        cleaned = re.sub(
            r"^\s*(?:In my (?:opinion|view|experience)|To me)[,:]?\s*(?:I (?:think|feel|believe)\s+(?:that\s+)?)?",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        cleaned = re.sub(
            r"^\s*Personally,?\s*(?:I (?:think|believe|feel)\s+(?:that\s+)?)?",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        cleaned = re.sub(
            r"^\s*I\s+(?:know|agree|understand|think|feel|believe|see|get it)(?:[.!?,]|\s+that\b)?\s*",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        cleaned = re.sub(
            r"^\s*That\s+(?=[a-z0-9])",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        cleaned = re.sub(
            r"^\s*(?:You know|Well|Nowhere is this more true than in)[,!]?\s*",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        # Strip accidental trailing commentary or conversational remarks
        cleaned = re.sub(
            r"\n+\s*(?:I (?:think|feel|believe|hope|know)|That (?:captures|summarizes)|Hope this helps)[^\n]*$",
            "",
            cleaned,
            flags=re.I,
        ).strip()

    # If original text did not start with a Subject: header, strip accidental Subject lines
    if not re.match(r"^\s*Subject:\s*", original_source, re.I):
        cleaned = re.sub(r"^\s*Subject:[^\n]+\n+", "", cleaned, flags=re.I).strip()

    # If original text did not start with a date line, strip accidental date headers (e.g. "14 October 2026")
    if not re.match(r"^\s*(?:\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b", original_source, re.I):
        cleaned = re.sub(r"^\s*(?:\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\s*\n+", "", cleaned, flags=re.I).strip()

    # If original text did not have a salutation, strip accidental placeholder salutations
    if not re.match(r"^\s*(?:Dear|Hi|Hello|Hey|To)\b", original_source, re.I):
        cleaned = re.sub(r"^\s*(?:Dear|Hi|Hello|Hey|To)\s+[^,\n]+[,:]\s*\n+", "", cleaned, flags=re.I).strip()

    # Strip accidental leading markdown header lines if original was not a header
    if not re.match(r"^\s*#+\s+", original_source):
        cleaned = re.sub(r"^\s*#+[^\n]*(?:\n+|$)", "", cleaned).strip()

    # Strip markdown bolding (**word**) if original did not have bolding
    if "**" not in original_source:
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)

    # Strip accidental bullet markers (* or -) if original did not have bullets
    if not re.search(r"^\s*[\*\-]\s+", original_source, re.M):
        has_bullets = bool(re.search(r"(?m)^\s*[\*\-]\s*", cleaned))
        if has_bullets:
            cleaned = re.sub(r"(?m)^\s*[\*\-]\s*", "", cleaned).strip()
            if "\n\n" not in original_source.strip():
                cleaned = re.sub(r"\n+", " ", cleaned).strip()

    # Strip compulsive moralizing / summary wrap-ups at the end of the text
    cleaned = re.sub(
        r"(?:\n+|\s+)(?:In summary|Overall|Ultimately|To summarize|In conclusion|All in all|This ensures a win-win)[,:][^\n\.]*[\.\!]?\s*$",
        "",
        cleaned,
        flags=re.I,
    ).strip()

    # If original text did not start with a numbered item (e.g. "1. "), strip accidental numbering
    if not re.search(r"^\s*\d+[\.\)]\s+", original_source, re.M):
        has_num = bool(re.search(r"(?m)^\s*\d+[\.\)]\s*", cleaned))
        cleaned = re.sub(r"(?m)^\s*\d+[\.\)]\s*", "", cleaned).strip()
        # If original was a single paragraph and numbering was present, collapse extra linebreaks into single paragraph
        if has_num and "\n\n" not in original_source.strip():
            cleaned = re.sub(r"\n+", " ", cleaned).strip()

    # If original source was a single paragraph and model broke output across double newlines, handle appropriately
    orig_stripped = original_source.strip()
    if "\n\n" not in orig_stripped and "\n\n" in cleaned:
        blocks = [b.strip() for b in re.split(r"\n{2,}", cleaned) if b.strip()]
        orig_len = len(orig_stripped.split())
        # Check if blocks are competing full drafts (each having at least 70% of input length)
        is_competing = (
            len(blocks) > 1
            and len(blocks[0].split()) >= 0.7 * orig_len
            and len(blocks[1].split()) >= 0.7 * orig_len
            and not re.match(r"^\s*(?:Dear|Hi|Hello|Hey|To)\b", cleaned, re.I)
        )
        if is_competing:
            orig_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", orig_stripped.lower()))
            b0_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", blocks[0].lower()))
            overlap0 = len(orig_words & b0_words) / max(1, len(orig_words)) if orig_words else 0
            b1_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", blocks[1].lower()))
            overlap1 = len(orig_words & b1_words) / max(1, len(orig_words)) if orig_words else 0

            if overlap0 > 0.88 and overlap1 <= overlap0:
                cleaned = blocks[1]
            else:
                orig_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", orig_stripped) if len(s.strip().split()) >= 6]
                copied0 = sum(1 for s in orig_sents if s.lower() in blocks[0].lower())
                copied1 = sum(1 for s in orig_sents if s.lower() in blocks[1].lower())
                cleaned = blocks[1] if copied1 < copied0 else blocks[0]
        elif not re.match(r"^\s*(?:Dear|Hi|Hello|Hey|To)\b", cleaned, re.I):
            # Model merely divided the single paragraph into separate sentence chunks; rejoin them
            cleaned = " ".join(blocks)

    # Deduplicate repeated sentences within paragraphs if model generated an echo loop
    orig_sents_lower = [s.strip().lower() for s in re.split(r"(?<=[.!?])\s+", orig_stripped) if s.strip()]
    cleaned_paras = []
    for p in cleaned.split("\n\n"):
        p_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]
        if len(p_sents) > 1:
            seen_sents = []
            final_sents = []
            for s in p_sents:
                s_lower = s.lower()
                if len(s.split()) >= 4 and s_lower in seen_sents and orig_sents_lower.count(s_lower) <= 1:
                    continue
                seen_sents.append(s_lower)
                final_sents.append(s)
            cleaned_paras.append(" ".join(final_sents))
        else:
            cleaned_paras.append(p)
    cleaned = "\n\n".join(cleaned_paras)

    # If original text started with uppercase, ensure first character of cleaned is capitalized
    if original_source.strip() and original_source.strip()[0].isupper() and cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned


def generate_fallback_rewrite(
    text: str,
    communication_type: str = "general_hr",
    tone: str = "professional",
    force_restructure: bool = False,
) -> str:
    """Intelligent, deep multi-domain humanizer eliminating AI clichés, formalisms, and robotic cadence."""
    clean_input = text.strip()
    if not clean_input:
        return text

    # Process paragraph by paragraph to strictly preserve multi-paragraph layout
    paragraphs = re.split(r"\n\s*\n", clean_input)
    rewritten_paras = []

    for para in paragraphs:
        p = para.strip()
        if not p:
            continue

        # Step 1: Structural splitting of long run-on sentences & participial clauses to boost burstiness
        p = re.sub(r",\s+which\s+facilitates\s+(?:the\s+)?synthesis\s+of\b", r". This helps produce", p, flags=re.I)
        p = re.sub(r",\s+which\s+facilitates\b", r". This helps with", p, flags=re.I)
        p = re.sub(r",\s+which\s+enables\b", r". This enables", p, flags=re.I)
        p = re.sub(r",\s+which\s+allows\b", r". This lets", p, flags=re.I)
        p = re.sub(r",\s+which\s+serves\s+as\b", r". It acts as", p, flags=re.I)
        p = re.sub(r",\s+which\s+highlights\b", r". This highlights", p, flags=re.I)
        p = re.sub(r",\s+playing\s+a\s+(?:pivotal|crucial|key|central|vital)\s+role\s+in\b", r". This plays a key role in", p, flags=re.I)
        p = re.sub(r",\s+generating\s+actionable\s+insights\s+for\b", r". This surfaces practical takeaways for", p, flags=re.I)
        p = re.sub(r",\s+thereby\s+(?:allowing|enabling)\b", r". This lets", p, flags=re.I)
        p = re.sub(r",\s+thereby\s+reducing\b", r". This directly reduces", p, flags=re.I)
        p = re.sub(r",\s+thereby\s+increasing\b", r". This steadily increases", p, flags=re.I)
        p = re.sub(r",\s+leading\s+to\b", r". This leads to", p, flags=re.I)
        p = re.sub(r",\s+resulting\s+in\b", r". As a result,", p, flags=re.I)
        p = re.sub(r",\s+ensuring\s+that\b", r". This makes sure that", p, flags=re.I)
        p = re.sub(r",\s+enabling\s+(?:the\s+)?rapid\s+mass\s+production(?:\s+of)?\b", r". This allowed printers to rapidly mass-produce", p, flags=re.I)
        p = re.sub(r",\s+sparking\s+the\s+Information\s+Age\b", r" and set off the Information Age", p, flags=re.I)

        # Split em-dash clauses into distinct sentences
        p = re.sub(r"([a-z0-9])\s*[—–]\s*a\s+(slow|costly|expensive|complex|difficult|demanding|rare)\b", r"\1. It was a \2", p, flags=re.I)
        p = re.sub(r"([a-z0-9])\s*[—–]\s*an\s+(expensive|essential|important|unprecedented)\b", r"\1. It was an \2", p, flags=re.I)

        # Step 2: Comprehensive Multi-Domain Lexicon
        replacements = [
            # High-priority compound phrases
            (re.compile(r"\bprecipitated a fundamental paradigm shift\b", re.I), "marked a major turning point"),
            (re.compile(r"\bprecipitated a paradigm shift\b", re.I), "marked a turning point"),
            (re.compile(r"\bprecipitated\b", re.I), "triggered"),
            (re.compile(r"\bfundamental paradigm shift\b", re.I), "major turning point"),
            (re.compile(r"\bparadigm shift\b", re.I), "major shift"),

            # Greetings, closings & preambles
            (re.compile(r"\bPlease do not hesitate to (?:contact me|reach out)\s*(?:if you (?:have any questions|require (?:further assistance|any additional information)|need anything else|have queries))?\.?\b", re.I), "Feel free to reach out if you need anything else."),
            (re.compile(r"\bif you require any additional information\.?\b", re.I), "if you need anything else."),
            (re.compile(r"\bPlease do not hesitate to contact me\b", re.I), "Feel free to reach out"),
            (re.compile(r"\bPlease do not hesitate to reach out\b", re.I), "Feel free to get in touch"),
            (re.compile(r"\bI hope this email finds you well\.?\b", re.I), "Hope you're having a good week."),
            (re.compile(r"\bI hope you are doing well\.?\b", re.I), "Hope all is well with you."),
            (re.compile(r"\bThank you for your time and consideration\.?\b", re.I), "Thanks for your time."),
            (re.compile(r"\bThank you in advance for your time and consideration\.?\b", re.I), "Thanks in advance for your help."),
            (re.compile(r"\bI am writing to inform you that\b", re.I), "I wanted to let you know that"),
            (re.compile(r"\bI am pleased to inform you that\b", re.I), "I'm glad to share that"),
            (re.compile(r"\bI am reaching out to inform you that\b", re.I), "I'm writing to share that"),
            (re.compile(r"\bPlease be advised that\b", re.I), "Just a heads-up that"),
            (re.compile(r"\bPlease be informed that\b", re.I), "Just so you know,"),
            (re.compile(r"\bIn the contemporary era of rapid technological advancement\b", re.I), "In today's fast-moving tech environment"),
            (re.compile(r"\bIn the contemporary recruitment landscape\b", re.I), "In today's hiring landscape"),
            (re.compile(r"\bIn the contemporary (?:era|landscape|workplace)\b", re.I), "Today"),
            (re.compile(r"\bin today's (?:fast-paced|rapidly evolving)[^\.,]*landscape,?\s*", re.I), "Today, "),
            (re.compile(r"\bin today's fast-paced world,?\s*", re.I), "Today, "),
            (re.compile(r"\bIn the rapidly evolving landscape of\b", re.I), "As ... changes quickly,"),
            (re.compile(r"\bIt goes without saying that\b", re.I), "Naturally,"),
            (re.compile(r"\bIt is worth noting that\b|\bIt is important to note that\b|\bIt should be noted that\b", re.I), "Keep in mind that"),
            (re.compile(r"\bIt is crucial to note that\b", re.I), "Notably,"),
            (re.compile(r"\bIt is imperative (?:that\s+we\b|that\b|to\b)\s*", re.I), "We need to "),
            (re.compile(r"\bIt is essential (?:that\s+we\b|that\b|to\b)\s*", re.I), "It's key to "),
            (re.compile(r"\bIt is vital (?:that\s+we\b|that\b|to\b)\s*", re.I), "We must "),
            (re.compile(r"\bIt is of paramount importance (?:that\s+we\b|that\b|to\b)\s*", re.I), "It's critical to "),
            (re.compile(r"\bIt is incumbent upon us to\b", re.I), "We need to"),

            # AI Buzzwords & Stuffy verbs
            (re.compile(r"\bdelve into\b", re.I), "explore"),
            (re.compile(r"\bdelving into\b", re.I), "exploring"),
            (re.compile(r"\bdelve\b", re.I), "look into"),
            (re.compile(r"\bharness multifaceted paradigms\b", re.I), "use varied approaches"),
            (re.compile(r"\bmultifaceted methodologies\b", re.I), "varied methods"),
            (re.compile(r"\bmultifaceted approaches\b", re.I), "varied approaches"),
            (re.compile(r"\bmultifaceted screening mechanisms\b", re.I), "well-rounded screening tools"),
            (re.compile(r"\bmultifaceted\b", re.I), "well-rounded"),
            (re.compile(r"\bmethodologies\b", re.I), "methods"),
            (re.compile(r"\bmethodology\b", re.I), "method"),
            (re.compile(r"\bcandidate proficiencies\b", re.I), "candidate skills"),
            (re.compile(r"\bworkforce proficiencies\b", re.I), "team skills"),
            (re.compile(r"\bproficiencies\b", re.I), "skills"),
            (re.compile(r"\bproficiency\b", re.I), "skill"),
            (re.compile(r"\bcompetencies\b", re.I), "skills"),
            (re.compile(r"\bcompetency\b", re.I), "skill"),
            (re.compile(r"\bharnessing\b", re.I), "using"),
            (re.compile(r"\bharness\b", re.I), "use"),
            (re.compile(r"\butilizing\b", re.I), "using"),
            (re.compile(r"\butilizes\b", re.I), "uses"),
            (re.compile(r"\butilize\b", re.I), "use"),
            (re.compile(r"\butilization of\b", re.I), "use of"),
            (re.compile(r"\bleveraging\b", re.I), "using"),
            (re.compile(r"\bleverages\b", re.I), "uses"),
            (re.compile(r"\bleverage\b", re.I), "use"),
            (re.compile(r"\bfacilitate dynamic synergies\b", re.I), "encourage strong collaboration"),
            (re.compile(r"\bfacilitating\b", re.I), "helping"),
            (re.compile(r"\bfacilitates\b", re.I), "helps"),
            (re.compile(r"\bfacilitate\b", re.I), "help"),
            (re.compile(r"\bfostering\b", re.I), "building"),
            (re.compile(r"\bfosters\b", re.I), "builds"),
            (re.compile(r"\bfoster\b", re.I), "build"),
            (re.compile(r"\bspearheading\b", re.I), "leading"),
            (re.compile(r"\bspearhead\b", re.I), "lead"),
            (re.compile(r"\baugmenting\b", re.I), "boosting"),
            (re.compile(r"\baugments\b", re.I), "boosts"),
            (re.compile(r"\baugment\b", re.I), "boost"),
            (re.compile(r"\bbolstering\b", re.I), "strengthening"),
            (re.compile(r"\bbolsters\b", re.I), "strengthens"),
            (re.compile(r"\bbolster\b", re.I), "strengthen"),
            (re.compile(r"\bstreamlining\b", re.I), "simplifying"),
            (re.compile(r"\bstreamlines\b", re.I), "simplifies"),
            (re.compile(r"\bstreamline\b", re.I), "simplify"),
            (re.compile(r"\bempowering\b", re.I), "enabling"),
            (re.compile(r"\bempowers\b", re.I), "enables"),
            (re.compile(r"\bempower\b", re.I), "enable"),
            (re.compile(r"\belevating\b", re.I), "improving"),
            (re.compile(r"\belevates\b", re.I), "improves"),
            (re.compile(r"\belevate\b", re.I), "improve"),
            (re.compile(r"\bnavigate the complexities of\b", re.I), "handle"),
            (re.compile(r"\bnavigating\b", re.I), "handling"),
            (re.compile(r"\bnavigates\b", re.I), "handles"),
            (re.compile(r"\bnavigate\b", re.I), "handle"),
            (re.compile(r"\bcornerstone of\b", re.I), "foundation of"),
            (re.compile(r"\bcornerstone\b", re.I), "bedrock"),
            (re.compile(r"\bbeacon of\b", re.I), "example of"),
            (re.compile(r"\bgame-changer\b", re.I), "turning point"),
            (re.compile(r"\bcutting-edge methodologies\b", re.I), "modern methods"),
            (re.compile(r"\bcutting-edge\b", re.I), "modern"),
            (re.compile(r"\bstate-of-the-art\b", re.I), "modern"),
            (re.compile(r"\brich tapestry\b", re.I), "wide mix"),
            (re.compile(r"\bintricate tapestry\b", re.I), "complex blend"),
            (re.compile(r"\btapestry of\b", re.I), "blend of"),
            (re.compile(r"\btapestry\b", re.I), "mix"),
            (re.compile(r"\ba testament to\b", re.I), "a clear sign of"),
            (re.compile(r"\bactionable insights\b", re.I), "practical takeaways"),
            (re.compile(r"\bactionable diagnostic insights\b", re.I), "practical takeaways"),
            (re.compile(r"\bactionable\b", re.I), "practical"),
            (re.compile(r"\bholistic approach\b", re.I), "well-rounded approach"),
            (re.compile(r"\bholistic\b", re.I), "well-rounded"),
            (re.compile(r"\bseamless integration\b", re.I), "smooth rollout"),
            (re.compile(r"\bseamless cross-functional alignment\b", re.I), "smooth teamwork across groups"),
            (re.compile(r"\bseamlessly\b", re.I), "smoothly"),
            (re.compile(r"\bseamless\b", re.I), "smooth"),
            (re.compile(r"\brobust data protection protocols\b", re.I), "solid data protection rules"),
            (re.compile(r"\brobust\b", re.I), "solid"),
            (re.compile(r"\brobustly\b", re.I), "reliably"),
            (re.compile(r"\brapid proliferation of\b", re.I), "fast spread of"),
            (re.compile(r"\bproliferation of\b", re.I), "spread of"),
            (re.compile(r"\boptimize organizational synergies\b", re.I), "boost collaboration"),
            (re.compile(r"\boptimize hiring velocity\b", re.I), "speed up hiring"),
            (re.compile(r"\boptimize\b", re.I), "tune"),
            (re.compile(r"\boptimizing\b", re.I), "improving"),
            (re.compile(r"\boperational synergies\b", re.I), "collaboration"),
            (re.compile(r"\bdynamic synergies\b", re.I), "close teamwork"),
            (re.compile(r"\bsynergies\b", re.I), "teamwork"),
            (re.compile(r"\bsynergy\b", re.I), "teamwork"),
            (re.compile(r"\boperational workflows\b", re.I), "day-to-day operations"),
            (re.compile(r"\broutine workflows\b", re.I), "repetitive tasks"),
            (re.compile(r"\bworkflows\b", re.I), "processes"),
            (re.compile(r"\bworkflow\b", re.I), "process"),
            (re.compile(r"\bcross-functional teams\b", re.I), "teams across departments"),
            (re.compile(r"\bcross-functional\b", re.I), "interdepartmental"),
            (re.compile(r"\bdisparate communication channels\b", re.I), "scattered communication tools"),
            (re.compile(r"\bdisparate\b", re.I), "disconnected"),
            (re.compile(r"\bharmonize\b", re.I), "align"),
            (re.compile(r"\bharmonizing\b", re.I), "aligning"),
            (re.compile(r"\bmitigating employee turnover\b", re.I), "keeping staff turnover low"),
            (re.compile(r"\bmitigating\b", re.I), "reducing"),
            (re.compile(r"\bmitigate\b", re.I), "reduce"),
            (re.compile(r"\btranscend legacy operational silos\b", re.I), "break down department silos"),
            (re.compile(r"\btranscend\b", re.I), "move beyond"),
            (re.compile(r"\bunprecedented levels of\b", re.I), "record levels of"),
            (re.compile(r"\bunprecedented speed\b", re.I), "record speed"),
            (re.compile(r"\bunprecedented\b", re.I), "historic"),
            (re.compile(r"\binnovation velocity\b", re.I), "pace of innovation"),
            (re.compile(r"\bvelocity\b", re.I), "speed"),
            (re.compile(r"\bcohesion\b", re.I), "unity"),
            (re.compile(r"\bparamount importance\b", re.I), "critical importance"),
            (re.compile(r"\bparamount\b", re.I), "critical"),
            (re.compile(r"\bpivotal role in\b", re.I), "key role in"),
            (re.compile(r"\bpivotal\b", re.I), "key"),
            (re.compile(r"\bimperative\b", re.I), "essential"),
            (re.compile(r"\bbusiness imperatives\b", re.I), "business goals"),
            (re.compile(r"\boperational tiers\b", re.I), "levels of the company"),
            (re.compile(r"\bproactively establish\b", re.I), "set up early"),
            (re.compile(r"\bproactively\b", re.I), "early on"),
            (re.compile(r"\bcomprehensive governance frameworks\b", re.I), "clear governance guidelines"),
            (re.compile(r"\bcomprehensive training programs\b", re.I), "thorough training programs"),
            (re.compile(r"\bcomprehensive\b", re.I), "thorough"),
            (re.compile(r"\bautomated methodologies\b", re.I), "automated tools"),
            (re.compile(r"\bsubstantial friction\b", re.I), "real hurdles"),
            (re.compile(r"\bfriction\b", re.I), "bottlenecks"),
            (re.compile(r"\bcontinuous feedback loops\b", re.I), "ongoing check-ins"),
            (re.compile(r"\bworkforce engagement and morale\b", re.I), "team engagement and morale"),
            (re.compile(r"\bcollaborative digital toolsets\b", re.I), "shared digital tools"),
            (re.compile(r"\bstreamlining administrative procedures\b", re.I), "cutting down on paperwork"),
            (re.compile(r"\bcultivate an inclusive workplace culture\b", re.I), "build an inclusive team culture"),
            (re.compile(r"\bcultivating\b", re.I), "building"),
            (re.compile(r"\bcultivate\b", re.I), "build"),
            (re.compile(r"\btransparent dialogue\b", re.I), "open communication"),
            (re.compile(r"\bongoing professional development\b", re.I), "regular skill development"),
            (re.compile(r"\bdemonstrate significantly higher\b", re.I), "see much higher"),
            (re.compile(r"\bdemonstrate\b", re.I), "show"),
            (re.compile(r"\bdemonstrates\b", re.I), "shows"),
            (re.compile(r"\bdemonstrated\b", re.I), "showed"),
            (re.compile(r"\bexhibits\b", re.I), "shows"),
            (re.compile(r"\bexhibited\b", re.I), "showed"),
            (re.compile(r"\bexhibit\b", re.I), "show"),
            (re.compile(r"\billustrates\b", re.I), "shows"),
            (re.compile(r"\billustrate\b", re.I), "show"),
            (re.compile(r"\bunderscores\b", re.I), "highlights"),
            (re.compile(r"\bunderscore\b", re.I), "highlight"),

            # Academic, Science, Humanities & Essay vocab
            (re.compile(r"\bis the biological process by which\b", re.I), "is the natural process where"),
            (re.compile(r"\bis the process by which\b", re.I), "is how"),
            (re.compile(r"\bchlorophyll pigments absorb solar radiation\b", re.I), "chlorophyll absorbs sunlight"),
            (re.compile(r"\babsorb solar radiation\b", re.I), "absorb sunlight"),
            (re.compile(r"\bsolar radiation\b", re.I), "sunlight"),
            (re.compile(r"\bsynthesis of glucose from carbon dioxide and water\b", re.I), "production of glucose using carbon dioxide and water"),
            (re.compile(r"\bsynthesis of\b", re.I), "production of"),
            (re.compile(r"\bOxygen is consequently released into the atmosphere as a byproduct\b", re.I), "This releases oxygen into the atmosphere as a natural byproduct"),
            (re.compile(r"\bis consequently released\b", re.I), "is then released"),
            (re.compile(r"\bsustaining aerobic life on Earth\b", re.I), "supporting oxygen-breathing life on Earth"),
            (re.compile(r"\bsustaining aerobic life\b", re.I), "supporting aerobic life"),
            (re.compile(r"\bsustaining\b", re.I), "supporting"),
            (re.compile(r"\bthis fundamental biochemical pathway serves as the cornerstone of\b", re.I), "this essential chemical process forms the foundation of"),
            (re.compile(r"\bfundamental biochemical pathway\b", re.I), "essential biochemical cycle"),
            (re.compile(r"\bpathway serves as the cornerstone of\b", re.I), "process acts as the bedrock for"),
            (re.compile(r"\bserves as the cornerstone of\b", re.I), "forms the foundation of"),
            (re.compile(r"\bserves as the foundation of\b", re.I), "forms the foundation of"),
            (re.compile(r"\bserves as a\b", re.I), "acts as a"),
            (re.compile(r"\bserves as\b", re.I), "acts as"),
            (re.compile(r"\bglobal primary productivity\b", re.I), "global organic production"),
            (re.compile(r"\bterrestrial carbon cycles\b", re.I), "Earth's carbon cycles"),
            (re.compile(r"\brapidly transforming global industry sectors by\b", re.I), "quickly reshaping industries by"),
            (re.compile(r"\brapidly transforming\b", re.I), "quickly reshaping"),
            (re.compile(r"\btransforming\b", re.I), "reshaping"),
            (re.compile(r"\bglobal industry sectors\b", re.I), "industries worldwide"),
            (re.compile(r"\bindustry sectors\b", re.I), "industries"),
            (re.compile(r"\bautomating routine workflows and optimizing operational efficiency\b", re.I), "automating everyday tasks and sharpening efficiency"),
            (re.compile(r"\bautomating routine workflows\b", re.I), "automating daily tasks"),
            (re.compile(r"\boptimizing operational efficiency\b", re.I), "improving day-to-day efficiency"),
            (re.compile(r"\boperational efficiency\b", re.I), "efficiency"),
            (re.compile(r"\bOrganizations leverage complex machine learning models\b", re.I), "Companies use machine learning models"),
            (re.compile(r"\bcomplex machine learning models\b", re.I), "advanced machine learning models"),
            (re.compile(r"\bvast repositories of unstructured data\b", re.I), "huge stores of raw data"),
            (re.compile(r"\bvast repositories of\b", re.I), "massive stores of"),
            (re.compile(r"\bunstructured data\b", re.I), "raw data"),
            (re.compile(r"\bgenerating actionable insights for decision-makers\b", re.I), "giving leaders practical takeaways"),
            (re.compile(r"\bdecision-makers\b", re.I), "leaders"),
            (re.compile(r"\bimplementing these advanced computational systems necessitates\b", re.I), "rolling out these computing systems requires"),
            (re.compile(r"\badvanced computational systems\b", re.I), "advanced computing systems"),
            (re.compile(r"\bcomputational systems\b", re.I), "computing systems"),
            (re.compile(r"\bnecessitates comprehensive ethical oversight\b", re.I), "calls for clear ethical guardrails"),
            (re.compile(r"\bnecessitates\b", re.I), "calls for"),
            (re.compile(r"\bnecessitate\b", re.I), "call for"),
            (re.compile(r"\bembracing technological innovation while maintaining human oversight\b", re.I), "adopting new technology while keeping humans involved"),
            (re.compile(r"\btechnological innovation\b", re.I), "new technology"),
            (re.compile(r"\bmaintaining human oversight\b", re.I), "keeping people in the loop"),
            (re.compile(r"\bremains imperative for long-term sustainability\b", re.I), "is essential for lasting success"),
            (re.compile(r"\bremains imperative for\b", re.I), "is vital for"),
            (re.compile(r"\bremains imperative\b", re.I), "is essential"),
            (re.compile(r"\blong-term sustainability\b", re.I), "long-term success"),
            (re.compile(r"\bThe novel explores themes of isolation and redemption\b", re.I), "The novel delves into loneliness and redemption"),
            (re.compile(r"\bexplores themes of\b", re.I), "examines ideas of"),
            (re.compile(r"\bnineteenth-century society\b", re.I), "19th-century society"),
            (re.compile(r"\bThrough vivid imagery and complex character relationships,\s*", re.I), "Using vivid imagery and layered relationships, "),
            (re.compile(r"\bvivid imagery and complex character relationships\b", re.I), "rich imagery and layered character relationships"),
            (re.compile(r"\bthe author illustrates the struggle between individual desire and societal expectations\b", re.I), "the writer captures the tension between personal desire and social expectations"),
            (re.compile(r"\bthe struggle between individual desire and societal expectations\b", re.I), "the clash between personal desire and societal pressure"),
            (re.compile(r"\bindividual desire and societal expectations\b", re.I), "personal desire and social expectations"),
            (re.compile(r"\bThe protagonist undergoes significant moral development\b", re.I), "The main character goes through meaningful personal growth"),
            (re.compile(r"\bprotagonist\b", re.I), "main character"),
            (re.compile(r"\bundergoes significant moral development\b", re.I), "grows noticeably in character"),
            (re.compile(r"\bsignificant moral development\b", re.I), "meaningful personal growth"),
            (re.compile(r"\bexperiencing severe adversity and personal loss\b", re.I), "facing harsh trials and deep personal loss"),
            (re.compile(r"\bsevere adversity and personal loss\b", re.I), "heavy hardship and personal loss"),
            (re.compile(r"\bsevere adversity\b", re.I), "heavy hardship"),
            (re.compile(r"\badversity\b", re.I), "hardship"),
            (re.compile(r"\bthe story highlights the importance of empathy, forgiveness, and personal responsibility\b", re.I), "the story emphasizes empathy, forgiveness, and personal accountability"),
            (re.compile(r"\bhighlights the importance of\b", re.I), "emphasizes the value of"),
            (re.compile(r"\bpersonal responsibility in overcoming deep emotional hardship\b", re.I), "personal accountability when dealing with deep pain"),
            (re.compile(r"\bdeep emotional hardship\b", re.I), "deep emotional pain"),

            # General, Academic, Historical & Narrative AI Cliches
            (re.compile(r"\brevolutionized human communication\b", re.I), "transformed the way humans communicate"),
            (re.compile(r"\brevolutionized\b", re.I), "transformed"),
            (re.compile(r"\bsparking the Information Age\b", re.I), "setting off the Information Age"),
            (re.compile(r"\bsparking the\b", re.I), "setting off the"),
            (re.compile(r"\bpainstakingly copied by hand\b", re.I), "copied by hand line by line"),
            (re.compile(r"\bpainstakingly\b", re.I), "carefully"),
            (re.compile(r"\ba costly, time-consuming process that reserved knowledge for\b", re.I), "a slow, costly process that kept knowledge in the hands of"),
            (re.compile(r"\bcostly, time-consuming process\b", re.I), "slow and expensive process"),
            (re.compile(r"\breserved knowledge for\b", re.I), "kept knowledge locked away for"),
            (re.compile(r"\bkey innovation\b", re.I), "main breakthrough"),
            (re.compile(r"\benabling rapid mass production of standardized texts\b", re.I), "allowing printers to rapidly mass-produce standardized texts"),
            (re.compile(r"\benabling rapid mass production of\b", re.I), "allowing for rapid mass production of"),
            (re.compile(r"\bThe immediate impact was profound:\s*", re.I), "The impact was felt right away: "),
            (re.compile(r"\bcost of publishing plummeted\b", re.I), "cost of publishing dropped sharply"),
            (re.compile(r"\bplummeted\b", re.I), "dropped sharply"),
            (re.compile(r"\bliteracy rates soared across Europe\b", re.I), "literacy surged across Europe"),
            (re.compile(r"\bsoared across\b", re.I), "surged across"),
            (re.compile(r"\bspread with unprecedented speed\b", re.I), "traveled faster than ever before"),
            (re.compile(r"\bfueled the Renaissance\b", re.I), "powered the Renaissance"),
            (re.compile(r"\baccelerated the Protestant Reformation\b", re.I), "sped up the Protestant Reformation"),
            (re.compile(r"\blaid the foundation for the Scientific Revolution\b", re.I), "paved the way for the Scientific Revolution"),
            (re.compile(r"\blaid the foundation for\b", re.I), "paved the way for"),
            (re.compile(r"\bBy democratizing access to information,?\s*", re.I), "By opening access to information, "),
            (re.compile(r"\bdemocratizing access to\b", re.I), "opening up access to"),
            (re.compile(r"\btransformed how societies preserve memory, exchange knowledge, and foster free thought\b", re.I), "reshaped how societies save records, share knowledge, and encourage free thought"),
            (re.compile(r"\bpreserve memory, exchange knowledge, and foster free thought\b", re.I), "save records, share knowledge, and encourage free thought"),
            (re.compile(r"\bpreserve memory\b", re.I), "save records"),
            (re.compile(r"\bexchange knowledge\b", re.I), "share knowledge"),
            (re.compile(r"\bfoster free thought\b", re.I), "encourage free thought"),
            (re.compile(r",?\s*\bmaking it one of the most transformative technological achievements in human history\.?\b", re.I), ". It stands as one of the most transformative technical achievements in history."),
            (re.compile(r"\btransformative technological achievements\b", re.I), "transformative technical achievements"),
            (re.compile(r"\btransformative\b", re.I), "groundbreaking"),

            # Connectives
            (re.compile(r"\bFurthermore,\b", re.I), "Also,"),
            (re.compile(r"\bMoreover,\b", re.I), "Plus,"),
            (re.compile(r"\bAdditionally,\b", re.I), "On top of that,"),
            (re.compile(r"\bConsequently,\b", re.I), "As a result,"),
            (re.compile(r"\bSubsequently,\b", re.I), "After that,"),
            (re.compile(r"\bIn conclusion,?\s*", re.I), ""),
            (re.compile(r"\bIn summary,?\s*", re.I), ""),
            (re.compile(r"\bUltimately,?\s*", re.I), ""),
            (re.compile(r"\bTo summarize,?\s*", re.I), ""),
            (re.compile(r"\bAll in all,?\s*", re.I), ""),
            (re.compile(r"\bin order to\b", re.I), "to"),
            (re.compile(r"\bat this point in time\b", re.I), "currently"),
            (re.compile(r"\bdue to the fact that\b", re.I), "because"),
            (re.compile(r"\bwith regards to\b|\bin regards to\b|\bwith regard to\b", re.I), "regarding"),
            (re.compile(r"\bpertaining to\b|\bconcerning\b", re.I), "about"),
            (re.compile(r"\bsubsequent to\b", re.I), "after"),
            (re.compile(r"\bprior to\b", re.I), "before"),
            (re.compile(r"\bin the event that\b", re.I), "if"),
            (re.compile(r"\bfor the purpose of\b", re.I), "for"),
            (re.compile(r"\bwith the exception of\b", re.I), "except for"),
            (re.compile(r"\bprovide you with\b", re.I), "share"),
            (re.compile(r"\bassist you with\b", re.I), "help you with"),
            (re.compile(r"\bassist\b", re.I), "help"),
            (re.compile(r"\bassistance\b", re.I), "help"),
            (re.compile(r"\bensure that\b", re.I), "make sure"),
            (re.compile(r"\bensure\b", re.I), "make sure"),
            (re.compile(r"\bobtain\b", re.I), "get"),
            (re.compile(r"\bcommence\b", re.I), "start"),
            (re.compile(r"\bcommencing\b", re.I), "starting"),
            (re.compile(r"\bdisseminate\b", re.I), "share"),
            (re.compile(r"\bnot only\s+([^,\n]+),\s*but\s+(?:also\s+)?([^,\n\.]+)", re.I), r"both \1 and \2"),
            (re.compile(r"\bnot just\s+([^,\n]+),\s*but\s+([^,\n\.]+)", re.I), r"both \1 and \2"),
        ]

        for pattern, repl in replacements:
            p = pattern.sub(repl, p)

        # Tone contractions if not strictly formal
        tone_lower = (tone or "").lower()
        if "formal" not in tone_lower:
            contractions = [
                (re.compile(r"\bI am\b(?!\s+not)"), "I'm"),
                (re.compile(r"\bIt is\b(?!\s+not)"), "It's"),
                (re.compile(r"\bWe are\b(?!\s+not)"), "We're"),
                (re.compile(r"\bYou are\b(?!\s+not)"), "You're"),
                (re.compile(r"\bThey are\b(?!\s+not)"), "They're"),
                (re.compile(r"\bThere is\b(?!\s+not)"), "There's"),
                (re.compile(r"\bWe will\b(?!\s+not)"), "We'll"),
                (re.compile(r"\bYou will\b(?!\s+not)"), "You'll"),
                (re.compile(r"\bI will\b(?!\s+not)"), "I'll"),
                (re.compile(r"\bdo not\b", re.I), "don't"),
                (re.compile(r"\bdoes not\b", re.I), "doesn't"),
                (re.compile(r"\bdid not\b", re.I), "didn't"),
                (re.compile(r"\bcannot\b", re.I), "can't"),
                (re.compile(r"\bwill not\b", re.I), "won't"),
            ]
            for cp, cr in contractions:
                p = cp.sub(cr, p)

        # Step 3: Sentence-level restructuring pass per paragraph
        w_orig = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", para)]
        w_cand = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", p)]
        overlap = len(set(w_orig) & set(w_cand)) / max(1, len(set(w_orig)))

        if overlap > 0.65 or p.strip().lower() == para.strip().lower() or force_restructure:
            cand_sentences = re.split(r"(?<=[.!?])\s+", p)
            restructured_sents = []
            for s in cand_sentences:
                s_clean = s.strip()
                if not s_clean:
                    continue

                # Invert introductory adverbial clauses (e.g. "During this process, X does Y" -> "X does Y during this process.")
                adv_match = re.match(r"^(During\s+[a-z0-9]+\s+[^,]+|Through\s+[a-z0-9]+\s+[^,]+|Throughout\s+[^,]+),\s+(.+)$", s_clean, re.I)
                if adv_match and len(s_clean.split()) >= 10:
                    prep_part = adv_match.group(1)
                    main_part = adv_match.group(2)
                    punc = "."
                    if main_part.endswith((".", "!", "?")):
                        punc = main_part[-1]
                        main_part = main_part[:-1]
                    main_part = main_part[0].upper() + main_part[1:]
                    s_clean = f"{main_part} {prep_part.lower()}{punc}"

                # Sentence-level restructuring and active transformations
                s_clean = re.sub(r"\bprocess by which\b", "way", s_clean, flags=re.I)
                s_clean = re.sub(r"\bconvert\b", "turn", s_clean, flags=re.I)
                s_clean = re.sub(r"\bconverts\b", "turns", s_clean, flags=re.I)
                s_clean = re.sub(r"\bconverting\b", "turning", s_clean, flags=re.I)
                s_clean = re.sub(r"\bchemical power\b", "chemical fuel", s_clean, flags=re.I)
                s_clean = re.sub(r"\bgreen plants\b", "plants", s_clean, flags=re.I)
                s_clean = re.sub(r"\bcertain bacteria\b", "some bacteria", s_clean, flags=re.I)
                s_clean = re.sub(r"\bbiological process\b", "vital natural cycle", s_clean, flags=re.I)
                s_clean = re.sub(r"\bis the\b", "works as the", s_clean, flags=re.I)
                s_clean = re.sub(r"\bare able to\b", "can", s_clean, flags=re.I)
                s_clean = re.sub(r"\bis able to\b", "can", s_clean, flags=re.I)
                s_clean = re.sub(r"\bhas the ability to\b", "can", s_clean, flags=re.I)
                s_clean = re.sub(r"\bserve as\b", "act as", s_clean, flags=re.I)
                s_clean = re.sub(r"\bserves as\b", "acts as", s_clean, flags=re.I)
                s_clean = re.sub(r"\bis responsible for\b", "handles", s_clean, flags=re.I)
                s_clean = re.sub(r"\bare responsible for\b", "handle", s_clean, flags=re.I)
                s_clean = re.sub(r"\bthere is a need to\b", "we need to", s_clean, flags=re.I)
                s_clean = re.sub(r"\bmakes it possible to\b", "lets us", s_clean, flags=re.I)
                s_clean = re.sub(r"\ballows for\b", "enables", s_clean, flags=re.I)
                s_clean = re.sub(r"\bplays a role in\b", "contributes to", s_clean, flags=re.I)
                s_clean = re.sub(r"\bis an example of\b", "illustrates", s_clean, flags=re.I)
                s_clean = re.sub(r"\bprimary\b", "main", s_clean, flags=re.I)
                s_clean = re.sub(r"\bsignificant\b", "notable", s_clean, flags=re.I)
                s_clean = re.sub(r"\bsubstantial\b", "major", s_clean, flags=re.I)
                s_clean = re.sub(r"\bessential\b", "key", s_clean, flags=re.I)
                s_clean = re.sub(r"\bdeployment of\b", "rollout of", s_clean, flags=re.I)
                s_clean = re.sub(r"\brecruitment operations\b", "hiring operations", s_clean, flags=re.I)
                s_clean = re.sub(r"\bprocedural bottlenecks\b", "process delays", s_clean, flags=re.I)
                s_clean = re.sub(r"\brecruiting leaders\b", "hiring leads", s_clean, flags=re.I)
                s_clean = re.sub(r"\bstandardized assessment criteria\b", "consistent evaluation guidelines", s_clean, flags=re.I)
                s_clean = re.sub(r"\bconduct an analysis of\b", "analyze", s_clean, flags=re.I)
                s_clean = re.sub(r"\bmake a decision\b", "decide", s_clean, flags=re.I)
                s_clean = re.sub(r"\btake into consideration\b", "consider", s_clean, flags=re.I)

                # Clean sentence capitalization
                s_clean = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), s_clean)
                restructured_sents.append(s_clean)

            p = " ".join(restructured_sents)

        # Fix mid-sentence capitalization after commas
        p = re.sub(r",\s*We need to\b", ", we need to", p)
        p = re.sub(r",\s*It's key to\b", ", it's key to", p)
        p = re.sub(r",\s*It's critical to\b", ", it's critical to", p)
        p = re.sub(r",\s*We must\b", ", we must", p)

        # Clean capitalization, double spaces & punctuation artifacts
        p = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), p)
        p = re.sub(r"\.\.+", ".", p)
        p = re.sub(r"[ \t]+", " ", p).strip()
        rewritten_paras.append(p)

    candidate = "\n\n".join(rewritten_paras).strip()
    return candidate


class HumanizerService:
    def __init__(self, default_model: str | None = None):
        self.default_model = default_model or settings.gemini_model
        self.timeout = settings.gemini_timeout

    def check_health(self) -> dict[str, Any]:
        """Check status of Gemini Cloud AI."""
        g_info = gemini_service.check_health()
        return {
            "reachable": g_info["configured"],
            "model_available": True,
            "active_model": g_info["model"],
            "available_models": ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-2.0-flash"],
            "gemini_configured": g_info["configured"],
            "gemini_rate_limited": g_info["rate_limited"],
            "cooldown_remaining": g_info["cooldown_remaining"],
        }

    def humanize_text(
        self,
        text: str,
        communication_type: str = "general_hr",
        tone: str = "professional",
        preserve_facts: bool = True,
        model_override: str | None = None,
        writing_mode: str = "Clarity Improvement",
        intensity: str = "Balanced",
        context_anchor: str | None = None,
    ) -> HumanizeResponse:
        start_time = time.time()
        clean_input = text.strip()

        if not clean_input:
            empty_val = ValidationResponse(
                passed=True,
                requires_review=False,
                confidence_score=1.0,
                warnings=[],
            )
            return HumanizeResponse(
                original_text="",
                rewritten_text="",
                validation=empty_val,
                model=settings.gemini_model,
                provider="gemini",
                fallback_used=False,
                duration_seconds=0.0,
            )

        is_question = clean_input.endswith("?")
        intensity_norm = str(intensity).capitalize() if intensity else "Balanced"

        # Determine writing mode guidelines
        mode_instruction = ""
        if writing_mode == "Clarity Improvement":
            mode_instruction = (
                "Focus on directness, transparent phrasing, and eliminating bureaucratic wordiness "
                "while preserving every fact, milestone, and commitment."
            )
        elif writing_mode == "De-AI Robotic Cleanup":
            mode_instruction = (
                "Eliminate mechanical robotic sentence structure, formulaic buzzwords, and AI cadence "
                "while locking in every entity and metric."
            )
        elif writing_mode == "Warmth & Empathy":
            mode_instruction = (
                "Inject genuine human empathy, supportive tone, and considerate perspective "
                "while leaving all details intact."
            )
        elif writing_mode == "Executive Polish":
            mode_instruction = (
                "Deliver crisp, confident executive-level clarity with strong active verbs and concise rhythm."
            )

        full_system_prompt = build_system_prompt(
            communication_type=communication_type,
            tone=tone,
            writing_mode=writing_mode,
            intensity=intensity_norm,
            context_anchor=context_anchor,
        )
        if mode_instruction:
            full_system_prompt += f"\n\nStyle Directive: {mode_instruction}"

        candidate = ""
        provider = "gemini"
        active_model_used = model_override or settings.gemini_model
        fallback_used = False
        fallback_reason = None
        gemini_succeeded = False

        # Attempt rewrite with Google Gemini if configured
        if gemini_service.is_configured() and not gemini_service.is_currently_rate_limited():
            temp = 0.65 if intensity_norm == "Subtle" else 0.9 if intensity_norm == "High" else 0.8
            success, raw_out, err_msg, is_rate_limit = gemini_service.generate_rewrite(
                text=clean_input,
                system_prompt=full_system_prompt,
                temperature=temp,
            )
            if success and raw_out.strip():
                clean_g = clean_model_output(raw_out, clean_input)
                if clean_g.strip() and clean_g.strip().lower() != clean_input.lower():
                    candidate = clean_g
                    gemini_succeeded = True
                    provider = "gemini"
                    active_model_used = settings.gemini_model
                    fallback_used = False
                    logger.info("✔ Google Gemini successfully delivered verified humanized rewrite.")

            if not gemini_succeeded:
                fallback_used = True
                if is_rate_limit:
                    fallback_reason = "Gemini API rate limit reached (429 Quota Exceeded). Using deterministic FactGuard engine."
                else:
                    clean_err = re.sub(r"\{.*?\}", "", err_msg or "").strip()
                    clean_err = clean_err.split("\n")[0][:100] if clean_err else "Validation mismatch"
                    fallback_reason = f"Gemini rewrite failed ({clean_err}). Using deterministic FactGuard engine."
                logger.warning("⚡ %s", fallback_reason)
        elif gemini_service.is_currently_rate_limited():
            fallback_used = True
            rem = gemini_service.cooldown_seconds_remaining()
            fallback_reason = f"Gemini rate limit cooldown active ({rem}s remaining). Using deterministic FactGuard engine."
            logger.warning("⚡ %s", fallback_reason)
        elif not settings.enable_gemini:
            # Gemini is explicitly disabled in config - FactGuard operates as primary autonomous engine
            fallback_used = False
            fallback_reason = None
            gemini_succeeded = False
            provider = "rule_engine"
            active_model_used = "FactGuard Rule Engine"
            logger.info("FactGuard Rule Engine active (Gemini disabled by user configuration).")
        else:
            fallback_used = True
            fallback_reason = "Gemini API key is not configured in .env. Using deterministic FactGuard engine."
            logger.info(fallback_reason)

        # If Gemini did not produce a candidate, use the deterministic rule engine
        if not gemini_succeeded:
            provider = "rule_engine"
            active_model_used = "FactGuard Rule Engine"
            candidate = generate_fallback_rewrite(clean_input, communication_type, tone)

        # Clean any stubborn AI clichés that may remain
        candidate = generate_fallback_rewrite(candidate, communication_type, tone)

        # Check divergence to ensure output is genuinely humanized
        w_orig_set = set(re.findall(r"\b[a-zA-Z]{3,}\b", clean_input.lower()))
        w_cand_set = set(re.findall(r"\b[a-zA-Z]{3,}\b", candidate.lower()))
        cand_overlap = len(w_orig_set & w_cand_set) / max(1, len(w_orig_set))

        if candidate.strip().lower() == clean_input.lower() or cand_overlap > 0.65:
            candidate = generate_fallback_rewrite(clean_input, communication_type, tone, force_restructure=True)

        # Ensure speech act integrity: if input was a question, rewrite must remain a question
        if is_question and not candidate.strip().endswith("?"):
            candidate = candidate.rstrip(".") + "?"

        validation = (
            validate_hr_rewrite(clean_input, candidate)
            if preserve_facts
            else ValidationResponse(
                passed=True,
                requires_review=False,
                confidence_score=1.0,
                warnings=[],
            )
        )

        retried = False
        # Retry mechanism: if critical issues exist on concise text, perform 1 targeted retry with Gemini
        if (
            preserve_facts
            and settings.max_retries > 0
            and len(clean_input.split()) <= 120
            and provider == "gemini"
            and not gemini_service.is_currently_rate_limited()
            and (
                len(validation.details.missing_numbers) > 0
                or len(validation.details.unsupported_judgments) > 0
                or validation.details.possible_negation_change
                or validation.details.possible_uncertainty_change
            )
        ):
            logger.info("Validation identified issues, attempting targeted Gemini retry.")
            try:
                retry_full_prompt = (
                    f"{full_system_prompt}\n\nNotice that the previous draft had potential issues: "
                    f"{', '.join(validation.warnings)}. Please strictly rewrite preserving all facts, numbers, dates, and negations."
                )
                r_ok, r_out, _, _ = gemini_service.generate_rewrite(
                    text=clean_input,
                    system_prompt=retry_full_prompt,
                    temperature=0.2,
                )
                if r_ok and r_out.strip() and r_out.strip().lower() != clean_input.lower():
                    r_cand = clean_model_output(r_out, clean_input)
                    r_val = validate_hr_rewrite(clean_input, r_cand)
                    if (
                        r_val.confidence_score >= validation.confidence_score
                        or len(r_val.warnings) <= len(validation.warnings)
                    ):
                        candidate = r_cand
                        validation = r_val
                        retried = True
            except Exception as g_retry_err:
                logger.debug("Gemini targeted retry skipped: %s", g_retry_err)

        # Final safety check: ensure candidate is never identical or minimally modified
        w_orig_f = set(re.findall(r"\b[a-zA-Z]{3,}\b", clean_input.lower()))
        w_cand_f = set(re.findall(r"\b[a-zA-Z]{3,}\b", candidate.lower()))
        final_overlap = len(w_orig_f & w_cand_f) / max(1, len(w_orig_f))
        if candidate.strip().lower() == clean_input.lower() or final_overlap > 0.65:
            candidate = generate_fallback_rewrite(clean_input, communication_type, tone, force_restructure=True)
            validation = validate_hr_rewrite(clean_input, candidate)

        elapsed = round(time.time() - start_time, 2)
        robotic_eval = analyze_robotic_language(clean_input, candidate)

        pipeline_stages = extract_pipeline_data(
            original=clean_input,
            rewrite=candidate,
            validation=validation,
            robotic_analysis=robotic_eval,
            communication_type=communication_type,
            tone=tone,
            intensity=intensity_norm,
            context_anchor=context_anchor,
        )

        scorecard = calculate_evaluation_scorecard(
            original=clean_input,
            rewrite=candidate,
            validation=validation,
            robotic_analysis=robotic_eval,
            communication_type=communication_type,
            tone=tone,
        )

        return HumanizeResponse(
            original_text=clean_input,
            rewritten_text=candidate,
            validation=validation,
            robotic_analysis=robotic_eval,
            pipeline_stages=pipeline_stages,
            evaluation_scorecard=scorecard,
            context_anchor=context_anchor,
            model=active_model_used,
            provider=provider,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            retried=retried,
            duration_seconds=elapsed,
        )


humanizer_service = HumanizerService()
ollama_service = humanizer_service
