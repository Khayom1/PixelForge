import os
from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="no no-follow open support")
def test_read_rejects_symlink_replaced_after_path_validation(tmp_path, monkeypatch) -> None:
    workspace = Workspace(tmp_path / "workspace")
    target = workspace.root / "notes.txt"
    target.write_text("workspace content", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("private content", encoding="utf-8")
    original_resolve = workspace.resolve

    def replace_after_validation(relative_path):
        resolved = original_resolve(relative_path)
        if relative_path == "notes.txt":
            target.unlink()
            target.symlink_to(outside)
        return resolved

    monkeypatch.setattr(workspace, "resolve", replace_after_validation)
    with pytest.raises(WorkspaceError):
        workspace.read_text("notes.txt")


def test_read_limit_is_enforced_on_open_descriptor(tmp_path, monkeypatch) -> None:
    workspace = Workspace(tmp_path / "workspace")
    target = workspace.root / "large.txt"
    target.write_text("x" * 1024, encoding="utf-8")
    original_stat = Path.stat

    def report_small_file(path, *args, **kwargs):
        metadata = original_stat(path, *args, **kwargs)
        if path == target:
            return SimpleNamespace(st_mode=metadata.st_mode, st_size=1)
        return metadata

    monkeypatch.setattr(Path, "stat", report_small_file)
    with pytest.raises(WorkspaceError, match="read limit"):
        workspace.read_text("large.txt", max_bytes=16)


@pytest.mark.skipif(
    not hasattr(os, "mkfifo") or not hasattr(os, "O_NONBLOCK"),
    reason="named pipes or non-blocking opens are unavailable",
)
def test_read_rejects_fifo_even_if_path_checks_report_regular_file(tmp_path, monkeypatch) -> None:
    workspace = Workspace(tmp_path / "workspace")
    fifo = workspace.root / "pipe"
    os.mkfifo(fifo)
    original_is_file = Path.is_file

    def report_regular_file(path):
        if path == fifo:
            return True
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", report_regular_file)
    with pytest.raises(WorkspaceError, match="regular file"):
        workspace.read_text("pipe")


@pytest.mark.skipif(
    not Workspace._supports_descriptor_paths(),
    reason="descriptor-relative filesystem operations are unavailable",
)
def test_write_stays_in_open_directory_if_parent_is_replaced(tmp_path, monkeypatch) -> None:
    workspace = Workspace(tmp_path / "workspace")
    parent = workspace.root / "nested"
    parent.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    backup = workspace.root / "nested-original"
    original_open_parent = workspace._open_parent_directory

    def open_then_replace(relative_path, create):
        descriptor, filename = original_open_parent(relative_path, create)
        if relative_path == "nested/new.txt":
            parent.rename(backup)
            parent.symlink_to(outside, target_is_directory=True)
        return descriptor, filename

    monkeypatch.setattr(workspace, "_open_parent_directory", open_then_replace)
    try:
        workspace.write_text("nested/new.txt", "safe")
    finally:
        parent.unlink()
        backup.rename(parent)

    assert (parent / "new.txt").read_text(encoding="utf-8") == "safe"
    assert not (outside / "new.txt").exists()


@pytest.mark.skipif(
    not Workspace._supports_descriptor_paths(),
    reason="descriptor-relative filesystem operations are unavailable",
)
def test_read_rejects_parent_symlink_replaced_after_path_validation(tmp_path, monkeypatch) -> None:
    workspace = Workspace(tmp_path / "workspace")
    parent = workspace.root / "nested"
    parent.mkdir()
    (parent / "notes.txt").write_text("workspace content", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "notes.txt").write_text("private content", encoding="utf-8")
    backup = workspace.root / "nested-original"
    original_resolve = workspace.resolve

    def replace_after_validation(relative_path):
        resolved = original_resolve(relative_path)
        if relative_path == "nested/notes.txt":
            parent.rename(backup)
            parent.symlink_to(outside, target_is_directory=True)
        return resolved

    monkeypatch.setattr(workspace, "resolve", replace_after_validation)
    try:
        with pytest.raises(WorkspaceError):
            workspace.read_text("nested/notes.txt")
    finally:
        parent.unlink()
        backup.rename(parent)


@pytest.mark.skipif(not hasattr(os, "link"), reason="hard links are unavailable")
def test_read_rejects_hard_linked_file(tmp_path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    outside = tmp_path / "private.txt"
    outside.write_text("private content", encoding="utf-8")
    os.link(outside, workspace.root / "project-copy.txt")

    with pytest.raises(WorkspaceError, match="Hard-linked"):
        workspace.read_text("project-copy.txt")


@pytest.mark.skipif(not hasattr(os, "link"), reason="hard links are unavailable")
def test_read_rechecks_link_count_after_open(tmp_path, monkeypatch) -> None:
    workspace = Workspace(tmp_path / "workspace")
    target = workspace.root / "notes.txt"
    target.write_text("workspace content", encoding="utf-8")
    alias = tmp_path / "late-hard-link"
    original_read = os.read

    def create_hard_link_during_read(descriptor, size):
        content = original_read(descriptor, size)
        if content and not alias.exists():
            os.link(target, alias)
        return content

    monkeypatch.setattr(os, "read", create_hard_link_during_read)
    with pytest.raises(WorkspaceError, match="Hard-linked"):
        workspace.read_text("notes.txt")


@pytest.mark.skipif(
    not Workspace._supports_descriptor_listing(),
    reason="descriptor-relative directory listing is unavailable",
)
def test_listing_does_not_follow_directory_replaced_with_symlink(tmp_path, monkeypatch) -> None:
    workspace = Workspace(tmp_path / "workspace")
    nested = workspace.root / "nested"
    nested.mkdir()
    backup = workspace.root / "nested-original"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("private content", encoding="utf-8")
    replaced = False
    original_open = os.open

    def replace_before_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal replaced
        if path == "nested" and dir_fd is not None and not replaced:
            nested.rename(backup)
            nested.symlink_to(outside, target_is_directory=True)
            replaced = True
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", replace_before_open)
    try:
        assert workspace.list_files() == []
    finally:
        if nested.is_symlink():
            nested.unlink()
        if backup.exists():
            backup.rename(nested)

    assert replaced
    assert (outside / "private.txt").read_text(encoding="utf-8") == "private content"
