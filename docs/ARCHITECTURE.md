# Architecture

PixelForge separates model reasoning from project execution. The model is replaceable; tools and verification rules remain application-owned.

## Current request lifecycle

1. The CLI creates a workspace rooted at a user-selected directory.
2. Configuration selects an OpenAI-compatible endpoint and model.
3. The runtime sends messages and registered JSON tool schemas.
4. The model may request a tool. The registry dispatches only registered tools.
5. Workspace tools enforce path boundaries and UTF-8 size limits.
6. Tool results return to the model; the loop ends on a normal assistant response or a configured step limit.
7. JSONL traces record timestamps, step numbers, tool names, and success flags, but not prompts, API keys, or generated file contents.

## Design boundaries

- Provider: transport and response parsing.
- Runtime: bounded agent loop, tool dispatch, trace events.
- Tools: explicit capabilities available to the model.
- Workspace: filesystem boundary and text-file policy.
- Engine adapters: future engine-specific project generation, validation, and runtime control.
- Clients: CLI today; responsive web/PWA and remote runtime planned.

## Why a small tool surface first?

Unrestricted shell access creates security and reproducibility risks. The first release exposes narrow file operations and a deterministic Phaser scaffold. Build execution, browser automation, and visual inspection must be added behind explicit permission and sandbox boundaries.

Future engine adapters should inspect projects, validate structure, build/export, launch test sessions, and collect diagnostics. An adapter must never claim a successful build without a real engine result.
