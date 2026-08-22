from __future__ import annotations

from problems import Problem


def answer_prompt(problem: Problem, tier: str) -> str:
    return f"""You are playing a short-answer reasoning game.
Reasoning tier purchased: {tier}

Return JSON only:
{{"answer": "short final answer"}}

Problem:
{problem.question}
"""


def table_talk_prompt(agent_name: str, category: str, bankroll: float) -> str:
    return f"""Write one public table-talk message under 100 characters.
Agent: {agent_name}
Category: {category}
Bankroll: ${bankroll:.0f}

Do not reveal a final answer. Return only the message.
"""

