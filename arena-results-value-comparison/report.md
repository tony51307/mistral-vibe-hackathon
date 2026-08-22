# Vibe Reasoning Arena

Model: `mistral-medium-3.5`
Created: 2026-08-22T22:32:26.815077+00:00

| Task | Trial | Policy | Routed | Quality | Tokens | Cost | Seconds |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| Simple addition | 1 | low | — | ✓ | 7681 | $0.01154 | 4.77 |
| Simple addition | 1 | high | — | ✓ | 7736 | $0.00676 | 4.82 |
| Simple addition | 1 | auto_adaptive | low | ✓ | 7683 | $0.00878 | 5.68 |
| Simple addition | 1 | auto_value | low | ✓ | 7965 | $0.01227 | 6.66 |
| Text transformation | 1 | low | — | ✓ | 7683 | $0.00862 | 4.68 |
| Text transformation | 1 | high | — | ✓ | 7741 | $0.00869 | 4.98 |
| Text transformation | 1 | auto_adaptive | low | ✓ | 7685 | $0.00879 | 5.04 |
| Text transformation | 1 | auto_value | low | ✓ | 8004 | $0.00969 | 6.98 |
| Simple factual transformation | 1 | low | — | ✓ | 7678 | $0.01153 | 5.02 |
| Simple factual transformation | 1 | high | — | ✓ | 7719 | $0.00907 | 9.10 |
| Simple factual transformation | 1 | auto_adaptive | low | ✓ | 7676 | $0.00634 | 4.68 |
| Simple factual transformation | 1 | auto_value | low | ✓ | 7961 | $0.01228 | 6.27 |
| Linear equation | 1 | low | — | ✗ | 7693 | $0.00879 | 5.23 |
| Linear equation | 1 | high | — | ✓ | 7798 | $0.01233 | 5.99 |
| Linear equation | 1 | auto_adaptive | low | ✗ | 7696 | $0.00638 | 4.35 |
| Linear equation | 1 | auto_value | low | ✓ | 8001 | $0.00944 | 5.80 |
| Without-replacement probability | 1 | low | — | ✗ | 7763 | $0.00684 | 7.31 |
| Without-replacement probability | 1 | high | — | ✓ | 7881 | $0.01291 | 6.28 |
| Without-replacement probability | 1 | auto_adaptive | low | ✗ | 7771 | $0.01208 | 6.52 |
| Without-replacement probability | 1 | auto_value | low | ✗ | 8059 | $0.01258 | 9.03 |
| Bat and ball cognitive reflection | 1 | low | — | ✗ | 7701 | $0.00864 | 11.48 |
| Bat and ball cognitive reflection | 1 | high | — | ✗ | 8060 | $0.01150 | 12.99 |
| Bat and ball cognitive reflection | 1 | auto_adaptive | low | ✗ | 7706 | $0.00885 | 5.19 |
| Bat and ball cognitive reflection | 1 | auto_value | low | ✗ | 8052 | $0.00962 | 8.13 |
| Monty Hall decision | 1 | low | — | ✓ | 7705 | $0.01158 | 5.85 |
| Monty Hall decision | 1 | high | — | ✓ | 7872 | $0.01006 | 11.27 |
| Monty Hall decision | 1 | auto_adaptive | low | ✓ | 7705 | $0.00882 | 4.79 |
| Monty Hall decision | 1 | auto_value | low | ✓ | 8049 | $0.01251 | 5.89 |
| Pair combinations | 1 | low | — | ✗ | 7691 | $0.01156 | 5.17 |
| Pair combinations | 1 | high | — | ✓ | 7811 | $0.01247 | 6.27 |
| Pair combinations | 1 | auto_adaptive | low | ✗ | 7690 | $0.01156 | 5.06 |
| Pair combinations | 1 | auto_value | low | ✓ | 7999 | $0.01238 | 5.97 |
| Syllogism validity | 1 | low | — | ✓ | 7702 | $0.00880 | 5.03 |
| Syllogism validity | 1 | high | — | ✓ | 8005 | $0.01383 | 6.99 |
| Syllogism validity | 1 | auto_adaptive | low | ✓ | 7702 | $0.00880 | 5.40 |
| Syllogism validity | 1 | auto_value | low | ✓ | 8056 | $0.01256 | 5.79 |
| Python aliasing behavior | 1 | low | — | ✓ | 7713 | $0.01163 | 5.14 |
| Python aliasing behavior | 1 | high | — | ✓ | 7833 | $0.00979 | 5.21 |
| Python aliasing behavior | 1 | auto_adaptive | low | ✗ | 7711 | $0.00887 | 5.07 |
| Python aliasing behavior | 1 | auto_value | low | ✓ | 8089 | $0.00978 | 5.87 |

