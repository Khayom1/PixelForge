"""PixelForge CLI."""

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
        description="AI agent for 2D game development.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Generate a starter game project.")
    init.add_argument("--engine", choices=["phaser"], default="phaser")
    init.add_argument("--name", required=True)
    init.add_argument("--output", default="./game")
    ask = sub.add_parser("ask", help="Ask the configured agent to work in a project.")
    ask.add_argument("--workspace", required=True)
    ask.add_argument("--prompt", required=True)
    inspect = sub.add_parser("inspect", help="List files in a project.")
    inspect.add_argument("--workspace", required=True)
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
            print(f"Created Phaser project at {output}")
            for item in result["result"]["files"]:
                print(f"  + {item}")
            return
        workspace = Workspace(args.workspace)
        if args.command == "inspect":
            files = workspace.list_files()
            if files:
                print("\n".join(files))
            else:
                print("No project files found.")
            return
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
