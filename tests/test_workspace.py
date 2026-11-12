from pathlib import Path

import pytest

from pixelforge.workspace import Workspace, WorkspaceError


def test_write_read_and_list(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "project")
    workspace.write_text("src/main.js", "console.log('hello');")
    assert workspace.read_text("src/main.js") == "console.log('hello');"
    assert workspace.list_files() == ["src/main.js"]


@pytest.mark.parametrize("path", ["../outside.txt", "/tmp/outside.txt", "a/../../outside.txt"])
def test_rejects_traversal(tmp_path: Path, path: str) -> None:
    with pytest.raises(WorkspaceError):
        Workspace(tmp_path / "project").write_text(path, "unsafe")


def test_rejects_symlink(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "project")
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace.root / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(WorkspaceError):
        workspace.write_text("linked/pwned.txt", "no")
    assert not (outside / "pwned.txt").exists()


def test_read_size_limit(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    workspace.write_text("large.txt", "x" * 20)
    with pytest.raises(WorkspaceError):
        workspace.read_text("large.txt", max_bytes=10)


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.production",
        ".git/config",
        ".pixelforge/traces.jsonl",
        ".ssh/id_ed25519",
        "certs/private.pem",
        "certs/signing.key",
        ".npmrc",
    ],
)
def test_rejects_credentials_and_private_metadata(tmp_path: Path, path: str) -> None:
    workspace = Workspace(tmp_path)
    with pytest.raises(WorkspaceError):
        workspace.read_text(path)
    with pytest.raises(WorkspaceError):
        workspace.write_text(path, "must not be exposed")


def test_file_listing_hides_private_and_generated_directories(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    (tmp_path / ".env").write_text("TOKEN=secret")
    (tmp_path / ".env.local").write_text("TOKEN=secret")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("private")
    (tmp_path / ".pixelforge").mkdir()
    (tmp_path / ".pixelforge" / "traces.jsonl").write_text("private")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "library.js").write_text("vendor")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.js").write_text("safe")
    assert workspace.list_files() == ["src/main.js"]
