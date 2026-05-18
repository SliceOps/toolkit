# Cost Ledger — template (Capa B.1)

> SliceOps cost-ledger with **two dimensions**: token cost **and** infra/CI cost.
> Token-only ledgers are blind to a finite, shared, exhaustible resource (CI
> minutes / API quota) until it hard-stops the pipeline. This template
> materializes P12 (Shared-Resource Pre-flight): the resource must be visible
> *before* it cuts. Copy per adopter; instance-specific units are Capa C.2.

## Per-Block summary

| Block | Slices | Token cost (M) | Infra/CI cost | Notes |
|---|---|---|---|---|
| BL-NN | N | ~X.X M | ~Y CI-min / $Z | forecast vs actual |

## Token dimension

| Slice | Band (XS/S/M/L/XL) | Forecast tok | Actual tok | Drift % |
|---|---|---|---|---|
| BL-NN.SL-NNN | M | 8M | — | — |

## Infra / CI dimension (P12)

| Period | CI minutes used | Budget | Headroom | Alert threshold hit? |
|---|---|---|---|---|
| YYYY-MM | — | — | — | no |

**Pre-Block checklist (P12 — mandatory before scaling parallelism past the
last Block-Retrospective baseline):**

- [ ] Enumerate finite/serialized shared resources this Block consumes
      (CI minutes, DEC/INS/HANDOFF counters, API rate limits,
      branch-protection serialization, DB migration locks, worktree state,
      connection pools)
- [ ] Each enumerated resource has: **cap** (hard limit), **alert**
      (warns BEFORE the limit, not at it), **telemetry** (continuous visibility)
- [ ] CI/infra budget headroom verified (not just token headroom)
- [ ] Bootstrap CI guardrails active (concurrency-cancel + change-gating +
      aggregation-gate + draft-skip + dependency-cache) — NOT retrofit
- [ ] Default for every shared resource = cap+alert, never silent hard-stop
      ("degradación avisada" > "corte seco invisible")

## Anti-patterns (P12)

- Spending limit `$0` / default quota → "exhaust resource" becomes "invisible
  hard-stop" instead of "warned degradation"
- Cost-ledger that tracks only tokens (infra-cost blindness)
- Scaling parallelism without enumerating the shared resources it consumes
- Guardrails patched post-incident instead of bootstrap defaults
