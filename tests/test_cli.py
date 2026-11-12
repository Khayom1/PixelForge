import sys

import pytest

from pixelforge import __version__
from pixelforge.cli import main


def test_cli_version(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["pixelforge", "--version"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 0
    assert capsys.readouterr().out.strip() == f"pixelforge {__version__}"


def test_cli_init_creates_phaser_project(tmp_path, monkeypatch, capsys) -> None:
    output = tmp_path / "star-runner"
    monkeypatch.setattr(
        sys,
        "argv",
        ["pixelforge", "init", "--name", "Star Runner", "--output", str(output)],
    )
    main()
    assert (output / "package.json").is_file()
    assert (output / "src" / "main.js").is_file()
    assert "Created Phaser project" in capsys.readouterr().out


def test_cli_inspect_reports_empty_workspace(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys, "argv", ["pixelforge", "inspect", "--workspace", str(tmp_path)]
    )
    main()
    assert capsys.readouterr().out.strip() == "No project files found."


def test_cli_inspect_lists_project_files(tmp_path, monkeypatch, capsys) -> None:
    (tmp_path / "main.js").write_text("console.log('ready');", encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["pixelforge", "inspect", "--workspace", str(tmp_path)]
    )
    main()
    assert capsys.readouterr().out.strip() == "main.js"


def test_cli_ask_uses_configured_provider(tmp_path, monkeypatch, capsys) -> None:
    class FakeProvider:
        def __init__(self, base_url, model, api_key, timeout_seconds):
            assert model == "local-test-model"

        def complete(self, messages, tools):
            from pixelforge.provider import ModelReply

            return ModelReply("Task completed.", [])

    monkeypatch.setenv("PIXELFORGE_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("PIXELFORGE_MODEL", "local-test-model")
    monkeypatch.delenv("PIXELFORGE_API_KEY", raising=False)
    monkeypatch.setattr("pixelforge.cli.OpenAICompatibleProvider", FakeProvider)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pixelforge",
            "ask",
            "--workspace",
            str(tmp_path),
            "--prompt",
            "Inspect this project.",
        ],
    )
    main()
    assert capsys.readouterr().out.strip() == "Task completed."
    assert (tmp_path / ".pixelforge" / "traces.jsonl").is_file()


def test_cli_ask_reports_missing_model_configuration(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("PIXELFORGE_MODEL", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pixelforge",
            "ask",
            "--workspace",
            str(tmp_path),
            "--prompt",
            "Inspect this project.",
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "PIXELFORGE_MODEL" in capsys.readouterr().err
