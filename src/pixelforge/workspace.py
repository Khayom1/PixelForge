"""Guarded text-file operations within a user-selected workspace."""

from __future__ import annotations

from pathlib import Path


class WorkspaceError(ValueError):
    """Workspace path or file policy violation."""


class Workspace:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative_path: str) -> Path:
        candidate_path = Path(relative_path)
        if candidate_path.is_absolute() or not relative_path or "\x00" in relative_path:
            raise WorkspaceError("A non-empty relative path is required.")
        if ".." in candidate_path.parts:
            raise WorkspaceError("Parent-directory traversal is not allowed.")
        candidate = (self.root / candidate_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("Path escapes the workspace.") from exc
        current = self.root
        for part in candidate_path.parts:
            if part in ("", "."):
                continue
            current = current / part
            if current.is_symlink():
                raise WorkspaceError("Symlinks are not allowed.")
        return candidate

    def list_files(self, limit: int = 200) -> list[str]:
        if limit < 1:
            raise WorkspaceError("limit must be positive.")
        result = []
        for path in sorted(self.root.rglob("*")):
            if len(result) >= limit:
                break
            if not path.is_symlink() and path.is_file():
                result.append(path.relative_to(self.root).as_posix())
        return result

    def read_text(self, relative_path: str, max_bytes: int = 256_000) -> str:
        path = self.resolve(relative_path)
        if not path.is_file():
            raise WorkspaceError("File does not exist.")
        if path.stat().st_size > max_bytes:
            raise WorkspaceError("File exceeds the read limit.")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise WorkspaceError("Only UTF-8 text files are supported.") from exc

    def write_text(self, relative_path: str, content: str, max_bytes: int = 256_000) -> str:
        if len(content.encode("utf-8")) > max_bytes:
            raise WorkspaceError("Content exceeds the write limit.")
        path = self.resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path = self.resolve(relative_path)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path.relative_to(self.root).as_posix()
