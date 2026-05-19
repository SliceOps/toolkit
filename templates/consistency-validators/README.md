# Consistency Validators — Capa B.1 Layer 3 (reference templates)

Runnable reference implementation of the consistency-management **Layer 3** CI validators. The *specification* lives in the SliceOps spec repo (`reference/r-rules/layer-3-validators.md`); this folder is the *executable starter*.

Layers 1–2 are manual (frontmatter discipline + pre-merge checklist + HITL). Layer 3 automates consistency so corpus health does not depend 100% on human discipline (it does not scale past ~20 DECs by hand).

## Files

| File | Role |
|---|---|
| `consistency-validators.yml` | GitHub Actions workflow — one job per validator + an aggregation-required-gate |
| `validators.py` | Deterministic reference script implementing the checks (Determinism-over-Regeneration B.2 — written once, reused; not AI-regenerated per run) |

## Validators (Phase 2 + counter-atomicity)

| Check | Enforces |
|---|---|
| `cross-references-bidirectional` | DEC A → B in `related-decs` ⇒ B references A |
| `no-orphan-decs` | empty `related-decs` AND empty `topics` ⇒ body must justify isolation |
| `frontmatter-schema` | Layer 1 fields present + well-formed |
| `topic-tags` | every `topics:` value ∈ canonical topic taxonomy |
| `counter-atomicity` | no two artifacts share `<PREFIX>-NNN`; counter store ≥ real max (P12) |

Phase 3 (glossary-coverage, supersession-chain acyclicity, vocabulary-changes↔glossary sync) are documented in the spec and added when the corpus warrants.

## Design

- **Vendor-agnostic pattern / GitHub-Actions instance**: the *pattern* is Capa B.1; this concrete workflow is a Capa C.2 instance. Other CI providers: port the same jobs.
- **Deterministic**: `validators.py` is a fixed script (same corpus → same result), not stochastic regeneration — B.2 Determinism-over-Regeneration, reinforces P5 (repeatable evidence) + P12 (cost economy).
- **Paths/prefixes are configurable**: the script takes the corpus root + prefix map as args so adopters bind it to their layout without editing logic.
- **Bootstrap default**: ships with the repo scaffold, not retrofitted post-incident (P12).

## Adopter instantiation

Copy both files; set the corpus root + `entity:`/prefix conventions; wire `consistency-validators.yml` into branch protection behind the aggregation gate (pair with the CI guardrail templates). Extend with Phase 3 + adopter R15+ checks as the corpus grows (R-rule amendments require a DEC citing a LearningPattern — P7).
