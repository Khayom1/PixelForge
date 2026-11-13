# PixelForge

**Open-source AI agent specialized for 2D game development.**

Works with cloud APIs **and** local models. Turns natural-language ideas into real, editable, playable 2D game projects.

[![CI](https://github.com/Khayom1/PixelForge/actions/workflows/ci.yml/badge.svg)](https://github.com/Khayom1/PixelForge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## What it is

PixelForge is a focused AI game engineer. It is not a general chatbot.

It can:

- Create a complete playable Phaser 3 starter (Vite + keyboard + touch)
- Inspect and modify real project files
- Implement features, fix bugs, and improve game logic
- Work with any OpenAI-compatible endpoint (OpenAI, Groq, Together, Ollama, LM Studio, vLLM, etc.)

## Current status (v0.2.0)

| Capability | Status |
|---|---|
| OpenAI-compatible provider (cloud + local) | Done |
| Specialized 2D-game system prompt | Done |
| Bounded tool-calling agent loop | Done |
| Guarded workspace (path / symlink / secrets) | Done |
| Phaser 3 playable starter generator | Done |
| Project summary + file tools | Done |
| CLI (`init`, `ask`, `inspect`) | Done |
| Automated tests + CI | Done |
| Godot / Pygame adapters | Planned |
| Visual / browser testing | Planned |
| Project memory across sessions | Planned |

Honest note: this is a solid foundation, not a finished multi-engine studio.

---

## Quick start

Requires **Python 3.11+**.

```bash
git clone https://github.com/Khayom1/PixelForge.git
cd PixelForge
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 1. Create a new game

```bash
pixelforge init --name "Star Runner" --output ./star-runner
cd star-runner
npm install
npm run dev
```

The generated game includes keyboard + touch controls and is playable in the browser.

### 2. Configure an AI model

**Cloud (example: OpenAI)**

```bash
export PIXELFORGE_BASE_URL="https://api.openai.com/v1"
export PIXELFORGE_MODEL="gpt-4o-mini"
export PIXELFORGE_API_KEY="sk-..."
```

**Local (example: Ollama)**

```bash
export PIXELFORGE_BASE_URL="http://localhost:11434/v1"
export PIXELFORGE_MODEL="qwen2.5-coder:14b"
# API key not required for most local servers
```

**Other local options that work:** LM Studio, llama.cpp server, vLLM, text-generation-webui, any OpenAI-compatible endpoint.

### 3. Ask the agent to modify the game

```bash
pixelforge ask --workspace ./star-runner --prompt "Add a restart button that appears when the player falls."
```

---

## CLI

```bash
pixelforge --version
pixelforge init --name "My Game" --output ./my-game
pixelforge inspect --workspace ./my-game
pixelforge ask --workspace ./my-game --prompt "Make the player jump higher"
```

### Environment variables

| Variable | Meaning | Default |
|---|---|---|
| `PIXELFORGE_BASE_URL` | OpenAI-compatible base URL | `https://api.openai.com/v1` |
| `PIXELFORGE_MODEL` | Model name | *(required for ask)* |
| `PIXELFORGE_API_KEY` | API key | optional (needed for most cloud providers) |
| `PIXELFORGE_TIMEOUT` | Timeout in seconds (1–600) | `60` |
| `PIXELFORGE_MAX_STEPS` | Max agent steps (1–32) | `8` |

---

## How it works

1. You give a natural-language instruction.
2. The agent receives a specialized 2D-game system prompt.
3. It inspects the project with tools (`list_project_files`, `get_project_summary`, `read_text_file`).
4. It makes precise file changes with `write_text_file` or creates a new game with `create_phaser_game`.
5. Every run is bounded (steps, tool calls, byte budgets) and leaves a compact JSONL trace.

The model never gets unrestricted shell access. All file operations stay inside the chosen workspace.

---

## Safety

- Path traversal and symlinks are rejected
- Common secret/config paths are blocked
- Tool arguments and results have hard size limits
- Agent steps and tool calls are capped
- API keys stay in environment variables and are never written to the workspace

See [docs/SECURITY.md](docs/SECURITY.md).

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```

CI tests Python 3.11–3.13 and builds a real Phaser project.

---

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

Next priorities: project memory, richer game skills, Godot/Pygame adapters, and safe verification loops.

---

## License

MIT — free for personal and commercial use.

Created and maintained by [Khayom Abdurahmonov (@Khayom1)](https://github.com/Khayom1).
