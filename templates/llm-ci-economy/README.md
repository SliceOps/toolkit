# LLM-CI-Economy — Layer B.2 sub-domain reference templates

Reference implementation of the **LLM-Inference-Cost-Economy** Layer B.2 sub-domain pattern (specialized within CI/Pipeline Cost Economy). Applies when a CI workflow calls a **paid LLM API** (audit, code-review, QA, codegen).

Spec: `sliceops-spec/reference/patterns/llm-inference-cost-economy.md`.

## Files

| File | Role |
|---|---|
| `llm-ci-economy.yml` | GitHub Actions workflow demonstrating the five levers and the LLM-aware draft gate (green-not-skipped). |

## The five levers (summary)

| Lever | Type | Purpose |
|---|---|---|
| **A** Prompt-caching discipline | NEW | Cache the stable >5K-token block; ~40–60% of cost is preventable. |
| **B** Model-tier discipline | NEW | Cheapest tier adequate; no top-tier "just in case". |
| **C** Diff-only context windowing | NEW | Send the diff, not full files. |
| **D** Trigger-set minimalism LLM-aware | REFINEMENT | No `synchronize` trigger; merge gate is `ready_for_review`. |
| **E** LLM-aware draft gate | REFINEMENT | Green-not-skipped (skipped required check = permanent PR block). |

## Pair with

- `../ci-guardrails/concurrency-cancel.yml` (always — dominant cost lever, parent pattern).
- `../ci-guardrails/aggregation-required-gate.yml` (when path-gating is used).
- `../cost-ledger/cost-ledger-template.md` (the **LLM-API-in-CI** is the third dimension).

## Adopter instantiation

Copy and set `vars.LLM_MODEL_MID_TIER` and `secrets.LLM_API_KEY`. Wire the actual API call honoring Levers A, B, and C (cache directive on the stable block; model tier matches task complexity; input context is the diff). The toolkit's Layer 3 consistency validators include an `R-LLM-CI-COST` check (in `../consistency-validators/`) that fails a workflow YAML failing the four bright-line rules of this pattern.
