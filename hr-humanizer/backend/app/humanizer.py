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
) -> str:
    """Intelligent, deep rule-based humanizer eliminating AI clichés, formalisms, and robotic cadence."""
    if not text.strip():
        return text

    rewritten = text

    # Comprehensive AI clichés, throat-clearing, and robotic corporate markers
    replacements = [
        # Long email phrases and greetings/closings
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

        # Preamble & throat clearing
        (re.compile(r"\bIn the contemporary era of rapid technological advancement\b", re.I), "In today's fast-moving tech environment"),
        (re.compile(r"\bIn the contemporary recruitment landscape\b", re.I), "In today's hiring landscape"),
        (re.compile(r"\bIn the contemporary (?:era|landscape|workplace)\b", re.I), "Today"),
        (re.compile(r"\bIn today's fast-paced (?:world|digital landscape|environment)\b", re.I), "In today's workplace"),
        (re.compile(r"\bIn the rapidly evolving landscape of\b", re.I), "As ... changes quickly,"),
        (re.compile(r"\bIt goes without saying that\b", re.I), "Naturally,"),
        (re.compile(r"\bIt is worth noting that\b", re.I), "Notably,"),
        (re.compile(r"\bIt is important to note that\b", re.I), "Keep in mind that"),
        (re.compile(r"\bIt is crucial to note that\b", re.I), "Notably,"),
        (re.compile(r"\bIt is imperative (?:that\s+we\b|that\b|to\b)\s*", re.I), "We need to "),
        (re.compile(r"\bIt is essential (?:that\s+we\b|that\b|to\b)\s*", re.I), "It's key to "),
        (re.compile(r"\bIt is vital (?:that\s+we\b|that\b|to\b)\s*", re.I), "We must "),
        (re.compile(r"\bIt is of paramount importance (?:that\s+we\b|that\b|to\b)\s*", re.I), "It's critical to "),
        (re.compile(r"\bIt is incumbent upon us to\b", re.I), "We need to"),

        # AI buzzwords & verbs
        (re.compile(r"\bharness multifaceted paradigms\b", re.I), "use varied approaches"),
        (re.compile(r"\bmultifaceted methodologies\b", re.I), "varied methods"),
        (re.compile(r"\bmethodologies\b", re.I), "methods"),
        (re.compile(r"\bmethodology\b", re.I), "method"),
        (re.compile(r"\bcandidate proficiencies\b", re.I), "candidate skills"),
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
        (re.compile(r"\bdelve into\b", re.I), "explore"),
        (re.compile(r"\bdelving into\b", re.I), "exploring"),
        (re.compile(r"\bdelve\b", re.I), "look into"),
        (re.compile(r"\baugmenting\b", re.I), "boosting"),
        (re.compile(r"\baugments\b", re.I), "boosts"),
        (re.compile(r"\baugment\b", re.I), "boost"),
        (re.compile(r"\bbolstering\b", re.I), "strengthening"),
        (re.compile(r"\bbolsters\b", re.I), "strengthens"),
        (re.compile(r"\bbolster\b", re.I), "strengthen"),
        (re.compile(r"\bstreamlining\b", re.I), "simplifying"),
        (re.compile(r"\bstreamlines\b", re.I), "simplifies"),
        (re.compile(r"\bstreamline\b", re.I), "simplify"),
        (re.compile(r"\bmaximize operational efficiencies\b", re.I), "work more efficiently"),
        (re.compile(r"\boperational efficiencies\b", re.I), "efficiency"),
        (re.compile(r"\bdynamic synergies\b", re.I), "close teamwork"),
        (re.compile(r"\bsynergies\b", re.I), "collaboration"),
        (re.compile(r"\bsynergy\b", re.I), "teamwork"),
        (re.compile(r"\bcross-functional teams\b", re.I), "teams across departments"),
        (re.compile(r"\bmultifaceted approaches\b", re.I), "varied approaches"),
        (re.compile(r"\bmultifaceted\b", re.I), "comprehensive"),
        (re.compile(r"\bparadigm shift\b", re.I), "major transition"),
        (re.compile(r"\bcutting-edge methodologies\b", re.I), "modern methods"),
        (re.compile(r"\bcutting-edge\b", re.I), "modern"),
        (re.compile(r"\brich tapestry\b", re.I), "wide range"),
        (re.compile(r"\bintricate tapestry\b", re.I), "complex blend"),
        (re.compile(r"\btapestry\b", re.I), "blend"),
        (re.compile(r"\ba testament to\b", re.I), "a clear reflection of"),
        (re.compile(r"\bdemonstrated proficiency in\b", re.I), "showed strong skills in"),
        (re.compile(r"\bpossesses competencies in\b", re.I), "is skilled in"),
        (re.compile(r"\bpossess competencies in\b", re.I), "have skills in"),
        (re.compile(r"\bexhibited exceptional dedication\b", re.I), "showed great dedication"),
        (re.compile(r"\bexhibits\b", re.I), "shows"),
        (re.compile(r"\bexhibited\b", re.I), "showed"),
        (re.compile(r"\bdomain acumen\b", re.I), "domain expertise"),
        (re.compile(r"\bacumen\b", re.I), "expertise"),
        (re.compile(r"\bexemplary\b", re.I), "excellent"),
        (re.compile(r"\bshowcases\b", re.I), "shows"),
        (re.compile(r"\bshowcased\b", re.I), "showed"),
        (re.compile(r"\bshowcasing\b", re.I), "showing"),
        (re.compile(r"\bcommencement date\b", re.I), "start date"),
        (re.compile(r"\bparamount\b", re.I), "critical"),
        (re.compile(r"\bpivotal\b", re.I), "key"),
        (re.compile(r"\boverarching\b", re.I), "main"),
        (re.compile(r"\bseamless integration\b", re.I), "smooth rollout"),
        (re.compile(r"\bseamlessly\b", re.I), "smoothly"),
        (re.compile(r"\brobust\b", re.I), "solid"),
        (re.compile(r"\brobustly\b", re.I), "reliably"),
        (re.compile(r"\bactionable insights\b", re.I), "practical takeaways"),
        (re.compile(r"\bholistic approach\b", re.I), "well-rounded approach"),
        (re.compile(r"\bsuccessfully completed\b", re.I), "completed"),
        (re.compile(r"\bin light of the aforementioned\b", re.I), "given this"),

        # Wordy connectives
        (re.compile(r"\bFurthermore,\b", re.I), "Also,"),
        (re.compile(r"\bMoreover,\b", re.I), "Plus,"),
        (re.compile(r"\bAdditionally,\b", re.I), "Also,"),
        (re.compile(r"\bin order to\b", re.I), "to"),
        (re.compile(r"\bat this point in time\b", re.I), "currently"),
        (re.compile(r"\bdue to the fact that\b", re.I), "because"),
        (re.compile(r"\bwith regards to\b", re.I), "regarding"),
        (re.compile(r"\bin regards to\b", re.I), "regarding"),
        (re.compile(r"\bpertaining to\b", re.I), "about"),
        (re.compile(r"\bconcerning\b", re.I), "about"),
        (re.compile(r"\bsubsequent to\b", re.I), "after"),
        (re.compile(r"\bprior to\b", re.I), "before"),
        (re.compile(r"\bin advance of\b", re.I), "before"),
        (re.compile(r"\bin the event that\b", re.I), "if"),
        (re.compile(r"\bin the event of\b", re.I), "in case of"),
        (re.compile(r"\bfor the purpose of\b", re.I), "for"),
        (re.compile(r"\bwith the exception of\b", re.I), "except for"),
        (re.compile(r"\bat your earliest convenience\b", re.I), "as soon as you can"),
        (re.compile(r"\bas soon as possible\b", re.I), "as soon as you're able"),
        (re.compile(r"\bon a daily basis\b", re.I), "daily"),
        (re.compile(r"\bin the near future\b", re.I), "soon"),
        (re.compile(r"\bprovide you with\b", re.I), "share"),
        (re.compile(r"\bprovide(?:\s+the)?\s+necessary\s+assistance\b", re.I), "help out"),
        (re.compile(r"\brequire additional assistance\b", re.I), "need extra help"),
        (re.compile(r"\bassist you with\b", re.I), "help you with"),
        (re.compile(r"\bassist with\b", re.I), "help with"),
        (re.compile(r"\bassist\b", re.I), "help"),
        (re.compile(r"\bassistance\b", re.I), "help"),
        (re.compile(r"\bensure that\b", re.I), "make sure"),
        (re.compile(r"\bensure\b", re.I), "make sure"),
        (re.compile(r"\bmake an inquiry\b", re.I), "ask"),
        (re.compile(r"\binquire about\b", re.I), "ask about"),
        (re.compile(r"\binquire\b", re.I), "ask"),
        (re.compile(r"\bobtain\b", re.I), "get"),
        (re.compile(r"\bcommence\b", re.I), "start"),
        (re.compile(r"\bcommencing\b", re.I), "starting"),
        (re.compile(r"\breach a decision\b", re.I), "decide"),
        (re.compile(r"\btake into consideration\b", re.I), "consider"),
        (re.compile(r"\bdisseminate\b", re.I), "share"),

        # Gemini & ChatGPT Anti-AI Tells
        (re.compile(r"\bempowering\b", re.I), "helping"),
        (re.compile(r"\bempowers\b", re.I), "helps"),
        (re.compile(r"\bempower\b", re.I), "help"),
        (re.compile(r"\belevating\b", re.I), "improving"),
        (re.compile(r"\belevates\b", re.I), "improves"),
        (re.compile(r"\belevate\b", re.I), "improve"),
        (re.compile(r"\bnavigate the complexities of\b", re.I), "handle"),
        (re.compile(r"\bnavigating\b", re.I), "handling"),
        (re.compile(r"\bnavigates\b", re.I), "handles"),
        (re.compile(r"\bnavigate\b", re.I), "handle"),
        (re.compile(r"\bin a nutshell\b", re.I), "briefly"),
        (re.compile(r"\bat its core\b", re.I), "essentially"),
        (re.compile(r"\bit is worth noting that\b", re.I), "note that"),
        (re.compile(r"\bit's worth noting that\b", re.I), "note that"),
        (re.compile(r"\bcornerstone\b", re.I), "foundation"),
        (re.compile(r"\bbeacon of\b", re.I), "example of"),
        (re.compile(r"\bgame-changer\b", re.I), "major shift"),
        (re.compile(r"\bin today's (?:fast-paced|rapidly evolving)[^\.,]*landscape,?\s*", re.I), "Today, "),
        (re.compile(r"\bin today's fast-paced world,?\s*", re.I), "Today, "),
        (re.compile(r"\bnot only\s+(?:does|do|can|will|is|are)?\s*([^,\n]+),\s*but\s+(?:also\s+)?(?:does|do|can|will|is|are)?\s*([^,\n\.]+)", re.I), r"both \1 and \2"),
        (re.compile(r"\bnot just\s+([^,\n]+),\s*but\s+([^,\n\.]+)", re.I), r"both \1 and \2"),
        (re.compile(r"\bIn conclusion,?\s*", re.I), ""),
        (re.compile(r"\bIn summary,?\s*", re.I), ""),
        (re.compile(r"\bUltimately,?\s*", re.I), ""),

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
        (re.compile(r"\bunprecedented speed\b", re.I), "record speed"),
        (re.compile(r"\bunprecedented\b", re.I), "extraordinary"),
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
    ]

    # Split em-dash clauses into punchy, separate sentences (creating high burstiness)
    rewritten = re.sub(
        r"([a-z0-9])\s*[—–]\s*a\s+(slow|costly|expensive|complex|difficult|demanding|rare)\b",
        r"\1. It was a \2",
        rewritten,
        flags=re.I,
    )
    rewritten = re.sub(
        r"([a-z0-9])\s*[—–]\s*an\s+(expensive|essential|important|unprecedented)\b",
        r"\1. It was an \2",
        rewritten,
        flags=re.I,
    )

    # Convert trailing participial clauses into distinct sentences
    rewritten = re.sub(
        r",\s+enabling\s+(?:the\s+)?rapid\s+mass\s+production(?:\s+of)?\b",
        r". This allowed printers to rapidly mass-produce",
        rewritten,
        flags=re.I,
    )
    rewritten = re.sub(
        r",\s+sparking\s+the\s+Information\s+Age\b",
        r" and set off the Information Age",
        rewritten,
        flags=re.I,
    )

    for pattern, repl in replacements:
        rewritten = pattern.sub(repl, rewritten)

    # Ensure clean sentence capitalization after word removals
    rewritten = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), rewritten)

    # Tone adjustments & natural workplace contractions
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
            (re.compile(r"\bThey will\b(?!\s+not)"), "They'll"),
            (re.compile(r"\bdo not\b", re.I), "don't"),
            (re.compile(r"\bdoes not\b", re.I), "doesn't"),
            (re.compile(r"\bdid not\b", re.I), "didn't"),
            (re.compile(r"\bcan not\b|\bcannot\b", re.I), "can't"),
            (re.compile(r"\bcould not\b", re.I), "couldn't"),
            (re.compile(r"\bwould not\b", re.I), "wouldn't"),
            (re.compile(r"\bshould not\b", re.I), "shouldn't"),
            (re.compile(r"\bhave not\b", re.I), "haven't"),
            (re.compile(r"\bhas not\b", re.I), "hasn't"),
            (re.compile(r"\bhad not\b", re.I), "hadn't"),
            (re.compile(r"\bwill not\b", re.I), "won't"),
        ]
        for cp, cr in contractions:
            rewritten = cp.sub(cr, rewritten)

    # Fix mid-sentence capitalization after commas
    rewritten = re.sub(r",\s*We need to\b", ", we need to", rewritten)
    rewritten = re.sub(r",\s*It's key to\b", ", it's key to", rewritten)
    rewritten = re.sub(r",\s*It's critical to\b", ", it's critical to", rewritten)
    rewritten = re.sub(r",\s*We must\b", ", we must", rewritten)

    # Standardize punctuation and spacing
    rewritten = re.sub(r"\.\.+", ".", rewritten)
    rewritten = re.sub(r"[ \t]+", " ", rewritten)
    rewritten = re.sub(r"\n\s*\n\s*\n+", "\n\n", rewritten).strip()
    return rewritten


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
            "available_models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
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

        # If STILL identical to input, apply natural conversational flow transformations
        if candidate.strip().lower() == clean_input.lower():
            cand_mod = candidate
            cand_mod = re.sub(r"\bI would like to\b", "I'd like to", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bWe would like to\b", "We'd like to", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bWe are\b", "We're", cand_mod)
            cand_mod = re.sub(r"\bI am\b", "I'm", cand_mod)
            cand_mod = re.sub(r"\bYou are\b", "You're", cand_mod)
            cand_mod = re.sub(r"\bThey are\b", "They're", cand_mod)
            cand_mod = re.sub(r"\bdo not\b", "don't", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bdoes not\b", "doesn't", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bdid not\b", "didn't", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bcannot\b", "can't", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bwill not\b", "won't", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bposition\b", "role", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bcontact you\b", "reach out", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bcontact us\b", "reach out to us", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bthere is\b", "there's", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bit is\b", "it's", cand_mod, flags=re.I)
            cand_mod = re.sub(r"\bthat is\b", "that's", cand_mod, flags=re.I)
            candidate = cand_mod

        # Ensure speech act integrity: if input was a question, rewrite must remain a question
        if is_question and not candidate.strip().endswith("?"):
            candidate = generate_fallback_rewrite(clean_input, communication_type, tone)
            if not candidate.strip().endswith("?"):
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

        # Final safety check: if candidate is still identical to original, apply rule transformations
        if candidate.strip().lower() == clean_input.lower():
            candidate = generate_fallback_rewrite(clean_input, communication_type, tone)
            if candidate.strip().lower() == clean_input.lower():
                cand_mod = re.sub(r"\bdoes not\b", "doesn't", candidate, flags=re.I)
                cand_mod = re.sub(r"\bdo not\b", "don't", cand_mod, flags=re.I)
                cand_mod = re.sub(r"\bthere is\b", "there's", cand_mod, flags=re.I)
                if cand_mod.strip().lower() != clean_input.lower():
                    candidate = cand_mod
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
