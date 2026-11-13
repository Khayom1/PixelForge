# Architecture

PixelForge separates model reasoning from project execution. The model is replaceable; tools and verification rules remain application-owned.

## Request lifecycle

1. CLI creates a workspace rooted at a user-selected directory.
2. Configuration selects an OpenAI-compatible endpoint and model (cloud or local).
3. Runtime injects a specialized 2D-game system prompt.
4. Runtime sends messages + registered JSON tool schemas to the provider.
5. Model may request tools. Only registered tools are dispatched.
6. Workspace tools enforce path boundaries, size limits, and secret-path denial.
7. Tool results return to the model. Loop ends on a final answer or step limit.
8. Compact JSONL traces record timestamps, step numbers, tool names, and success flags — never prompts, keys, or full file contents.

## Components

| Component | Responsibility |
|---|---|
| `provider.py` | Transport + response parsing for any OpenAI-compatible endpoint |
| `prompts.py` | Specialized system prompt for 2D game development |
| `runtime.py` | Bounded agent loop, tool dispatch, tracing |
| `tools.py` | Explicit capabilities exposed to the model |
| `workspace.py` | Filesystem boundary and text-file policy |
| `cli.py` | User entry point |
| `config.py` | Environment-based settings |

## Design principles

- **Narrow tool surface first.** Unrestricted shell access creates security and reproducibility risks.
- **Honest status.** Planned features are never advertised as shipped.
- **Provider independence.** Any OpenAI-compatible server works (cloud or local).
- **Deterministic scaffolds.** Generated Phaser projects are complete and playable.
- **Safety by default.** Path traversal, symlinks, hardlinks, and secret paths are rejected.

## Future engine adapters

Future adapters should:

1. Inspect projects and validate structure
2. Build / export safely
3. Launch test sessions
4. Collect diagnostics

An adapter must never claim a successful build without a real engine result.
