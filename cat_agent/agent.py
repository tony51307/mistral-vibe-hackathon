"""Create a Mistral image-generation agent and draw a cat for each player."""

from __future__ import annotations

from pathlib import Path
import os
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PORTRAITS = Path(__file__).resolve().parent / "portraits"
AGENT_ID_PATH = Path(__file__).resolve().parent / ".agent_id"

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "main_ui" / ".env")

PLAYER_PROMPTS = {
    "fast": (
        "Generate a sleek lightning-fast tabby cat portrait at a poker table, "
        "electric blue eyes, a gold lightning streak on its forehead, motion blur, "
        "casino lighting, square portrait."
    ),
    "always_think": (
        "Generate a thoughtful tuxedo cat portrait wearing tiny round glasses, "
        "sitting at a poker table with a notebook, deep in thought, warm lamp light, "
        "square portrait."
    ),
    "dynamic": (
        "Generate an orange cat in an office playing poker, one paw on chips, "
        "playful and focused at the same time, cinematic portrait, square crop."
    ),
}


def _client():
    from mistralai.client import Mistral

    key = os.getenv("MISTRAL_API_KEY", "").strip()
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is missing from .env")
    return Mistral(api_key=key)


def _model() -> str:
    return os.getenv("MISTRAL_IMAGE_MODEL", "mistral-medium-latest")


def get_or_create_agent(client: Any | None = None) -> str:
    """Reuse a saved agent id, or create the official image_generation agent."""
    client = client or _client()
    if AGENT_ID_PATH.exists():
        saved = AGENT_ID_PATH.read_text(encoding="utf-8").strip()
        if saved:
            return saved
    image_agent = client.beta.agents.create(
        model=_model(),
        name="Pay-to-Think Cat Portraits",
        description="Agent used to generate cat portraits for table seats.",
        instructions="Use the image generation tool when you have to create images.",
        tools=[{"type": "image_generation"}],
        completion_args={"temperature": 0.3, "top_p": 0.95},
    )
    AGENT_ID_PATH.write_text(image_agent.id, encoding="utf-8")
    return image_agent.id


def _file_ids(response: Any) -> list[str]:
    from mistralai.client.models import ToolFileChunk

    found: list[str] = []
    for entry in getattr(response, "outputs", None) or []:
        content = getattr(entry, "content", None)
        if not isinstance(content, list):
            continue
        for chunk in content:
            if isinstance(chunk, ToolFileChunk):
                found.append(chunk.file_id)
                continue
            if isinstance(chunk, dict) and chunk.get("file_id"):
                found.append(str(chunk["file_id"]))
                continue
            file_id = getattr(chunk, "file_id", None)
            if file_id:
                found.append(str(file_id))
    return found


def generate_cat(prompt: str, dest: Path, *, client: Any | None = None, agent_id: str | None = None) -> Path:
    client = client or _client()
    agent_id = agent_id or get_or_create_agent(client)
    response = client.beta.conversations.start(agent_id=agent_id, inputs=prompt)
    ids = _file_ids(response)
    if not ids:
        raise RuntimeError(f"image generation returned no file for: {prompt[:60]}")
    downloaded = client.files.download(file_id=ids[-1])
    data = downloaded.read() if hasattr(downloaded, "read") else downloaded
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def generate_portraits(*, force: bool = False, players: list[str] | None = None) -> dict[str, Path]:
    client = _client()
    agent_id = get_or_create_agent(client)
    chosen = players or list(PLAYER_PROMPTS)
    paths: dict[str, Path] = {}
    for player_id in chosen:
        dest = PORTRAITS / f"{player_id}.png"
        if dest.exists() and dest.stat().st_size > 0 and not force:
            paths[player_id] = dest
            continue
        paths[player_id] = generate_cat(PLAYER_PROMPTS[player_id], dest, client=client, agent_id=agent_id)
    return paths


def portrait_path(player_id: str) -> Path | None:
    path = PORTRAITS / f"{player_id}.png"
    return path if path.exists() and path.stat().st_size > 0 else None


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate Mistral cat portraits for table players")
    parser.add_argument("--force", action="store_true", help="regenerate even if files exist")
    parser.add_argument("--player", action="append", choices=sorted(PLAYER_PROMPTS), help="only these seats")
    args = parser.parse_args()
    paths = generate_portraits(force=args.force, players=args.player)
    for player_id, path in paths.items():
        print(f"{player_id}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
