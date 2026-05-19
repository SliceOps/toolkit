# SliceOps Toolkit

> CI guardrail templates, validators, and tooling for SliceOps™ adopters.

**Status: scaffolding in progress (private).** Companion to [sliceops-spec](https://github.com/SliceOps/spec). Intended license: MIT (pending IP/Legal ratification — no `LICENSE` file yet by design).

## What's here

| Path | Purpose |
|---|---|
| `templates/ci-guardrails/` | **Capa B.2 CI/Pipeline Cost Economy** reference templates (5 levers) — bootstrap defaults materializing P12 Shared-Resource Pre-flight |
| `templates/cost-ledger/` | **Capa B.1** cost-ledger template with token + infra/CI dual dimension (P12) |
| `templates/consistency-validators/` | **Capa B.1 Layer 3** consistency validators — workflow + deterministic `validators.py` (cross-references-bidirectional, no-orphan-decs, frontmatter-schema, topic-tags, counter-atomicity) |

## Roadmap (pending)

- Layer 3 Phase 3 validators (glossary-coverage, supersession-chain acyclicity, vocabulary-changes↔glossary sync)
- `validate-folder-structure` (lightweight-pivot structure)
- `validate-shared-resource-preflight`
- slice-forecaster + DAG builder

## Design posture

The **patterns** are vendor-agnostic / stack-agnostic (Capa B.2). Concrete instances (GitHub Actions YAML, specific package managers) are Capa C.2 — each header documents the equivalent for other CI providers so adopters instantiate their own. Guardrails are **bootstrap defaults, never post-incident retrofit** (P12).

---

SliceOps™ is an open methodology authored by Andrés Ramírez Sierra. Trademark and copyright held personally.
