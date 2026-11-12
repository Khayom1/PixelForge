![PixelForge — AI game engineer](assets/pixelforge-banner.svg)

# PixelForge

**An open-source AI agent for building playable 2D games.**

Local models. Cloud models. Real project files. Verifiable builds.

[![CI](https://github.com/Khayom1/PixelForge/actions/workflows/ci.yml/badge.svg)](https://github.com/Khayom1/PixelForge/actions/workflows/ci.yml)
![MIT](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Status](https://img.shields.io/badge/status-early%20development-orange)

PixelForge is a provider-independent, open-source AI game engineer. It is being built to turn natural-language ideas into editable 2D game projects, then verify those projects with repeatable checks.

> **Honest status:** early development. The first vertical slice provides an OpenAI-compatible model adapter, bounded tool-calling loop, guarded project workspace, Phaser starter generator, CLI, and automated tests. A visual editor, autonomous visual testing, native mobile apps, and multi-engine support are not shipped yet.

## Shipped foundation

| Capability | Status |
| --- | --- |
| OpenAI-compatible provider (cloud or local endpoint) | Implemented |
| Bounded tool-calling runtime with request, call, and output budgets | Implemented |
| Workspace path, symlink, and sensitive-file protections | Implemented |
| Atomic text-file writes and protected scaffold generation | Implemented |
| Phaser 3 playable starter generator | Implemented |
| CLI: init, inspect, ask, and version output | Implemented |
| Automated tests, Ruff linting, and GitHub Actions CI | Implemented |
| Project memory, Godot, Pygame | Planned |
| Web/PWA, desktop packaging, visual QA | Planned |

## Quick start

Python 3.11+:

~~~bash
git clone https://github.com/Khayom1/PixelForge.git
cd PixelForge
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pixelforge init --engine phaser --name "Star Runner" --output ./star-runner
cd star-runner
npm install
npm run dev
~~~

The starter includes keyboard and touch controls and runs in modern browsers.

## Configure an AI model

PixelForge uses the OpenAI-compatible Chat Completions protocol:

~~~bash
export PIXELFORGE_BASE_URL="https://api.openai.com/v1"
export PIXELFORGE_MODEL="your-model-name"
export PIXELFORGE_API_KEY="your-api-key"
pixelforge ask --workspace ./star-runner --prompt "Add a restart button."
~~~

For local inference, point `PIXELFORGE_BASE_URL` to a local OpenAI-compatible server and use its model name. Leave the API key unset if the server does not require authentication.

Optional runtime limits:

~~~bash
export PIXELFORGE_TIMEOUT="60"
export PIXELFORGE_MAX_STEPS="8"
~~~

The provider timeout is limited to 1–600 seconds. Agent runs are bounded to 1–32 model steps.

## CLI

~~~bash
pixelforge --help
pixelforge --version
pixelforge init --engine phaser --name "Star Runner" --output ./star-runner
pixelforge inspect --workspace ./star-runner
pixelforge ask --workspace ./star-runner --prompt "Add a restart button."
~~~

Project generation refuses to overwrite an existing output directory. Review your changes before committing or publishing generated projects.

## Desktop and mobile

- Desktop: CLI is available; responsive web/PWA is planned.
- Android: CLI can run in a compatible terminal such as Termux; local model size depends on device resources.
- iOS: use a supported desktop or remote runtime from a mobile browser for now; native local execution is not claimed.
- Generated Phaser games support desktop and mobile browsers.

## Safety

Credentials are read from environment variables and are not exposed through workspace tools. Workspace operations reject path traversal and symlinks, block common secret/configuration paths, omit private metadata from listings, and enforce text-size limits. Provider responses, prompts, tool arguments, tool calls, and tool outputs are bounded. Generated project creation does not replace an existing directory and cleans up incomplete output after a failed generation.

The model cannot execute arbitrary shell commands, subprocesses, package installs, or network fetches in this release. These controls do not replace operating-system isolation: the CLI runs with the permissions of the local user. See [docs/SECURITY.md](docs/SECURITY.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development

~~~bash
python -m pip install -e ".[dev]"
pytest
ruff check src tests
~~~

CI tests Python 3.11–3.13, runs Ruff, and generates and production-builds a Phaser project using Node.js 24. See [CONTRIBUTING.md](CONTRIBUTING.md). The roadmap is in [docs/ROADMAP.md](docs/ROADMAP.md). Planned features are not advertised as shipped.

## Author

Created and maintained by [Khayom Abdurahmonov (@Khayom1)](https://github.com/Khayom1). MIT licensed.
