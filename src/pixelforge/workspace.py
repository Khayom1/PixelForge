"""Guarded text-file operations within a user-selected workspace."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_PROTECTED_NAMES = {
    ".git", ".pixelforge", ".ssh", ".aws", ".azure", ".docker",
    ".env", ".netrc", ".npmrc", ".pypirc", "id_rsa", "id_ed25519",
    "id_ecdsa", "credentials",
}
_PROTECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
_IGNORED_DIRS = {
    ".git", ".pixelforge", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".next", "dist", "build",
    ".cache",
}


class WorkspaceError(ValueError):
    """Workspace path or file policy violation."""


class Workspace:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _is_protected(parts: tuple[str, ...]) -> bool:
        for part in parts:
            lowered = part.lower()
            if lowered in _PROTECTED_NAMES or lowered.startswith(".env."):
                return True
            if Path(lowered).suffix in _PROTECTED_SUFFIXES:
                return True
        return False

    def resolve(self, relative_path: str) -> Path:
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or "\x00" in relative_path
            or "\\" in relative_path
        ):
            raise WorkspaceError("A non-empty relative path using forward slashes is required.")
        candidate_path = Path(relative_path)
        if candidate_path.is_absolute():
            raise WorkspaceError("Absolute paths are not allowed.")
        if any(part == ".." for part in candidate_path.parts):
            raise WorkspaceError("Parent-directory traversal is not allowed.")
        if self._is_protected(candidate_path.parts):
            raise WorkspaceError("Access to protected configuration, credential, and metadata paths is denied.")

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
        result: list[str] = []
        for root, directories, filenames in os.walk(self.root, topdown=True, followlinks=False):
            base = Path(root)
            directories[:] = sorted(
                name for name in directories
                if name.lower() not in _IGNORED_DIRS
                and not name.lower().startswith(".pixelforge-stage-")
                and not (base / name).is_symlink()
                and not self._is_protected((name,))
            )
            for name in sorted(filenames):
                path = base / name
                relative = path.relative_to(self.root)
                if path.is_symlink() or self._is_protected(relative.parts):
                    continue
                if path.is_file():
                    result.append(relative.as_posix())
                    if len(result) >= limit:
                        return result
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
        if not isinstance(content, str):
            raise WorkspaceError("Only UTF-8 text content is supported.")
        encoded = content.encode("utf-8")
        if len(encoded) > max_bytes:
            raise WorkspaceError("Content exceeds the write limit.")
        path = self.resolve(relative_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise WorkspaceError(f"Could not prepare output directory: {exc}") from exc
        path = self.resolve(relative_path)
        if path.exists() and not path.is_file():
            raise WorkspaceError("Target exists and is not a regular file.")

        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".pixelforge-write-", dir=path.parent, delete=False
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(encoded)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, path)
            temporary_name = None
        except OSError as exc:
            raise WorkspaceError(f"Could not write project file: {exc}") from exc
        finally:
            if temporary_name:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
        return path.relative_to(self.root).as_posix()
