import json

from pixelforge.tools import build_registry
from pixelforge.workspace import Workspace


def test_phaser_scaffold(tmp_path) -> None:
    result = build_registry(Workspace(tmp_path)).execute(
        "create_phaser_game", json.dumps({"name": "Star Runner", "directory": "star-runner"})
    )
    assert result["ok"]
    assert "star-runner/src/main.js" in result["result"]["files"]
    assert "Phaser.Game" in (tmp_path / "star-runner/src/main.js").read_text()


def test_rejects_bad_project_directory(tmp_path) -> None:
    result = build_registry(Workspace(tmp_path)).execute(
        "create_phaser_game", json.dumps({"name": "Unsafe", "directory": "../escape"})
    )
    assert not result["ok"]


def test_unknown_tool_is_denied(tmp_path) -> None:
    assert build_registry(Workspace(tmp_path)).execute("shell", "{}")["ok"] is False



def test_game_title_is_html_escaped(tmp_path) -> None:
    malicious_title = '<img src=x onerror=alert(1)>'
    result = build_registry(Workspace(tmp_path)).execute(
        "create_phaser_game",
        json.dumps({"name": malicious_title, "directory": "safe-game"}),
    )
    assert result["ok"]
    generated = (tmp_path / "safe-game/index.html").read_text()
    assert "&lt;img" in generated
    assert "<img" not in generated


def test_scaffold_package_manifest_is_valid_json(tmp_path) -> None:
    result = build_registry(Workspace(tmp_path)).execute(
        "create_phaser_game",
        json.dumps({"name": "Manifest Test", "directory": "manifest-test"}),
    )
    assert result["ok"]
    manifest = json.loads((tmp_path / "manifest-test/package.json").read_text())
    assert manifest["dependencies"]["phaser"].startswith("^3.")
