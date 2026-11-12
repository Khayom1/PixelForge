"""Environment-based runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class Settings:
    base_url: str = "https://api.openai.com/v1"
    model: str = ""
    api_key: str | None = None
    timeout_seconds: float = 60.0
    max_agent_steps: int = 8

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            base_url=os.getenv("PIXELFORGE_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            model=os.getenv("PIXELFORGE_MODEL", ""),
            api_key=os.getenv("PIXELFORGE_API_KEY") or None,
            timeout_seconds=float(os.getenv("PIXELFORGE_TIMEOUT", "60")),
            max_agent_steps=max(1, min(int(os.getenv("PIXELFORGE_MAX_STEPS", "8")), 32)),
        )

    def validate_for_model_use(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip() or len(self.model) > 200:
            raise ValueError("PIXELFORGE_MODEL is required and must be at most 200 characters.")
        try:
            parsed = urlsplit(self.base_url)
            valid_url = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            raise ValueError(
                "PIXELFORGE_BASE_URL must be an absolute HTTP(S) URL without embedded credentials."
            )
        if not isfinite(self.timeout_seconds) or not 1 <= self.timeout_seconds <= 600:
            raise ValueError("PIXELFORGE_TIMEOUT must be between 1 and 600 seconds.")
        if not 1 <= self.max_agent_steps <= 32:
            raise ValueError("PIXELFORGE_MAX_STEPS must be between 1 and 32.")
