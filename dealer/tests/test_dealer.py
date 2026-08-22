from pathlib import Path
import tempfile
import unittest

from game.dealer_distributor import DealerGame, InvalidPhase
from game.loaders import load_agendas, load_problem_bank
from game.models import GameConfig, Phase


ROOT = Path(__file__).resolve().parents[1]
BANK = load_problem_bank(ROOT / "data" / "pay_to_think_problem_bank_v1.json")
AGENDAS = load_agendas(ROOT / "data" / "pay_to_think_agendas_v1.yaml", BANK)


def fixed_router(tier):
    return lambda payload: {"reasoning_tier": tier}


def fixed_solver(answer):
    return lambda payload: {"answer": answer, "actual_output_tokens": 1}


def one_round_game(player_ids=("a", "b"), **kwargs):
    config = kwargs.pop("config", GameConfig(season_rounds=1))
    return DealerGame(
        player_ids=player_ids,
        problem_bank=BANK,
        agenda_catalog=AGENDAS,
        strategy_number=1,
        seed=260822,
        config=config,
        **kwargs,
    )


def play_to_reveal(game, messages=None):
    game.reveal_category()
    game.collect_entries()
    game.record_table_talk(messages or {})
    return game.reveal_problem()


def finish(game, payloads, answers, tiers=None):
    tiers = tiers or {agent_id: "none" for agent_id in payloads}
    game.route_and_purchase({agent_id: fixed_router(tiers[agent_id]) for agent_id in payloads})
    game.solve({agent_id: fixed_solver(answers[agent_id]) for agent_id in payloads})
    game.judge()
    game.payout()
    return game.complete_round()


class DealerTests(unittest.TestCase):
    def test_phase_order_is_enforced(self):
        game = one_round_game()
        with self.assertRaises(InvalidPhase):
            game.collect_entries()
        game.reveal_category()
        self.assertEqual(game.phase, Phase.ENTRY)

    def test_entry_h_reasoning_burn_and_winner_payout(self):
        game = one_round_game()
        payloads = play_to_reveal(game)
        correct = BANK.problems["quant_001"]["answer"]["display"]
        event = finish(game, payloads, {"a": correct, "b": "wrong"})
        self.assertEqual(event["entry_total_cents"], 2_000)
        self.assertEqual(event["dealer_contribution_cents"], 1_200)
        self.assertEqual(event["pot_cents"], 3_200)
        self.assertEqual(game.players["a"].bankroll_cents, 10_100)
        self.assertEqual(game.players["b"].bankroll_cents, 6_900)
        self.assertEqual(event["rollover_out_cents"], 0)

    def test_no_winner_rolls_the_full_pot(self):
        config = GameConfig(season_rounds=2)
        game = one_round_game(config=config)
        first = play_to_reveal(game)
        first_event = finish(game, first, {"a": "wrong", "b": "wrong"})
        self.assertEqual(first_event["rollover_out_cents"], 3_200)
        second_categories = game.reveal_category()
        self.assertEqual(second_categories["a"]["current_rollover_cents"], 3_200)
        game.collect_entries()
        game.record_table_talk({})
        second = game.reveal_problem()
        self.assertEqual(second["a"]["pot_cents"], 6_400)

    def test_split_remainder_carries_to_rollover(self):
        config = GameConfig(season_rounds=1, dealer_contribution_cents=1_201)
        game = one_round_game(player_ids=("a", "b", "c"), config=config)
        payloads = play_to_reveal(game)
        correct = BANK.problems["quant_001"]["answer"]["display"]
        event = finish(game, payloads, {"a": correct, "b": correct, "c": "wrong"})
        self.assertEqual(event["pot_cents"], 4_201)
        self.assertEqual(event["rollover_out_cents"], 1)
        self.assertEqual(event["agents"][0]["prize_received_cents"], 2_100)
        self.assertEqual(event["agents"][1]["prize_received_cents"], 2_100)

    def test_show_hand_stakes_everything_and_buys_no_reasoning(self):
        game = one_round_game(player_ids=("a",))
        game.players["a"].bankroll_cents = 600
        payloads = play_to_reveal(game)
        correct = BANK.problems["quant_001"]["answer"]["display"]
        event = finish(game, payloads, {"a": correct})
        record = event["agents"][0]
        self.assertTrue(record["show_hand"])
        self.assertEqual(record["entry_paid_cents"], 600)
        self.assertEqual(record["reasoning_price_cents"], 0)
        self.assertEqual(record["router_attempts"], 0)
        self.assertEqual(game.players["a"].bankroll_cents, 1_800)

    def test_router_retries_then_falls_back_deterministically(self):
        config = GameConfig(starting_bankroll_cents=1_500, season_rounds=1)
        game = one_round_game(player_ids=("a",), config=config)
        play_to_reveal(game)
        calls = []

        def overspending_router(payload):
            calls.append(payload["router_retry"])
            return {"reasoning_tier": "xhigh"}

        game.route_and_purchase({"a": overspending_router})
        record = game._round_players["a"]
        self.assertEqual(calls, [False, True])
        self.assertEqual(record.router_tier, "high")
        self.assertEqual(record.reasoning_price_cents, 500)
        self.assertTrue(record.router_fallback)
        self.assertEqual(game.players["a"].bankroll_cents, 0)

    def test_exact_entry_boundary_never_makes_bankroll_negative(self):
        config = GameConfig(starting_bankroll_cents=1_000, season_rounds=1)
        game = one_round_game(player_ids=("a",), config=config)
        play_to_reveal(game)
        game.route_and_purchase({"a": fixed_router("none")})
        record = game._round_players["a"]
        self.assertEqual(record.router_tier, "none")
        self.assertEqual(record.reasoning_price_cents, 0)
        self.assertTrue(record.router_fallback)
        self.assertEqual(game.players["a"].bankroll_cents, 0)

    def test_jsonl_event_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run.jsonl"
            game = one_round_game(output_path=output)
            payloads = play_to_reveal(game)
            correct = BANK.problems["quant_001"]["answer"]["display"]
            finish(game, payloads, {"a": correct, "b": "wrong"})
            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn('"problem_bank_sha256"', lines[0])

    def test_complete_25_round_agenda_rotates_in_registered_order(self):
        game = DealerGame(
            player_ids=["a"],
            problem_bank=BANK,
            agenda_catalog=AGENDAS,
            strategy_number=5,
            seed=260822,
            config=GameConfig(),
        )
        observed = []
        for agenda_round in AGENDAS.agendas[5].rounds:
            category = game.reveal_category()["a"]
            self.assertEqual(category["category"], agenda_round.category)
            game.collect_entries()
            game.record_table_talk({})
            payloads = game.reveal_problem()
            observed.append(payloads["a"]["problem_id"])
            answer = BANK.problems[agenda_round.problem_id]["answer"]["display"]
            finish(game, payloads, {"a": answer})
        self.assertEqual(observed, [item.problem_id for item in AGENDAS.agendas[5].rounds])


if __name__ == "__main__":
    unittest.main()
