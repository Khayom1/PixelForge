"""Environment-based runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    base_url: str = "https://api.openai.com/v1"
    model: str = ""
    api_key: str | None = None
    timeout_seconds: float = 60.0
    max_agent_steps: int = 8

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.getenv("PIXELFORGE_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            model=os.getenv("PIXELFORGE_MODEL", ""),
            api_key=os.getenv("PIXELFORGE_API_KEY") or None,
            timeout_seconds=float(os.getenv("PIXELFORGE_TIMEOUT", "60")),
            max_agent_steps=max(1, min(int(os.getenv("PIXELFORGE_MAX_STEPS", "8")), 32)),
        )

    def validate_for_model_use(self) -> None:
        if not self.model.strip():
            raise ValueError("PIXELFORGE_MODEL is required.")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("PIXELFORGE_BASE_URL must be an HTTP(S) URL.")
        if self.timeout_seconds <= 0:
            raise ValueError("PIXELFORGE_TIMEOUT must be positive.")
