"""Application configuration for HR Communication Humanizer."""

import os
from pathlib import Path
from pydantic import BaseModel

# Automatically load .env from backend directory or project root
try:
    from dotenv import load_dotenv
    # Look for .env in current working dir, app parent, or project root
    for candidate_dir in [
        Path.cwd(),
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path(__file__).resolve().parent.parent.parent.parent,
    ]:
        env_file = candidate_dir / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)
except ImportError:
    pass


class Settings(BaseModel):
    # Google Gemini AI settings
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    gemini_timeout: float = float(os.getenv("GEMINI_TIMEOUT", "30.0"))
    enable_gemini: bool = os.getenv("ENABLE_GEMINI", "false").lower() in ("true", "1", "yes")

    # Legacy alias for backward compatibility
    @property
    def model_name(self) -> str:
        return self.gemini_model

    # Operational limits
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "60.0"))
    max_input_length: int = int(os.getenv("MAX_INPUT_LENGTH", "4000"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "1"))

    # Server settings
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


settings = Settings()
