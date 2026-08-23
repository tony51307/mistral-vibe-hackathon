"""Prewarm live solver cache for the Streamlit demo."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from vibe_client import VibeCliClient

from game import LIVE_SOLVER_CACHE_PATH, GameConfig, new_game, play_round


def _cache_size() -> int:
    if not LIVE_SOLVER_CACHE_PATH.exists():
        return 0
    data: dict[str, Any] = json.loads(LIVE_SOLVER_CACHE_PATH.read_text())
    return len(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()

    state = new_game(
        GameConfig(use_live_api=True, solver_backend="vibe_cli", n_rounds=args.rounds)
    )
    client = VibeCliClient()
    started_at = time.time()

    print(f"cache_path={LIVE_SOLVER_CACHE_PATH}")
    for hand in range(1, args.rounds + 1):
        record = play_round(state, client)
        winners = ", ".join(record.get("winners", [])) or "none"
        print(
            f"hand {hand}/{args.rounds} complete "
            f"cache_entries={_cache_size()} winners={winners}",
            flush=True,
        )
        if state.finished:
            break

    elapsed = time.time() - started_at
    print(f"done elapsed_seconds={elapsed:.1f} cache_entries={_cache_size()}")


if __name__ == "__main__":
    main()
