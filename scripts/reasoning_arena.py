from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

from vibe.core.paths import SESSION_LOG_DIR
from vibe.utils.io import read_safe

type Policy = Literal["low", "high", "auto"]


class ArenaTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    prompt: str
    expected_auto_level: Literal["low", "high"]


class ArenaResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    policy: Policy
    response: str
    routed_level: str | None = None
    routing_reason: str | None = None
    stability: float | None = None
    elapsed_seconds: float
    total_tokens: int | None = None
    cost: float | None = None
    error: str | None = None


class ArenaReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: str
    model: str
    tasks: list[ArenaTask]
    results: list[ArenaResult]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Vibe thinking policies")
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path(__file__).with_name("reasoning_arena_tasks.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("arena-results"))
    parser.add_argument("--model", default="mistral-vibe-cli-latest")
    parser.add_argument("--alias", default="mistral-medium-3.5")
    parser.add_argument(
        "--policies", nargs="+", choices=("low", "high", "auto"), default=None
    )
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def load_tasks(path: Path, limit: int | None = None) -> list[ArenaTask]:
    payload = json.loads(read_safe(path, raise_on_error=True).text)
    tasks = [ArenaTask.model_validate(item) for item in payload]
    return tasks[:limit] if limit is not None else tasks


def _model_override(model: str, alias: str, policy: Policy) -> str:
    return json.dumps([
        {
            "name": model,
            "provider": "mistral",
            "alias": alias,
            "display_name": alias,
            "thinking": policy,
            "supports_images": True,
        }
    ])


async def run_case(
    task: ArenaTask, policy: Policy, *, model: str, alias: str
) -> ArenaResult:
    env = dict(os.environ)
    env["VIBE_ACTIVE_MODEL"] = alias
    env["VIBE_MODELS"] = _model_override(model, alias, policy)
    started = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "vibe.cli.entrypoint",
        "-p",
        task.prompt,
        "--output",
        "json",
        "--max-turns",
        "1",
        "--trust",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await process.communicate()
    elapsed = time.perf_counter() - started
    if process.returncode != 0:
        return ArenaResult(
            task_id=task.id,
            policy=policy,
            response="",
            elapsed_seconds=elapsed,
            error=stderr.decode(errors="replace").strip(),
        )
    try:
        history = json.loads(stdout)
        return _result_from_history(task.id, policy, history, elapsed)
    except (json.JSONDecodeError, ValueError) as exc:
        return ArenaResult(
            task_id=task.id,
            policy=policy,
            response="",
            elapsed_seconds=elapsed,
            error=str(exc),
        )


def _result_from_history(
    task_id: str, policy: Policy, history: list[dict[str, object]], elapsed: float
) -> ArenaResult:
    routing = next(
        (detail for entry in history if (detail := _routing_detail(entry)) is not None),
        None,
    )
    assistant = next(
        (
            entry
            for entry in reversed(history)
            if entry.get("type") == "message" and entry.get("role") == "assistant"
        ),
        None,
    )
    if assistant is None:
        raise ValueError("Vibe returned no assistant message")
    response = _content_text(assistant.get("content"))
    session_id = str(assistant.get("sessionId", ""))
    tokens, cost = _session_metrics(session_id)
    return ArenaResult(
        task_id=task_id,
        policy=policy,
        response=response,
        routed_level=str(routing.get("level")) if routing else None,
        routing_reason=str(routing.get("reason")) if routing else None,
        stability=float(routing["stability"]) if routing else None,
        elapsed_seconds=elapsed,
        total_tokens=tokens,
        cost=cost,
    )


def _routing_detail(entry: dict[str, object]) -> dict[str, object] | None:
    if entry.get("type") != "notice":
        return None
    detail = entry.get("detail")
    if not isinstance(detail, dict) or detail.get("kind") != "reasoning_routed":
        return None
    return cast(dict[str, object], detail)


def _content_text(content: object) -> str:
    if not isinstance(content, list):
        return ""
    return "".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _session_metrics(session_id: str) -> tuple[int | None, float | None]:
    if not session_id:
        return None, None
    prefix = session_id.split("-", maxsplit=1)[0]
    matches = list(SESSION_LOG_DIR.path.glob(f"session_*_{prefix}/meta.json"))
    if not matches:
        return None, None
    metadata = json.loads(read_safe(matches[-1], raise_on_error=True).text)
    stats = metadata.get("stats", {})
    if not isinstance(stats, dict):
        return None, None
    tokens = stats.get("session_total_llm_tokens")
    cost = stats.get("session_cost")
    return (
        int(tokens) if isinstance(tokens, int | float) else None,
        float(cost) if isinstance(cost, int | float) else None,
    )


def render_markdown(report: ArenaReport) -> str:
    summaries = {
        policy: _policy_summary(report.results, policy)
        for policy in ("low", "high", "auto")
    }
    lines = [
        "# Vibe Reasoning Arena",
        "",
        f"Model: `{report.model}`  ",
        f"Created: {report.created_at}",
        "",
        "| Task | Policy | Routed | Tokens | Cost | Seconds |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    tasks = {task.id: task for task in report.tasks}
    for result in report.results:
        task = tasks[result.task_id]
        routed = result.routed_level or "—"
        tokens = str(result.total_tokens) if result.total_tokens is not None else "—"
        cost = f"${result.cost:.5f}" if result.cost is not None else "—"
        lines.append(
            f"| {task.title} | {result.policy} | {routed} | {tokens} | "
            f"{cost} | {result.elapsed_seconds:.2f} |"
        )
    lines.extend([
        "",
        "## Policy totals",
        "",
        "| Policy | Tokens | Cost | Seconds |",
        "| --- | ---: | ---: | ---: |",
    ])
    for policy, summary in summaries.items():
        lines.append(
            f"| {policy} | {summary['tokens']:.0f} | ${summary['cost']:.5f} | "
            f"{summary['seconds']:.2f} |"
        )
    high = summaries["high"]
    auto = summaries["auto"]
    if high["cost"] > 0 and high["seconds"] > 0:
        cost_saving = (high["cost"] - auto["cost"]) / high["cost"] * 100
        time_saving = (high["seconds"] - auto["seconds"]) / high["seconds"] * 100
        lines.extend([
            "",
            f"AutoThink vs High: **{cost_saving:.1f}% cost reduction**, "
            f"**{time_saving:.1f}% latency reduction**.",
        ])
    auto_results = [result for result in report.results if result.policy == "auto"]
    correct = sum(
        result.routed_level == tasks[result.task_id].expected_auto_level
        for result in auto_results
    )
    lines.extend([
        "",
        f"AutoThink routing agreement: **{correct}/{len(auto_results)}**",
        "",
        "## Responses",
        "",
    ])
    for result in report.results:
        lines.extend([
            f"### {tasks[result.task_id].title} — {result.policy}",
            "",
            result.error or result.response,
            "",
        ])
    return "\n".join(lines)


def _policy_summary(results: list[ArenaResult], policy: Policy) -> dict[str, float]:
    selected = [result for result in results if result.policy == policy]
    return {
        "tokens": float(sum(result.total_tokens or 0 for result in selected)),
        "cost": sum(result.cost or 0 for result in selected),
        "seconds": sum(result.elapsed_seconds for result in selected),
    }


async def run() -> int:
    args = parse_arguments()
    tasks = load_tasks(args.tasks, args.limit)
    policies: list[Policy] = args.policies or ["low", "high", "auto"]
    results: list[ArenaResult] = []
    for task in tasks:
        for policy in policies:
            print(f"Running {task.id} with {policy}...", flush=True)
            results.append(
                await run_case(task, policy, model=args.model, alias=args.alias)
            )
    report = ArenaReport(
        created_at=datetime.now(UTC).isoformat(),
        model=args.alias,
        tasks=tasks,
        results=results,
    )
    await asyncio.to_thread(args.output_dir.mkdir, parents=True, exist_ok=True)
    json_path = args.output_dir / "report.json"
    markdown_path = args.output_dir / "report.md"
    await asyncio.to_thread(
        json_path.write_text, report.model_dump_json(indent=2), encoding="utf-8"
    )
    await asyncio.to_thread(
        markdown_path.write_text, render_markdown(report), encoding="utf-8"
    )
    print(f"Wrote {json_path} and {markdown_path}")
    return int(any(result.error for result in results))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
