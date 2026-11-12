# Contributing

Thanks for helping improve PixelForge.

Before opening a pull request:
1. Open or comment on an issue for substantial changes.
2. Keep changes focused and explain user-visible behavior.
3. Add or update tests for behavior changes.
4. Run: python -m pip install -e ".[dev]", pytest, and ruff check src tests.
5. Update docs when commands, configuration, security boundaries, or capabilities change.

Engineering principles:
- Provider-independent interfaces.
- Narrow tools with explicit input schemas.
- No hidden network calls or credential collection.
- No claims of successful builds without real verification.
- Mobile-friendly workflows and accessible documentation.
- Prefer deterministic tests over paid-API tests.

Use concise imperative commit messages.
