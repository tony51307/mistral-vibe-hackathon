from pathlib import Path
import tempfile
import unittest

import yaml

from game.dealer_distributor import DealerGame, SeasonComplete
from game.loaders import DataValidationError, load_agendas, load_problem_bank, load_table_modes
from game.models import GameConfig


ROOT = Path(__file__).resolve().parents[1]
BANK = load_problem_bank(ROOT / "data" / "pay_to_think_problem_bank_v1.json")
AGENDAS = load_agendas(ROOT / "data" / "pay_to_think_agendas_v1.yaml", BANK)
TABLE_PATH = ROOT / "tables" / "table_modes_v1.yaml"


class TableConfigurationTests(unittest.TestCase):
    def test_v1_contribution_scales_from_two_through_ten_agents(self):
        for count in range(2, 11):
            with self.subTest(count=count):
                config = GameConfig.for_table_size(count)
                self.assertEqual(config.dealer_contribution_cents, 300 * count)
                self.assertEqual(
                    count * config.entry_fee_cents + config.dealer_contribution_cents,
                    1_300 * count,
                )

    def test_out_of_range_table_sizes_are_rejected(self):
        for count in (1, 11):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "between 2 and 10"):
                    GameConfig.for_table_size(count)

    def test_canonical_modes_load_and_reference_existing_agendas(self):
        tables = load_table_modes(TABLE_PATH, AGENDAS)
        self.assertEqual(tables.default_mode, "baseline")
        self.assertEqual(
            {mode_id: mode.initial_agent_count for mode_id, mode in tables.modes.items()},
            {
                "heads_up": 2,
                "baseline": 4,
                "demo": 6,
                "tournament": 8,
                "social_lab": 7,
                "social_stress": 9,
                "ecology": 10,
            },
        )

    def test_changed_economy_contract_is_rejected(self):
        document = yaml.safe_load(TABLE_PATH.read_text(encoding="utf-8"))
        document["economy"]["entry_fee_cents"] = 999
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tables.yaml"
            path.write_text(yaml.safe_dump(document), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "frozen V1"):
                load_table_modes(path, AGENDAS)

    def test_mode_builds_default_ids_fixed_h_and_recommended_agenda(self):
        tables = load_table_modes(TABLE_PATH, AGENDAS)
        game = DealerGame.from_table_mode(
            table_catalog=tables,
            mode_id="demo",
            problem_bank=BANK,
            agenda_catalog=AGENDAS,
            seed=260822,
        )
        self.assertEqual(tuple(game.players), tuple(f"agent_{n}" for n in range(1, 7)))
        self.assertEqual(game.initial_agent_count, 6)
        self.assertEqual(game.config.dealer_contribution_cents, 1_800)
        self.assertEqual(game.agenda.strategy_number, 3)
        self.assertEqual(game.table_mode_id, "demo")

    def test_custom_ids_must_match_mode_size(self):
        tables = load_table_modes(TABLE_PATH, AGENDAS)
        with self.assertRaisesRegex(ValueError, "requires 4 player IDs"):
            DealerGame.from_table_mode(
                table_catalog=tables,
                mode_id="baseline",
                player_ids=["only", "three", "agents"],
                problem_bank=BANK,
                agenda_catalog=AGENDAS,
                seed=260822,
            )

    def test_sole_survivor_ends_season_and_event_records_table(self):
        tables = load_table_modes(TABLE_PATH, AGENDAS)
        game = DealerGame.from_table_mode(
            table_catalog=tables,
            mode_id="heads_up",
            player_ids=["a", "b"],
            problem_bank=BANK,
            agenda_catalog=AGENDAS,
            seed=260822,
        )
        game.players["b"].bankroll_cents = 600
        game.reveal_category()
        game.collect_entries()
        game.record_table_talk({})
        game.reveal_problem()
        game.route_and_purchase(
            {
                "a": lambda payload: {"reasoning_tier": "none"},
                "b": lambda payload: {"reasoning_tier": "none"},
            }
        )
        correct = BANK.problems["quant_001"]["answer"]["display"]
        game.solve(
            {
                "a": lambda payload: {"answer": correct},
                "b": lambda payload: {"answer": "wrong"},
            }
        )
        game.judge()
        game.payout()
        event = game.complete_round()

        self.assertEqual(event["dealer_contribution_cents"], 600)
        self.assertEqual(event["initial_agent_count"], 2)
        self.assertEqual(event["table_mode_id"], "heads_up")
        self.assertEqual(event["season_result"]["status"], "SOLE_SURVIVOR")
        self.assertEqual(event["season_result"]["winner_ids"], ["a"])
        with self.assertRaises(SeasonComplete) as raised:
            game.reveal_category()
        self.assertEqual(raised.exception.result["status"], "SOLE_SURVIVOR")

    def test_h_stays_fixed_after_an_agent_is_eliminated(self):
        tables = load_table_modes(TABLE_PATH, AGENDAS)
        game = DealerGame.from_table_mode(
            table_catalog=tables,
            mode_id="baseline",
            player_ids=["a", "b", "c", "d"],
            problem_bank=BANK,
            agenda_catalog=AGENDAS,
            strategy_number=1,
            seed=260822,
        )
        game.players["b"].bankroll_cents = 600
        game.reveal_category()
        game.collect_entries()
        game.record_table_talk({})
        game.reveal_problem()
        game.route_and_purchase(
            {agent_id: (lambda payload: {"reasoning_tier": "none"}) for agent_id in game.players}
        )
        correct = BANK.problems["quant_001"]["answer"]["display"]
        game.solve(
            {
                "a": lambda payload: {"answer": correct},
                "b": lambda payload: {"answer": "wrong"},
                "c": lambda payload: {"answer": "wrong"},
                "d": lambda payload: {"answer": "wrong"},
            }
        )
        game.judge()
        game.payout()
        game.complete_round()

        self.assertEqual(game.players["b"].bankroll_cents, 0)
        self.assertIsNone(game.season_result)
        category_payloads = game.reveal_category()
        self.assertEqual(set(category_payloads), {"a", "c", "d"})
        game.collect_entries()
        game.record_table_talk({})
        problem_payloads = game.reveal_problem()
        self.assertEqual(problem_payloads["a"]["pot_cents"], 4_200)
        self.assertEqual(game.config.dealer_contribution_cents, 1_200)

    def test_all_eliminated_in_unresolved_show_hand_is_house_win(self):
        tables = load_table_modes(TABLE_PATH, AGENDAS)
        game = DealerGame.from_table_mode(
            table_catalog=tables,
            mode_id="heads_up",
            player_ids=["a", "b"],
            problem_bank=BANK,
            agenda_catalog=AGENDAS,
            seed=260822,
        )
        game.players["a"].bankroll_cents = 600
        game.players["b"].bankroll_cents = 600
        game.reveal_category()
        game.collect_entries()
        game.record_table_talk({})
        game.reveal_problem()
        game.route_and_purchase(
            {
                "a": lambda payload: {"reasoning_tier": "none"},
                "b": lambda payload: {"reasoning_tier": "none"},
            }
        )
        game.solve(
            {
                "a": lambda payload: {"answer": "wrong"},
                "b": lambda payload: {"answer": "wrong"},
            }
        )
        game.judge()
        game.payout()
        event = game.complete_round()
        self.assertEqual(event["season_result"]["status"], "HOUSE_WIN")
        self.assertEqual(event["season_result"]["winner_ids"], [])
        self.assertEqual(event["rollover_out_cents"], 1_800)


if __name__ == "__main__":
    unittest.main()