## Policy totals

| Policy | Runs | Quality | Avg tokens | Avg cost | Avg seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| low | 10 | 60.0% | 7701 | $0.00995 | 5.97 |
| high | 10 | 90.0% | 7846 | $0.01074 | 7.39 |
| auto_adaptive | 10 | 50.0% | 7702 | $0.00893 | 5.18 |
| auto_value | 10 | 80.0% | 8024 | $0.01131 | 6.64 |

auto_adaptive vs High: **16.9% cost reduction**, **29.9% latency reduction**.

auto_value vs High: **5.3% cost increase**, **10.2% latency reduction**.

auto_adaptive routing agreement: **4/10 (40.0%)**

### auto_adaptive routing confusion

| Expected | Routed low | Routed high | Other/error |
| --- | ---: | ---: | ---: |
| low | 4 | 0 | 0 |
| high | 6 | 0 | 0 |

auto_value routing agreement: **4/10 (40.0%)**

### auto_value routing confusion

| Expected | Routed low | Routed high | Other/error |
| --- | ---: | ---: | ---: |
| low | 4 | 0 | 0 |
| high | 6 | 0 | 0 |

## Responses

### Simple addition — low (trial 1)

42

### Simple addition — high (trial 1)

42

### Simple addition — auto_adaptive (trial 1)

42

### Simple addition — auto_value (trial 1)

42

### Text transformation — low (trial 1)

HELLO WORLD

### Text transformation — high (trial 1)

HELLO WORLD

### Text transformation — auto_adaptive (trial 1)

HELLO WORLD

### Text transformation — auto_value (trial 1)

HELLO WORLD

### Simple factual transformation — low (trial 1)

Wednesday

### Simple factual transformation — high (trial 1)

Wednesday

### Simple factual transformation — auto_adaptive (trial 1)

Wednesday

### Simple factual transformation — auto_value (trial 1)

Wednesday

### Linear equation — low (trial 1)

17

### Linear equation — high (trial 1)

19

### Linear equation — auto_adaptive (trial 1)

17

### Linear equation — auto_value (trial 1)

19

### Without-replacement probability — low (trial 1)

The probability that both balls drawn are red is:

First draw: 5/12
Second draw (without replacement): 4/11

(5/12) * (4/11) = 20/132 = 5/33

5/33

### Without-replacement probability — high (trial 1)

5/33

### Without-replacement probability — auto_adaptive (trial 1)

The number of ways to draw 2 red balls from 5 is C(5,2) = 10. The total number of ways to draw any 2 balls from 12 is C(12,2) = 66. So the probability is 10/66 = 5/33.

### Without-replacement probability — auto_value (trial 1)

5/22

### Bat and ball cognitive reflection — low (trial 1)

0.05

### Bat and ball cognitive reflection — high (trial 1)

0.05

### Bat and ball cognitive reflection — auto_adaptive (trial 1)

The ball costs $0.05.

### Bat and ball cognitive reflection — auto_value (trial 1)

0.05

### Monty Hall decision — low (trial 1)

SWITCH

### Monty Hall decision — high (trial 1)

SWITCH

### Monty Hall decision — auto_adaptive (trial 1)

SWITCH

### Monty Hall decision — auto_value (trial 1)

SWITCH

### Pair combinations — low (trial 1)

132

### Pair combinations — high (trial 1)

66

### Pair combinations — auto_adaptive (trial 1)

132

### Pair combinations — auto_value (trial 1)

66

### Syllogism validity — low (trial 1)

NO

### Syllogism validity — high (trial 1)

NO

### Syllogism validity — auto_adaptive (trial 1)

NO

### Syllogism validity — auto_value (trial 1)

NO

### Python aliasing behavior — low (trial 1)

[1, 2, 3]

### Python aliasing behavior — high (trial 1)

[1, 2, 3]

### Python aliasing behavior — auto_adaptive (trial 1)

`[1, 2, 3]`

### Python aliasing behavior — auto_value (trial 1)

[1, 2, 3]
