# Cost Ledger — template (Capa B.1)

> SliceOps cost-ledger with **three dimensions**: token cost **+** infra/CI cost **+** LLM-API-in-CI cost.
> A token-only ledger is blind to finite shared resources (CI minutes / API
> quota / LLM-API spend) until they hard-stop the pipeline. This template
> materializes P12 (Shared-Resource Pre-flight): the resource must be visible
> *before* it cuts. The LLM-API dimension was added when LLM-Inference-Cost-
> Economy (B.2 sub-domain) formalized the LLM-API budget as a third resource
> class with distinct dynamics (`PR velocity × push-frequency × prompt-size`).
> Copy per adopter; instance-specific units are Capa C.2.

## Per-Block summary

| Block | Slices | Token cost (M) | Infra/CI cost | LLM-API-in-CI cost | Notes |
|---|---|---|---|---|---|
| BL-NN | N | ~X.X M | ~Y CI-min / $Z | ~$W / N runs | forecast vs actual |

## Token dimension (development tokens — slice/session throughput)

Token-band measured in **billed-equivalent** (input + cache_creation × 1.25 + cache_read × 0.10 + output) — NOT total-with-cache (which inflates ~5×).

| Slice | Token-band (XS/S/M/L/XL) | Context-band (XS/S/M/L/XL) | Forecast tok | Actual tok | Drift % |
|---|---|---|---|---|---|
| BL-NN.SL-NNN | M | L | 8M | — | — |

## Infra / CI dimension (P12)

| Period | CI minutes used | Budget | Headroom | Alert threshold hit? |
|---|---|---|---|---|
| YYYY-MM | — | — | — | no |

## LLM-API-in-CI dimension (P12 + LLM-Inference-Cost-Economy)

LLM API spend in CI-time audit / code-review / QA / codegen workflows. Scales with `PR velocity × push-frequency × prompt-size` — dynamics distinct from token-throughput and infra-minutes. Per-row: declare model tier, input-context shape (diff vs full file), whether the stable block is cached.

| Workflow | Model tier | Cache on stable block? | Input context | Calls / mo | Cost / mo | Budget | Headroom | Alert? |
|---|---|---|---|---|---|---|---|---|
| llm-audit (PRs) | mid-tier | yes | diff-only | — | $— | $— | — | no |

**Pre-Block checklist (P12 — mandatory before scaling parallelism past the
last Block-Retrospective baseline):**

- [ ] Enumerate finite/serialized shared resources this Block consumes
      (CI minutes, DEC/INS/HANDOFF counters, API rate limits, **LLM-API spend**,
      branch-protection serialization, DB migration locks, worktree state,
      connection pools)
- [ ] Each enumerated resource has: **cap** (hard limit), **alert**
      (warns BEFORE the limit, not at it), **telemetry** (continuous visibility)
- [ ] CI/infra budget headroom verified (not just token headroom)
- [ ] **LLM-API-in-CI budget headroom verified** (third dimension; scales
      independently of tokens and CI minutes)
- [ ] Bootstrap CI guardrails active (concurrency-cancel + change-gating +
      aggregation-gate + draft-skip + dependency-cache) — NOT retrofit
- [ ] LLM-CI levers active when paid-LLM endpoint is called (prompt-caching +
      model-tier + diff-only context + trigger-set minimalism + LLM-aware
      draft gate green-not-skipped) — bootstrap default
- [ ] Default for every shared resource = cap+alert, never silent hard-stop
      ("warned degradation" > "invisible hard-cut")

## Anti-patterns (P12 + LLM-Inference-Cost-Economy)

- Spending limit `$0` / default quota → "exhaust resource" becomes "invisible
  hard-cut" instead of "warned degradation"
- Cost-ledger that tracks only tokens (infra-cost + LLM-API blindness)
- Cost-ledger that tracks tokens + infra but NOT LLM-API-in-CI (the most
  common blind spot — the bill is the only signal)
- Scaling parallelism without enumerating the shared resources it consumes
- Guardrails patched post-incident instead of bootstrap defaults
- Token-band measured as total-with-cache (inflates ~5×; the canonical unit
  is billed-equivalent — see `sliceops-spec/reference/sizing/`)
