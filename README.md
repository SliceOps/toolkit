# SliceOps Toolkit

> CI guardrail templates, validators, and tooling for SliceOps™ adopters.

**Status: scaffolding in progress (private).** Companion to [sliceops-spec](https://github.com/SliceOps/spec). Licensed under the [MIT License](LICENSE) (ratified 2026-06-15, `DR-2026-06-15-sliceops-license-ratification`).

## What's here

| Path | Purpose |
|---|---|
| `templates/ci-guardrails/` | **Layer B.2 CI/Pipeline Cost Economy** reference templates (5 levers) — bootstrap defaults materializing P12 Shared-Resource Pre-flight |
| `templates/llm-ci-economy/` | **Layer B.2 sub-domain LLM-Inference-Cost-Economy** — workflow demonstrating prompt-caching, model-tier, diff-only context, trigger-set minimalism LLM-aware, and green-not-skipped draft gate |
| `templates/cost-ledger/` | **Layer B.1** cost-ledger template with three dimensions: token (billed-equivalent), infra/CI, and LLM-API-in-CI (P12) |
| `templates/consistency-validators/` | **Layer B.1 Layer 3** consistency validators — workflow and deterministic `validators.py` (cross-references-bidirectional, no-orphan-decs, frontmatter-schema, topic-tags, counter-atomicity) |
| `calibration/` | **Layer B.1 Calibration discipline** — deterministic `calibrate.py` (stdlib) parses session `.jsonl`, then percentiles, then bands; `band-calibration-register.md` is the append-only audit trail (v1 baseline 2026-06-15) |

## Roadmap (pending)

- Layer 3 Phase 3 validators (glossary-coverage, supersession-chain acyclicity, vocabulary-changes↔glossary sync)
- `validate-folder-structure` (lightweight-pivot structure)
- `validate-shared-resource-preflight`
- slice-forecaster and DAG builder

## Design posture

The **patterns** are vendor-agnostic / stack-agnostic (Layer B.2). Concrete instances (GitHub Actions YAML, specific package managers) are Layer C.2 — each header documents the equivalent for other CI providers so adopters instantiate their own. Guardrails are **bootstrap defaults, never post-incident retrofit** (P12).

## License

Licensed under the [MIT License](LICENSE). Copyright (c) 2026 Andrés Ramírez Sierra.

Code files carry an `SPDX-License-Identifier: MIT` header so per-file scope stays unambiguous when files are reused individually.

SliceOps™ is a trademark of Andrés Ramírez Sierra (EUIPO filing #019381071, pending registration); trademark usage is governed separately by [`TRADEMARK.md`](https://github.com/SliceOps/spec/blob/main/TRADEMARK.md) in [sliceops-spec](https://github.com/SliceOps/spec). The MIT license does not transfer trademark rights.

---

SliceOps™ is an open framework authored by Andrés Ramírez Sierra. Trademark and copyright held personally.
