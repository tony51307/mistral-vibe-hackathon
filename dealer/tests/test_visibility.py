from pathlib import Path
import unittest

from game.dealer_distributor import DealerGame
from game.loaders import load_agendas, load_problem_bank
from game.models import GameConfig


ROOT = Path(__file__).resolve().parents[1]


def all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


class VisibilityTests(unittest.TestCase):
    def setUp(self):
        bank = load_problem_bank(ROOT / "data" / "pay_to_think_problem_bank_v1.json")
        agendas = load_agendas(ROOT / "data" / "pay_to_think_agendas_v1.yaml", bank)
        self.game = DealerGame(
            player_ids=["agent"],
            problem_bank=bank,
            agenda_catalog=agendas,
            strategy_number=6,
            seed=260822,
            config=GameConfig(season_rounds=1),
        )

    def test_category_payload_reveals_no_problem_identity_or_hidden_metadata(self):
        payload = self.game.reveal_category()["agent"]
        self.assertNotIn("problem_id", payload)
        self.assertEqual(payload["category"], "general_quantitative_reasoning")
        self.assertFalse({"answer", "dealer_meta", "difficulty", "guessability"} & set(all_keys(payload)))

    def test_problem_payload_uses_public_whitelist(self):
        self.game.reveal_category()
        self.game.collect_entries()
        self.game.record_table_talk({"agent": "I may spend."})
        payload = self.game.reveal_problem()["agent"]
        forbidden = {
            "answer",
            "validator",
            "dealer_meta",
            "difficulty",
            "guessability",
            "suggested_reasoning_tier",
            "reference_reasoning_tier",
            "round_role",
            "future_rounds",
        }
        self.assertFalse(forbidden & set(all_keys(payload)))
        self.assertEqual(
            {"problem_id", "category", "prompt_markdown"} & set(payload),
            {"problem_id", "category", "prompt_markdown"},
        )

    def test_mutating_returned_payload_cannot_inject_data_into_router(self):
        self.game.reveal_category()
        self.game.collect_entries()
        self.game.record_table_talk({})
        payload = self.game.reveal_problem()
        payload["agent"]["answer"] = "injected"
        seen = {}

        def router(request):
            seen.update(request)
            return {"reasoning_tier": "none"}

        self.game.route_and_purchase({"agent": router})
        self.assertNotIn("answer", seen)

    def test_table_talk_preserves_original_and_sanitizes_display(self):
        self.game.reveal_category()
        self.game.collect_entries()
        displayed = self.game.record_table_talk({"agent": "<script>"})
        self.assertEqual(displayed["agent"], "&lt;script&gt;")
        self.assertEqual(self.game._round_players["agent"].public_message, "<script>")

    def test_table_talk_character_limit_is_enforced(self):
        self.game.reveal_category()
        self.game.collect_entries()
        with self.assertRaisesRegex(ValueError, "exceeds 100"):
            self.game.record_table_talk({"agent": "x" * 101})


if __name__ == "__main__":
    unittest.main()
