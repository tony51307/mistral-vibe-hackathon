# Loading Old + New Pay-to-Think Problem Banks

The mixed agendas reference two independent JSON banks:

```text
pay_to_think_problem_bank_v1.json
pay_to_think_reasoning_sensitive_additions_v2.json
```

Load both at dealer startup and merge by `id`.

```python
from game import load_agenda_catalogs, load_problem_banks

bank = load_problem_banks([
    "data/pay_to_think_problem_bank_v1.json",
    "data/pay_to_think_reasoning_sensitive_additions_v2.json",
])
agendas = load_agenda_catalogs([
    "data/pay_to_think_agendas_v1.yaml",
    "data/pay_to_think_mixed_old_new_agendas_v3.yaml",
], bank)
```

The production loader rejects duplicate JSON/YAML keys, duplicate IDs or
strategy numbers across files, unsupported schema versions, and agenda metadata
that disagrees with its authoritative source problem. It retains per-source and
combined SHA-256 values for reproducible audit events. Input ordering does not
change the combined hash.

For each YAML round, resolve only by `problem_id`.

`source_bank`, `dealer_difficulty`, `guessability`, `reasoning_profile`, and
`reference_reasoning_tier` are dealer/audit metadata and must never enter an agent prompt.

The new bank is intentionally not a replacement for V1. It adds problems with:

- multi-step short derivations;
- tempting shallow answers;
- parameterized textbook structures;
- low/medium/high reasoning-lift candidates;
- a small number of cheap captures.

Before making scientific claims, empirically estimate accuracy at each reasoning tier and
replace the hand-authored `reasoning_profile` metadata with measured model-specific lift.
