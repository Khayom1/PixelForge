"""PixelForge CLI — specialized AI agent for 2D game development."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pixelforge import __version__
from pixelforge.config import Settings
from pixelforge.provider import OpenAICompatibleProvider, ProviderError
from pixelforge.runtime import AgentRuntime
from pixelforge.tools import build_registry
from pixelforge.workspace import Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixelforge",
        description=(
            "PixelForge — open-source AI agent specialized for 2D game development.\n"
            "Works with any OpenAI-compatible API (cloud) or local model server."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  pixelforge init --name \"Star Runner\" --output ./star-runner\n"
            "  pixelforge ask --workspace ./star-runner --prompt \"Add a restart button\"\n"
            "  pixelforge inspect --workspace ./star-runner\n"
            "\n"
            "Environment:\n"
            "  PIXELFORGE_BASE_URL   OpenAI-compatible endpoint (default: https://api.openai.com/v1)\n"
            "  PIXELFORGE_MODEL     Model name (required for ask)\n"
            "  PIXELFORGE_API_KEY   API key (optional for local servers)\n"
            "  PIXELFORGE_TIMEOUT   Request timeout in seconds (1-600, default 60)\n"
            "  PIXELFORGE_MAX_STEPS Max agent steps (1-32, default 8)\n"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Generate a playable Phaser 3 starter project.")
    init.add_argument("--engine", choices=["phaser"], default="phaser")
    init.add_argument("--name", required=True, help="Display name of the game")
    init.add_argument("--output", default="./game", help="Output directory (default: ./game)")

    ask = sub.add_parser(
        "ask",
        help="Ask the AI agent to inspect or modify a game project.",
    )
    ask.add_argument("--workspace", required=True, help="Path to the game project directory")
    ask.add_argument("--prompt", required=True, help="Natural-language instruction for the agent")

    inspect = sub.add_parser("inspect", help="List files in a game project.")
    inspect.add_argument("--workspace", required=True, help="Path to the game project directory")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "init":
            output = Path(args.output).expanduser().resolve()
            result = build_registry(Workspace(output.parent)).execute(
                "create_phaser_game",
                json.dumps({"name": args.name, "directory": output.name}),
            )
            if not result["ok"]:
                raise RuntimeError(result["error"])
            print(f"Created Phaser 3 project at {output}")
            for item in result["result"]["files"]:
                print(f"  + {item}")
            print("\nNext steps:")
            print(f"  cd {output}")
            print("  npm install")
            print("  npm run dev")
            return

        workspace = Workspace(args.workspace)

        if args.command == "inspect":
            files = workspace.list_files()
            if files:
                print("\n".join(files))
            else:
                print("No project files found.")
            return

        # ask command
        settings = Settings.from_env()
        settings.validate_for_model_use()
        provider = OpenAICompatibleProvider(
            settings.base_url,
            settings.model,
            settings.api_key,
            settings.timeout_seconds,
        )
        runtime = AgentRuntime(
            provider,
            build_registry(workspace),
            max_steps=settings.max_agent_steps,
            trace_path=workspace.root / ".pixelforge" / "traces.jsonl",
        )
        print(runtime.run(args.prompt))
    except (ValueError, RuntimeError, ProviderError, OSError) as exc:
        print(f"PixelForge error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
