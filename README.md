# SliceOps Toolkit

> CI guardrail templates, validators, and tooling for SliceOps™ adopters.

**Status: scaffolding in progress (private).** Companion to [sliceops-spec](https://github.com/SliceOps/spec). Intended license: MIT (pending IP/Legal ratification — no `LICENSE` file yet by design).

## What's here

| Path | Purpose |
|---|---|
| `templates/ci-guardrails/` | **Capa B.2 CI/Pipeline Cost Economy** reference templates (5 levers) — bootstrap defaults materializing P12 Shared-Resource Pre-flight |
| `templates/llm-ci-economy/` | **Capa B.2 sub-domain LLM-Inference-Cost-Economy** — workflow demonstrating prompt-caching + model-tier + diff-only context + trigger-set minimalism LLM-aware + green-not-skipped draft gate |
| `templates/cost-ledger/` | **Capa B.1** cost-ledger template with three dimensions: token (billed-equivalent) + infra/CI + LLM-API-in-CI (P12) |
| `templates/consistency-validators/` | **Capa B.1 Layer 3** consistency validators — workflow + deterministic `validators.py` (cross-references-bidirectional, no-orphan-decs, frontmatter-schema, topic-tags, counter-atomicity) |
| `calibration/` | **Capa B.1 Calibration discipline** — deterministic `calibrate.py` (stdlib) parses session `.jsonl` → percentiles → bands; `band-calibration-register.md` is the append-only audit trail (v1 baseline 2026-06-15) |

## Roadmap (pending)

- Layer 3 Phase 3 validators (glossary-coverage, supersession-chain acyclicity, vocabulary-changes↔glossary sync)
- `validate-folder-structure` (lightweight-pivot structure)
- `validate-shared-resource-preflight`
- slice-forecaster + DAG builder

## Design posture

The **patterns** are vendor-agnostic / stack-agnostic (Capa B.2). Concrete instances (GitHub Actions YAML, specific package managers) are Capa C.2 — each header documents the equivalent for other CI providers so adopters instantiate their own. Guardrails are **bootstrap defaults, never post-incident retrofit** (P12).

## License

Licensed under the [MIT License](LICENSE). Copyright (c) 2026 Andrés Ramírez Sierra.

Code files carry an `SPDX-License-Identifier: MIT` header so per-file scope stays unambiguous when files are reused individually.

SliceOps™ is a trademark of Andrés Ramírez Sierra (EUIPO filing #019381071, pending registration); trademark usage is governed separately by `TRADEMARK.md` in [sliceops-spec](https://github.com/SliceOps/spec) (pending). The MIT license does not transfer trademark rights.

---

SliceOps™ is an open methodology authored by Andrés Ramírez Sierra. Trademark and copyright held personally.
