# Vibe Reasoning Arena

Model: `mistral-medium-3.5`
Created: 2026-08-22T22:37:45.004006+00:00

| Task | Trial | Policy | Routed | Quality | Tokens | Cost | Seconds |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| Simple addition | 1 | auto_value | low | ✓ | 8154 | $0.00989 | 6.29 |
| Text transformation | 1 | auto_value | low | ✓ | 8219 | $0.00961 | 6.44 |
| Simple factual transformation | 1 | auto_value | low | ✓ | 8177 | $0.01277 | 7.57 |
| Linear equation | 1 | auto_value | medium | ✓ | 8559 | $0.00937 | 8.17 |
| Without-replacement probability | 1 | auto_value | high | ✓ | 8546 | $0.01470 | 16.05 |
| Bat and ball cognitive reflection | 1 | auto_value | low | ✓ | 8301 | $0.01309 | 7.24 |
| Monty Hall decision | 1 | auto_value | low | ✓ | 8312 | $0.01309 | 7.25 |
| Pair combinations | 1 | auto_value | high | ✓ | 8530 | $0.01200 | 8.21 |
| Syllogism validity | 1 | auto_value | low | ✓ | 8376 | $0.01054 | 7.37 |
| Python aliasing behavior | 1 | auto_value | low | ✓ | 8339 | $0.01045 | 11.35 |

## Policy totals

| Policy | Runs | Quality | Avg tokens | Avg cost | Avg seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| auto_value | 10 | 100.0% | 8351 | $0.01155 | 8.59 |

auto_value routing agreement: **5/10 (50.0%)**

### auto_value routing confusion

| Expected | Routed low | Routed high | Other/error |
| --- | ---: | ---: | ---: |
| low | 3 | 0 | 1 |
| high | 4 | 2 | 0 |

## Responses

### Simple addition — auto_value (trial 1)

42

### Text transformation — auto_value (trial 1)

HELLO WORLD

### Simple factual transformation — auto_value (trial 1)

Wednesday

### Linear equation — auto_value (trial 1)

19

### Without-replacement probability — auto_value (trial 1)

5/33

### Bat and ball cognitive reflection — auto_value (trial 1)

0.05

### Monty Hall decision — auto_value (trial 1)

SWITCH

### Pair combinations — auto_value (trial 1)

66

### Syllogism validity — auto_value (trial 1)

NO

### Python aliasing behavior — auto_value (trial 1)

[1, 2, 3]
