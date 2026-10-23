"""Google Gemini AI Service with rate-limit detection and seamless local fallback signalling."""

from __future__ import annotations

import logging
import time
from typing import Any, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = None
        self._rate_limited_until: float = 0.0
        self._last_error: str | None = None

    @property
    def api_key(self) -> str | None:
        return self._api_key or settings.gemini_api_key

    @property
    def model(self) -> str:
        return self._model or settings.gemini_model

    @property
    def timeout(self) -> float:
        return self._timeout or settings.gemini_timeout

    def is_configured(self) -> bool:
        """Check if Gemini is enabled and an API key is available."""
        if not settings.enable_gemini:
            return False
        key = self.api_key
        return bool(key and key.strip())

    def is_currently_rate_limited(self) -> bool:
        """Check if we are in a cooldown period due to recent 429 / quota exhaustion."""
        return time.time() < self._rate_limited_until

    def cooldown_seconds_remaining(self) -> int:
        """Seconds remaining in rate-limit cooldown."""
        return max(0, int(self._rate_limited_until - time.time()))

    def get_client(self):
        """Lazy-initialize Google GenAI client."""
        if not self.is_configured():
            raise ValueError("GEMINI_API_KEY is not configured.")

        # Re-initialize client if key changed or not yet initialized
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError as e:
                raise RuntimeError(
                    "google-genai SDK is not installed. Please run 'pip install google-genai'."
                ) from e
        return self._client

    def generate_rewrite(
        self,
        text: str,
        system_prompt: str,
        temperature: float = 0.7,
    ) -> Tuple[bool, str, str | None, bool]:
        """Attempt text humanization with Google Gemini.

        Returns:
            Tuple of (success, output_text, error_message, is_rate_limit)
        """
        if not self.is_configured():
            return False, "", "Gemini API key is not configured.", False

        if self.is_currently_rate_limited():
            rem = self.cooldown_seconds_remaining()
            msg = f"Gemini rate limit cooldown active ({rem}s remaining)."
            return False, "", msg, True

        clean_text = text.strip()
        if not clean_text:
            return True, "", None, False

        token_estimate = max(1024, min(8192, int(len(clean_text.split()) * 4.0) + 500))

        try:
            from google.genai import types

            client = self.get_client()

            prompt = (
                f"Rewrite every sentence of the passage below into authentic, lively human writing that bypasses all AI detectors.\n\n"
                f"STRICT RULES:\n"
                f"- High burstiness: mix short punchy sentences (3-6 words) with natural longer sentences. Break monotone sentence length.\n"
                f"- Never use AI tells: no 'not only... but also', no rule of three adjectives, no 'delve', 'tapestry', 'streamline', 'foster', 'crucial', 'pivotal', 'seamless', 'harness', 'robust', or 'moreover'.\n"
                f"- No summary sentences at the end ('In summary', 'Ultimately', 'Overall').\n"
                f"- No bullet points, no bold headers, no quotation marks, no conversational preamble.\n"
                f"- Retain 100% of all numbers, dates, currency, percentages, names, and facts exactly.\n\n"
                f"Original text:\n{clean_text}\n\n"
                f"Human rewrite:"
            )

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=token_estimate,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )

            models_to_try = [self.model] if self.model else []
            fallback_candidates = [
                "gemini-3.8-flash",
                "gemini-3.8-flash-lite",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
            ]
            for cand in fallback_candidates:
                if cand not in models_to_try:
                    models_to_try.append(cand)

            last_err_str = ""
            for target_model in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=target_model,
                        contents=prompt,
                        config=config,
                    )

                    output = (response.text or "").strip()
                    if output:
                        self._last_error = None
                        if target_model != self.model:
                            logger.info("Retried with alternate model %s successfully.", target_model)
                        return True, output, None, False
                except Exception as model_err:
                    err_msg = str(model_err)
                    last_err_str = err_msg
                    err_lower = err_msg.lower()

                    is_rl = (
                        "429" in err_msg
                        or "resource_exhausted" in err_lower
                        or "quota" in err_lower
                        or "rate limit" in err_lower
                        or "too many requests" in err_lower
                    )
                    if is_rl:
                        self._rate_limited_until = time.time() + 60.0
                        self._last_error = f"Rate limit reached (429 / ResourceExhausted): {err_msg}"
                        logger.warning(
                            "Gemini API rate limit reached on %s. Cooling down for 60s.",
                            target_model,
                        )
                        return False, "", self._last_error, True

                    logger.warning(
                        "Gemini API call to %s failed (%s). Checking next available model...",
                        target_model,
                        err_msg,
                    )

            self._last_error = f"Gemini API error across models: {last_err_str}"
            return False, "", self._last_error, False

        except Exception as err:
            err_str = str(err)
            self._last_error = f"Gemini initialization error: {err_str}"
            logger.warning("Gemini failed (%s).", err_str)
            return False, "", self._last_error, False

    def check_health(self) -> dict[str, Any]:
        """Health and status inspection for Gemini engine."""
        configured = self.is_configured()
        rate_limited = self.is_currently_rate_limited()
        status_msg = "ready"
        if not configured:
            status_msg = "api_key_missing"
        elif rate_limited:
            status_msg = "rate_limited_cooling_down"

        return {
            "status": status_msg,
            "configured": configured,
            "model": self.model,
            "rate_limited": rate_limited,
            "cooldown_remaining": self.cooldown_seconds_remaining(),
            "last_error": self._last_error,
        }


gemini_service = GeminiService()
