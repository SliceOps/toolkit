# Consistency Validators — Layer B.1 Layer 3 (reference templates)

Runnable reference implementation of the consistency-management **Layer 3** CI validators. The *specification* lives in the SliceOps spec repo (`reference/r-rules/layer-3-validators.md`); this folder is the *executable starter*.

Layers 1–2 are manual (frontmatter discipline, pre-merge checklist, and HITL). Layer 3 automates consistency so corpus health does not depend 100% on human discipline (it does not scale past ~20 DECs by hand).

## Files

| File | Role |
|---|---|
| `consistency-validators.yml` | GitHub Actions workflow — one job per validator and an aggregation-required-gate |
| `validators.py` | Deterministic reference script implementing the checks (Determinism-over-Regeneration B.2 — written once, reused; not AI-regenerated per run) |
| `schemas/evidence.v1.schema.json` | Vendored copy of the **canonical** evidence.v1 schema from [sliceops-spec `reference/evidence/`](https://github.com/SliceOps/spec/tree/main/reference/evidence) — byte-synced by the toolkit CI (drift fails the build); never edit it here, re-vendor from the spec |

## Validators (Phase 2, 2.5, evidence, and counter-atomicity)

### Phase 2 — baseline

| Check | Enforces |
|---|---|
| `cross-references-bidirectional` | DEC A → B in `related-decs` ⇒ B references A |
| `no-orphan-decs` | empty `related-decs` AND empty `topics` ⇒ body must justify isolation |
| `frontmatter-schema` | Layer 1 fields present and well-formed |
| `topic-tags` | every `topics:` value ∈ canonical topic taxonomy |
| `counter-atomicity` | no two artifacts share `<PREFIX>-NNN`; counter store ≥ real max (P9) |

### Phase 2.5 — denormalized-drift and unit/cost coherence

| Check | Enforces |
|---|---|
| `principle-count-coherence` | The count of P-NN headings in `principles.md` is the canonical truth; every literal "N principles" / "P4-PN" elsewhere must match. Closes the failure mode that the manual fix-on-touch does not converge (an empirically demonstrated recurrence). |
| `entity-count-coherence` | The count of `NN-*.md` files in `reference/entity-catalog/` is canonical; every literal "N entities" / "N cognitive entities" / "N-entity" must match. Same denormalized-drift family as principle-count. |
| `band-unit` | Token-band must be in **billed-equivalent**, NOT total-with-cache (which inflates ~5×). Flags any spec text declaring token-band in total-with-cache as the canonical unit. |
| `llm-ci-cost` | **R-LLM-CI-COST.** Workflows calling a paid-LLM endpoint must: have a concurrency cancel-in-progress block, NOT trigger on `synchronize` (without a documented exception), and use a step-level draft gate that ends green-not-skipped (a `skipped` required check blocks the PR permanently). |

### Observability reporters (v0.4.0) — signals, never gates

| Reporter | Emits |
|---|---|
| `subslice-rate` | The **sub-slice rate** — the share of distinct slice coordinates (SLC or read-tolerated dotted) carrying a one-letter sub-slice suffix. Per **DEC-0014_4** the rate is a health signal for planning altitude, not a defect. Emitted as a `::notice::`; it **never** sets the failure flag and never blocks a merge (P9 — degradation announced, never a silent cut). |

**Reading the signal.** A sub-slice is emergent granularity discovered *in execution* (the plan commits to structure; execution discovers the leaves — principles P4/P5). A low rate **concentrated in inherently-emergent work** (tooling, cleanup, meta-work) is healthy: the suffix is absorbing only the irreducible tail. A **rising** rate, or sub-slices **spreading into the plannable core of the build**, means slices are being cut too coarse — a prompt to plan finer. The soft 15% waterline is a heuristic "worth a look", not a spec constant. **Emergent → suffix; foreseeable batch → numbered sibling slices** (using the suffix to enumerate a known batch is the misuse that inflates the signal). Reporters are registered in `REPORTER_CHECKS`; adding one there makes it emit-only.

### Plan gate — check #11 (`plan-completeness`)

| Check | Enforces |
|---|---|
| `plan-completeness` | A plan under `6N-execution/6N-plans/` is **complete before its slices execute**: no unchecked definition-of-ready box while the gate claims `READY`, every slice row citing a substrate spec or declared under *Asserted scope*, and every planned coordinate present in the derived DAG. |

**Why it exists.** Every other check here audits the decision corpus or the framework's self-coherence, and every mechanized gate in SliceOps fires at or after **merge** — when code already exists. An incomplete *plan* failed against nothing. This is the first check that runs **before** execution (**DEC-0020** clause 4), the pre-execution counterpart of P6's evidence gate.

**What it does NOT check: altitude.** Whether a plan is coarse or fine is P5's business and stays a judgment call. This check is about **completeness** — a slice that is *declared* is declared in full. Coarse-but-complete is the intended state (DEC-0020 clause 5); both partial cells of that matrix are defects, and neither is licensed by P5.

**Declaring beats omitting.** A slice with no substrate spec is *allowed* when it appears under **Asserted scope** — the point is that asserted scope is visible, not that it is forbidden (**DEC-0017** clause 2). Likewise a plan may carry unchecked boxes when its gate honestly says `BLOCKED`; only a plan **claiming** `READY` must satisfy every one.

**Columns are located by header, never by position.** A plan that renames or drops the *Derives from* column **fails loudly** rather than silently disabling the derivation check — a positional heuristic passed exactly that case during development. Only the `## Slices` table is read: a plan's other tables (*Asserted scope*, *Blocked*, *Waves*) also carry coordinates, and reading them as declarations applies the wrong columns to the wrong rows.

**Discovery**: `*.md` under any `6N-execution/6N-plans/` path (DEC-0011_4), with `6N-execution/6N-dags/` read for the DAG comparison. A corpus with **zero** plans reports `SKIPPED` (green) — a corpus that does not plan here is silent, not failing, the same contract as `evidence-schema`.

Template: [`plan-template.md`](https://github.com/SliceOps/spec/blob/main/reference/templates/plan-template.md) · workflow and the full gate: [`workflows/planning.md`](https://github.com/SliceOps/spec/blob/main/reference/workflows/planning.md).

### evidence.v1 — check #10 (`evidence-schema`)

| Check | Enforces |
|---|---|
| `evidence-schema` | Every **evidence.v1 record** under `--root` validates against the canonical schema (`schemas/evidence.v1.schema.json`, `$id` `https://sliceops.org/schemas/evidence/evidence.v1.schema.json`, approved `DEC-2026-07-02-evidence-v1-canonical-schema`) — including the machine-enforced **P6 slice-merge completeness**: functional+quality+security checks, ≥1 `decisionRefs`, `provenance` with `sliceId`+`commitSha`. |

**Discovery**: ONLY files ending `.evidence.json` or `.evidence.v1.json` under `--root` (frozen lifecycle dirs excluded, as everywhere). Any filename containing `.example.` is a golden fixture and is **never** validated as a record — the spec repo ships three deliberately-invalid `*.evidence.v1.example.json` fixtures that must not break its CI. A corpus with **zero** evidence records reports `SKIPPED` (green): adopting evidence.v1 is opt-in per corpus.

**Dependency policy** (same as PyYAML): if `jsonschema` is importable the check runs **full JSON Schema Draft 2020-12** validation; otherwise a documented **stdlib subset** (json+re) applies, covering: required top-level fields, the `schemaVersion` const, enum membership (`status`, `actor.type`, check `category`/`status`/`severity`, `redaction.status`), pattern checks (`evidenceId`, `operationType`, `provenance.sliceId`/`commitSha`, `decisionRefs`, artifact/trace hashes — exactly 64|96|128 lowercase hex — and reverse-DNS `extensions` keys), `additionalProperties` rejection at the top level, required sub-fields, and the slice-merge completeness rule. The fallback does **NOT** cover: format annotations (RFC 3339 `date-time`), string length bounds, nested `additionalProperties`, or other deep conditional subtleties — install `jsonschema` for the full contract. All enums/patterns the fallback checks are read from the vendored schema at run time (no duplicated literals to drift).

Records carry **no embedded signature** by design (v1: detached signature over the artifact bundle/manifest; the record is hash-anchored) — signature verification is out of this check's scope. See the prose spec [`reference/evidence/evidence-v1.md`](https://github.com/SliceOps/spec/blob/main/reference/evidence/evidence-v1.md).

Phase 3 (glossary-coverage, supersession-chain acyclicity, vocabulary-changes↔glossary sync) are documented in the spec and added when the corpus warrants.

## Design

- **Vendor-agnostic pattern / GitHub-Actions instance**: the *pattern* is Layer B.1; this concrete workflow is a Layer C.2 instance. Other CI providers: port the same jobs.
- **Deterministic**: `validators.py` is a fixed script (same corpus gives the same result), not stochastic regeneration — B.2 Determinism-over-Regeneration, reinforces P6 (repeatable evidence) and P9 (cost economy).
- **Paths/prefixes are configurable**: the script takes the corpus root and prefix map as args so adopters bind it to their layout without editing logic.
- **Bootstrap default**: ships with the repo scaffold, not retrofitted post-incident (P9).

## Adopter instantiation

Copy the folder (workflow + `validators.py` + `schemas/` — the script resolves the vendored schema relative to its own location); set the corpus root and `entity:`/prefix conventions; wire `consistency-validators.yml` into branch protection behind the aggregation gate (pair with the CI guardrail templates). If you vendor, add a sync gate that byte-compares your `schemas/evidence.v1.schema.json` against the spec's raw-main canonical (the toolkit's own `ci.yml` shows the shape). Extend with Phase 3 and adopter R15+ checks as the corpus grows (R-rule amendments require a DEC citing a LearningPattern — P8).
