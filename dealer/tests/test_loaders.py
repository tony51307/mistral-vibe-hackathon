import json
from pathlib import Path
import tempfile
import unittest

import yaml

from game.loaders import DataValidationError, load_agendas, load_problem_bank


ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "data" / "pay_to_think_problem_bank_v1.json"
AGENDA_PATH = ROOT / "data" / "pay_to_think_agendas_v1.yaml"


class LoaderTests(unittest.TestCase):
    def test_canonical_bank_and_all_agendas_validate(self):
        bank = load_problem_bank(BANK_PATH)
        catalog = load_agendas(AGENDA_PATH, bank)
        self.assertEqual(len(bank.problems), 50)
        self.assertEqual(set(catalog.agendas), {1, 2, 3, 4, 5})
        self.assertTrue(all(len(agenda.rounds) == 25 for agenda in catalog.agendas.values()))

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


if __name__ == "__main__":
    unittest.main()
