import pytest

from pixelforge.config import Settings


def test_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("PIXELFORGE_BASE_URL", "http://127.0.0.1:5000/v1/")
    monkeypatch.setenv("PIXELFORGE_MODEL", "qwen-local")
    monkeypatch.setenv("PIXELFORGE_API_KEY", "")
    monkeypatch.setenv("PIXELFORGE_MAX_STEPS", "100")
    settings = Settings.from_env()
    assert settings.base_url == "http://127.0.0.1:5000/v1"
    assert settings.model == "qwen-local"
    assert settings.api_key is None
    assert settings.max_agent_steps == 32
    settings.validate_for_model_use()


def test_settings_require_model() -> None:
    with pytest.raises(ValueError, match="PIXELFORGE_MODEL"):
        Settings().validate_for_model_use()


def test_settings_reject_invalid_url() -> None:
    with pytest.raises(ValueError, match="HTTP"):
        Settings(base_url="file:///tmp", model="test").validate_for_model_use()
