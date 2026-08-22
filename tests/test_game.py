from __future__ import annotations

import unittest
from collections import Counter

from economy import affordable_tiers, clamp_tier_to_bankroll
from game import GameEngine
from metrics import agent_scoreboard, economy_metrics
from problems import is_correct, seeded_problem_sequence


class GameTests(unittest.TestCase):
    def test_seeded_sequence_has_25_unique_problems(self) -> None:
        problems = seeded_problem_sequence(seed=7, rounds=25)
        self.assertEqual(len(problems), 25)
        self.assertEqual(len({problem.id for problem in problems}), 25)

    def test_answer_validation_accepts_equivalent_fractions(self) -> None:
        problem = next(problem for problem in seeded_problem_sequence(7, 25) if problem.id == "probability_001")
        self.assertTrue(is_correct(problem, "20/132"))
        self.assertTrue(is_correct(problem, "5/33"))
        self.assertFalse(is_correct(problem, "1/6"))

    def test_tier_affordability(self) -> None:
        self.assertEqual(affordable_tiers(6), ["none", "low", "medium", "high"])
        self.assertEqual(clamp_tier_to_bankroll("xhigh", 6), "high")
        self.assertEqual(clamp_tier_to_bankroll("medium", 2), "low")

    def test_table_talk_differs_by_agent(self) -> None:
        engine = GameEngine(seed=7)
        season = engine.new_season()
        result = engine.play_next_round(season)
        assert result is not None
        messages = list(result.public_messages.values())
        self.assertEqual(len(messages), 4)
        self.assertEqual(len(set(messages)), 4)

    def test_full_season_metrics_are_demo_ready(self) -> None:
        engine = GameEngine(seed=7, use_mistral=False)
        season = engine.new_season()
        while season.round_number < season.config.season_rounds:
            engine.play_next_round(season)

        economy = economy_metrics(season)
        scoreboard = {row["policy"]: row for row in agent_scoreboard(season)}
        tiers = Counter(
            turn.reasoning_tier
            for result in season.history
            for turn in result.turns.values()
        )

        self.assertGreaterEqual(economy["average_reasoning_spend"], 2.5)
        self.assertLessEqual(economy["average_reasoning_spend"], 3.2)
        self.assertGreaterEqual(tiers["high"], 5)
        self.assertLessEqual(tiers["high"], 25)
        self.assertGreaterEqual(tiers["xhigh"], 2)
        self.assertLessEqual(tiers["xhigh"], 8)
        self.assertGreaterEqual(scoreboard["dynamic"]["bankroll"], 30)
        self.assertGreaterEqual(scoreboard["dynamic"]["accuracy"], 0.60)


if __name__ == "__main__":
    unittest.main()

