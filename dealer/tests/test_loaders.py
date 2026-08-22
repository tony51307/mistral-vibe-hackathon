import json
from pathlib import Path
import tempfile
import unittest

import yaml

from game.loaders import DataValidationError, load_agendas, load_problem_bank, load_table_modes
from game.models import ReasoningTier


ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "data" / "pay_to_think_problem_bank_v1.json"
AGENDA_PATH = ROOT / "data" / "pay_to_think_agendas_v1.yaml"
TABLE_PATH = ROOT / "tables" / "table_modes_v1.yaml"


class LoaderTests(unittest.TestCase):
    def test_canonical_bank_and_all_agendas_validate(self):
        bank = load_problem_bank(BANK_PATH)
        catalog = load_agendas(AGENDA_PATH, bank)
        self.assertEqual(len(bank.problems), 50)
        self.assertEqual(set(catalog.agendas), set(range(1, 11)))
        self.assertTrue(all(len(agenda.rounds) == 25 for agenda in catalog.agendas.values()))
        dynamic = catalog.agendas[9]
        self.assertTrue(dynamic.showcase_bias)
        self.assertEqual(dynamic.name, "reasoning_tier_ladder")
        self.assertTrue(dynamic.dynamic_advantage)
        self.assertEqual(
            dynamic.rounds[0].reference_reasoning_tier,
            ReasoningTier.NONE,
        )
        self.assertEqual(dynamic.rounds[0].round_role, "cheap_capture")
        tables = load_table_modes(TABLE_PATH, catalog)
        self.assertEqual(tables.get().initial_agent_count, 4)

    def test_agenda_metadata_cannot_override_canonical_bank(self):
        bank = load_problem_bank(BANK_PATH)
        document = yaml.safe_load(AGENDA_PATH.read_text(encoding="utf-8"))
        document["agendas"][0]["rounds"][0]["dealer_difficulty"] = "wrong"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / AGENDA_PATH.name
            path.write_text(yaml.safe_dump(document), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "difficulty mismatch"):
                load_agendas(path, bank)

    def test_duplicate_problem_ids_are_rejected(self):
        document = json.loads(BANK_PATH.read_text(encoding="utf-8"))
        document["problems"].append(document["problems"][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / BANK_PATH.name
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "duplicate problem id"):
                load_problem_bank(path)

    def test_dynamic_edge_analysis_metadata_is_validated(self):
        bank = load_problem_bank(BANK_PATH)
        document = yaml.safe_load(AGENDA_PATH.read_text(encoding="utf-8"))
        dynamic = next(
            agenda for agenda in document["agendas"] if agenda["strategy_number"] == 6
        )
        dynamic["rounds"][0]["reference_reasoning_tier"] = "impossible"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / AGENDA_PATH.name
            path.write_text(yaml.safe_dump(document), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "reference_reasoning_tier"):
                load_agendas(path, bank)


if __name__ == "__main__":
    unittest.main()
