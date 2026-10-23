import sys
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path for direct test runs
_CURRENT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CURRENT_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from app.humanizer import ollama_service  # type: ignore[import-untyped, import-not-found]  # noqa: E402
    from app.fact_checks import validate_hr_rewrite  # type: ignore[import-untyped, import-not-found]  # noqa: E402
except ImportError:
    from backend.app.humanizer import ollama_service  # type: ignore[import-untyped, import-not-found]  # noqa: E402
    from backend.app.fact_checks import validate_hr_rewrite  # type: ignore[import-untyped, import-not-found]  # noqa: E402


# 204-word single paragraph text
PARAGRAPH_204_WORDS = (
    "The rapid proliferation of artificial intelligence tools across modern enterprise architectures has precipitated "
    "a fundamental paradigm shift in corporate talent management and operational workflows. In order to optimize "
    "organizational synergies and facilitate seamless cross-functional alignment, executive leadership must proactively "
    "establish comprehensive governance frameworks prior to the formal rollout of automated methodologies. "
    "Furthermore, human resources professionals are increasingly called upon to evaluate candidate competencies and "
    "workforce proficiencies through multifaceted screening mechanisms, ensuring that technical capabilities correspond "
    "precisely with evolving business imperatives. However, contemporary enterprises frequently encounter substantial "
    "friction when attempting to harmonize disparate communication channels without instituting standardized operational "
    "protocols. Consequently, establishing continuous feedback loops and delivering actionable insights remains of "
    "paramount importance for mitigating employee turnover while bolstering workforce engagement and morale across all "
    "operational tiers. By actively leveraging collaborative digital toolsets and streamlining administrative procedures, "
    "departments can transcend legacy operational silos and achieve unprecedented levels of organizational cohesion. "
    "In addition, organizations that cultivate an inclusive workplace culture emphasizing transparent dialogue and ongoing "
    "professional development demonstrate significantly higher retention rates and greater innovation velocity."
)

# 250-word single paragraph text
PARAGRAPH_250_WORDS = (
    "In today's rapidly evolving technological landscape, organizations across multiple sectors are increasingly adopting sophisticated "
    "artificial intelligence methodologies in an effort to streamline operational workflows and bolster organizational productivity. "
    "The implementation of automated talent acquisition systems has fundamentally transformed traditional human resources practices, "
    "enabling recruiters to analyze candidate credentials with unprecedented speed and efficiency. However, executive leadership must "
    "ensure that technological integration does not compromise essential compliance standards, fair labor practices, and transparent "
    "communication protocols. When transitioning to automated screening tools, talent management departments frequently encounter substantial "
    "operational friction, particularly when attempting to harmonize disparate communication channels across cross-functional engineering "
    "and product divisions. Consequently, establishing continuous feedback loops and delivering actionable diagnostic insights remains "
    "of paramount importance for mitigating voluntary employee turnover and bolstering overall workforce morale. Moreover, organizations "
    "that cultivate an inclusive workplace environment prioritizing psychological safety and transparent dialogue demonstrate significantly "
    "higher employee retention rates and sustained innovation velocity. Talent development professionals must therefore design comprehensive "
    "training initiatives that empower existing personnel to adapt effectively to digital transformations while maintaining rigorous quality "
    "benchmarks. Ultimately, the successful convergence of artificial intelligence capabilities and human-centric leadership requires a deliberate "
    "commitment to ethical governance, continuous performance monitoring, and empathy across all operational tiers of the modern global enterprise."
)

# Multi-paragraph text (two 110-word paragraphs separated by blank line)
MULTI_PARAGRAPH_TEXT = (
    "The deployment of automated screening systems has fundamentally transformed contemporary recruitment operations across competitive enterprise environments. "
    "In order to optimize hiring velocity and reduce procedural bottlenecks, recruiting leaders must establish standardized assessment criteria prior to the rollout of new platforms. "
    "Furthermore, talent teams are increasingly expected to evaluate candidate proficiencies with objectivity, ensuring that hiring decisions reflect core technical capabilities rather than subjective impressions. "
    "However, organizations often face substantial friction when attempting to calibrate scoring thresholds across different interview panels without clear guidance.\n\n"
    "To resolve these operational challenges, executive leadership must institute comprehensive training programs and continuous calibration reviews across all functional hiring teams. "
    "By leveraging structured interview rubrics and simplifying feedback submission workflows, departments can eliminate ambiguous evaluation standards and achieve higher hiring consistency. "
    "In addition, cultivating an inclusive candidate experience emphasizing prompt communication and transparent interview timelines leads to higher offer acceptance rates and lower candidate drop-off."
)


def test_204_word_paragraph_transformation():
    """Verify that a single paragraph of 200+ words transforms cleanly without failure or timeouts."""
    res = ollama_service.humanize_text(
        text=PARAGRAPH_204_WORDS,
        communication_type="general_communication",
        tone="conversational",
        preserve_facts=True,
    )

    assert res.rewritten_text is not None
    assert len(res.rewritten_text.strip()) > 0
    words = res.rewritten_text.split()
    # Length should remain sensible (within 60% - 140% of original words, not exploding to 500+ words)
    assert 120 <= len(words) <= 260
    # FactGuard validation must pass
    assert res.validation.passed is True
    # Zero leaked thoughts or reasoning tags
    assert "<think>" not in res.rewritten_text
    assert "the user wants" not in res.rewritten_text.lower()
    assert "the original text says" not in res.rewritten_text.lower()


def test_250_word_paragraph_transformation():
    """Verify that a single paragraph of 250 words transforms cleanly with 100% factual integrity."""
    res = ollama_service.humanize_text(
        text=PARAGRAPH_250_WORDS,
        communication_type="general_communication",
        tone="conversational",
        preserve_facts=True,
    )

    assert res.rewritten_text is not None
    words = res.rewritten_text.split()
    assert 150 <= len(words) <= 300
    assert res.validation.passed is True
    assert "<think>" not in res.rewritten_text


def test_multi_paragraph_structure_preservation():
    """Verify that multi-paragraph documents preserve their exact paragraph count and separation."""
    res = ollama_service.humanize_text(
        text=MULTI_PARAGRAPH_TEXT,
        communication_type="general_hr",
        tone="professional",
        preserve_facts=True,
    )

    orig_paras = [p.strip() for p in MULTI_PARAGRAPH_TEXT.split("\n\n") if p.strip()]
    rev_paras = [p.strip() for p in res.rewritten_text.split("\n\n") if p.strip()]

    # Multi-paragraph layout must be preserved (2 paragraphs in, 2 paragraphs out)
    assert len(rev_paras) == len(orig_paras)
    assert res.validation.passed is True
