"""Explicit tools exposed to the model."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from pixelforge.workspace import Workspace, WorkspaceError


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters
        }}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, raw_arguments: str) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            args = json.loads(raw_arguments or "{}")
            if not isinstance(args, dict):
                raise ValueError("Arguments must be a JSON object.")
            return {"ok": True, "result": tool.handler(args)}
        except (json.JSONDecodeError, ValueError, WorkspaceError, OSError) as exc:
            return {"ok": False, "error": str(exc)}


def required_string(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string.")
    return value


def create_phaser_game(workspace: Workspace, name: str, directory: str) -> dict[str, Any]:
    slug = re.sub(r"[^a-z0-9-]+", "-", directory.lower()).strip("-")
    if not slug or slug != directory.lower():
        raise ValueError("directory must use lowercase letters, numbers, and hyphens.")
    title = name.strip()
    if not title or len(title) > 64:
        raise ValueError("name must contain 1 to 64 characters.")
    prefix = slug + "/"
    files = {
        "package.json": json.dumps({
            "name": slug, "version": "1.0.0", "private": True,
            "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
            "dependencies": {"phaser": "^3.90.0"},
            "devDependencies": {"vite": "^6.0.0"}
        }, indent=2) + "\n",
        "index.html": f'''<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
</head>
<body>
<main id="game" aria-label="{title} game"></main>
<script type="module" src="/src/main.js"></script>
</body>
</html>
''',
        "src/main.js": """import Phaser from 'phaser';
import './style.css';

class MainScene extends Phaser.Scene {
  constructor() { super('main'); this.score = 0; }
  create() {
    const { width, height } = this.scale;
    this.add.rectangle(width / 2, height / 2, width, height, 0x17243a);
    this.add.text(20, 18, 'STAR RUNNER', { fontSize: '22px', color: '#ffffff' });
    this.scoreText = this.add.text(20, 48, 'Stars: 0', { color: '#b9d7ff' });
    this.platforms = this.physics.add.staticGroup();
    const ground = this.add.rectangle(width / 2, height - 24, width, 48, 0x456b58);
    this.physics.add.existing(ground, true);
    this.platforms.add(ground);
    this.player = this.add.rectangle(90, height - 90, 32, 42, 0x69c4ff);
    this.physics.add.existing(this.player);
    this.player.body.setCollideWorldBounds(true);
    this.physics.add.collider(this.player, this.platforms);
    this.star = this.add.circle(width * 0.68, height - 100, 13, 0xffd166);
    this.physics.add.existing(this.star, true);
    this.physics.add.overlap(this.player, this.star, () => {
      this.score += 1;
      this.scoreText.setText('Stars: ' + this.score);
      this.star.setPosition(Phaser.Math.Between(40, width - 40),
        Phaser.Math.Between(90, Math.max(100, height - 100)));
      this.star.body.updateFromGameObject();
    });
    this.keys = this.input.keyboard.createCursorKeys();
    this.input.keyboard.on('keydown-SPACE', () => this.jump());
    this.button(width - 150, 'LEFT', () => this.player.body.setVelocityX(-220));
    this.button(width - 85, 'RIGHT', () => this.player.body.setVelocityX(220));
    this.button(width - 35, 'JUMP', () => this.jump());
  }
  button(x, label, action) {
    const item = this.add.text(x, this.scale.height - 18, label, {
      fontSize: '13px', color: '#fff', backgroundColor: '#314b6b',
      padding: { x: 10, y: 12 }
    }).setOrigin(0.5).setInteractive();
    item.on('pointerdown', action);
  }
  jump() {
    if (this.player.body.blocked.down || this.player.body.touching.down) {
      this.player.body.setVelocityY(-420);
    }
  }
  update() {
    if (this.keys.left.isDown) this.player.body.setVelocityX(-220);
    else if (this.keys.right.isDown) this.player.body.setVelocityX(220);
    else this.player.body.setVelocityX(0);
    if (this.keys.up.isDown) this.jump();
  }
}
new Phaser.Game({
  type: Phaser.AUTO, parent: 'game', width: 800, height: 480,
  backgroundColor: '#17243a',
  physics: { default: 'arcade', arcade: { gravity: { y: 900 }, debug: false } },
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: [MainScene]
});
""",
        "src/style.css": """* { box-sizing: border-box; }
html, body { margin: 0; width: 100%; min-height: 100%; background: #101827; }
body { min-height: 100dvh; display: grid; place-items: center; overflow: hidden; }
#game { width: min(100vw, 960px); height: min(100dvh, 576px); }
canvas { display: block; max-width: 100%; max-height: 100%; touch-action: none; }
""",
        "README.md": f"""# {title}

Phaser 3 starter generated by PixelForge.

~~~bash
npm install
npm run dev
~~~

Use arrow keys and Space on desktop. Touch controls are available on mobile.
"""
    }
    written = []
    for path, content in files.items():
        workspace.write_text(prefix + path, content)
        written.append(prefix + path)
    return {"project": slug, "files": written, "engine": "Phaser 3"}


def build_registry(workspace: Workspace) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(Tool(
        "list_project_files", "List relative file paths in the current project.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        lambda _args: {"files": workspace.list_files()},
    ))
    registry.register(Tool(
        "read_text_file", "Read a UTF-8 text file in the current project.",
        {"type": "object", "properties": {"path": {"type": "string"}},
         "required": ["path"], "additionalProperties": False},
        lambda args: {"path": required_string(args, "path"),
                      "content": workspace.read_text(required_string(args, "path"))},
    ))
    registry.register(Tool(
        "write_text_file", "Write a UTF-8 text file in the current project.",
        {"type": "object", "properties": {"path": {"type": "string"},
         "content": {"type": "string"}}, "required": ["path", "content"],
         "additionalProperties": False},
        lambda args: {"written": workspace.write_text(
            required_string(args, "path"), required_string(args, "content"))},
    ))
    registry.register(Tool(
        "create_phaser_game", "Generate a playable Phaser 3 starter project.",
        {"type": "object", "properties": {"name": {"type": "string"},
         "directory": {"type": "string"}}, "required": ["name", "directory"],
         "additionalProperties": False},
        lambda args: create_phaser_game(workspace, required_string(args, "name"),
                                        required_string(args, "directory")),
    ))
    return registry
