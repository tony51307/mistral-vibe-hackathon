# Value-of-Computation Router Comparison

Model: `mistral-medium-3.5`

The policies use one model with different reasoning budgets. Low, High, and
`auto_adaptive` were run in the shared comparison matrix. The final
`auto_value` result was rerun after making its structured-output boundary
tolerant; its raw report contains no routing fallbacks.

## Semantically rescored result

| Policy | Correct | Avg tokens | Avg cost | Avg seconds |
| --- | ---: | ---: | ---: | ---: |
| Low | 8/10 | 7,701 | $0.00995 | 5.97 |
| High | 10/10 | 7,846 | $0.01074 | 7.39 |
| Adaptive perturbation | 8/10 | 7,702 | $0.00893 | 5.18 |
| Candidate/critic value | 10/10 | 8,351 | $0.01155 | 8.59 |

The semantic rescore accepts equivalent formatting explicitly allowed by the
task: explanatory text containing `5/33`, `0.05` with or without a dollar sign,
and a Python list wrapped in Markdown code ticks. The raw first comparison used
strict whole-response matching and therefore understated Low, High, and
adaptive quality.

## Findings

- Low and adaptive both missed the linear equation and combinations tasks.
- High solved all ten tasks.
- The final value router also solved all ten. It routed the linear equation to
  Medium and combinations to High after candidate/critic evaluation.
- Compared with High, value routing used 6.4% more tokens, cost 7.5% more, and
  took 16.2% longer in these single trials.
- Compared with adaptive, value routing recovered two tasks but paid 29.3% more
  cost and 65.8% more latency.

## Interpretation

The candidate/critic architecture demonstrates the intended quality mechanism:
cheap work is retained as evidence and concrete critique can recover failures
that prompt-level routing misses. It does not yet demonstrate compute savings.
Every candidate is currently criticized because no trustworthy external
verifier is available. The next economic optimization is to skip the critic
only when a deterministic verifier has actually accepted the candidate—not
when the model merely claims that verification is cheap.

These are development results from one trial per task. They are evidence for
the implementation path, not a statistically conclusive benchmark.
