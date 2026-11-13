"""Guarded text-file operations within a user-selected workspace."""

from __future__ import annotations

import os
import stat
import tempfile
import uuid
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
    def _supports_descriptor_paths() -> bool:
        required = (os.open, os.mkdir, os.rename, os.stat, os.unlink)
        return (
            hasattr(os, "O_DIRECTORY")
            and hasattr(os, "O_NOFOLLOW")
            and all(operation in os.supports_dir_fd for operation in required)
            and os.stat in os.supports_follow_symlinks
        )

    def _open_root_directory(self) -> int:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = os.open(self.root.anchor, directory_flags)
        try:
            for part in self.root.parts[1:]:
                next_descriptor = os.open(part, directory_flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def _open_parent_directory(self, relative_path: str, create: bool) -> tuple[int, str]:
        parts = Path(relative_path).parts
        if not parts:
            raise WorkspaceError("A file path is required.")

        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = self._open_root_directory()
        try:
            for part in parts[:-1]:
                try:
                    next_descriptor = os.open(part, directory_flags, dir_fd=descriptor)
                except FileNotFoundError:
                    if not create:
                        raise
                    try:
                        os.mkdir(part, 0o700, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    next_descriptor = os.open(part, directory_flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
            return descriptor, parts[-1]
        except BaseException:
            os.close(descriptor)
            raise

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
            raise WorkspaceError(
                "Access to protected configuration, credential, and metadata paths is denied."
            )

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
        if max_bytes < 0:
            raise WorkspaceError("max_bytes must not be negative.")
        path = self.resolve(relative_path)
        try:
            if self._supports_descriptor_paths():
                parent_descriptor, filename = self._open_parent_directory(
                    relative_path, create=False
                )
                try:
                    descriptor = os.open(
                        filename,
                        os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
                        dir_fd=parent_descriptor,
                    )
                finally:
                    os.close(parent_descriptor)
            else:
                descriptor = os.open(
                    path,
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0),
                )
        except FileNotFoundError as exc:
            raise WorkspaceError("File does not exist.") from exc
        except OSError as exc:
            raise WorkspaceError("File cannot be opened safely.") from exc

        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise WorkspaceError("File is not a regular file.")
            if metadata.st_nlink != 1:
                raise WorkspaceError("Hard-linked files are not allowed.")
            if metadata.st_size > max_bytes:
                raise WorkspaceError("File exceeds the read limit.")

            content = bytearray()
            while len(content) <= max_bytes:
                chunk = os.read(descriptor, min(64 * 1024, max_bytes + 1 - len(content)))
                if not chunk:
                    break
                content.extend(chunk)
            if len(content) > max_bytes:
                raise WorkspaceError("File exceeds the read limit.")
            if os.fstat(descriptor).st_nlink != 1:
                raise WorkspaceError("Hard-linked files are not allowed.")
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise WorkspaceError("Only UTF-8 text files are supported.") from exc
        except OSError as exc:
            raise WorkspaceError("File could not be read safely.") from exc
        finally:
            os.close(descriptor)

    def write_text(self, relative_path: str, content: str, max_bytes: int = 256_000) -> str:
        if not isinstance(content, str):
            raise WorkspaceError("Only UTF-8 text content is supported.")
        encoded = content.encode("utf-8")
        if len(encoded) > max_bytes:
            raise WorkspaceError("Content exceeds the write limit.")
        path = self.resolve(relative_path)

        if self._supports_descriptor_paths():
            try:
                parent_descriptor, filename = self._open_parent_directory(
                    relative_path, create=True
                )
            except OSError as exc:
                raise WorkspaceError(f"Could not prepare output directory: {exc}") from exc
            temporary_name = f".pixelforge-write-{uuid.uuid4().hex}"
            temporary_descriptor: int | None = None
            temporary_exists = False
            try:
                try:
                    existing = os.stat(
                        filename, dir_fd=parent_descriptor, follow_symlinks=False
                    )
                except FileNotFoundError:
                    existing = None
                if existing is not None and not stat.S_ISREG(existing.st_mode):
                    raise WorkspaceError("Target exists and is not a regular file.")

                temporary_descriptor = os.open(
                    temporary_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent_descriptor,
                )
                temporary_exists = True
                stream = os.fdopen(temporary_descriptor, "wb")
                temporary_descriptor = None
                with stream as temporary:
                    temporary.write(encoded)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.rename(
                    temporary_name,
                    filename,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                )
                temporary_exists = False
            except WorkspaceError:
                raise
            except OSError as exc:
                raise WorkspaceError(f"Could not write project file: {exc}") from exc
            finally:
                if temporary_descriptor is not None:
                    os.close(temporary_descriptor)
                if temporary_exists:
                    try:
                        os.unlink(temporary_name, dir_fd=parent_descriptor)
                    except FileNotFoundError:
                        pass
                os.close(parent_descriptor)
        else:
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
