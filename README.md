# SliceOps Toolkit

> CI guardrail templates, validators, and tooling for SliceOps™ adopters.

**Status: public · v0.2.1.** Companion to [sliceops-spec](https://github.com/SliceOps/spec). Licensed under the [MIT License](LICENSE) (ratified 2026-06-15, `DEC-2026-06-15-sliceops-license-ratification`).

## What's here

| Path | Purpose |
|---|---|
| `templates/ci-guardrails/` | **Layer B.2 CI/Pipeline Cost Economy** reference templates (5 levers) — bootstrap defaults materializing P9 Shared-Resource Pre-flight |
| `templates/llm-ci-economy/` | **Layer B.2 sub-domain LLM-Inference-Cost-Economy** — workflow demonstrating prompt-caching, model-tier, diff-only context, trigger-set minimalism LLM-aware, and green-not-skipped draft gate |
| `templates/cost-ledger/` | **Layer B.1** cost-ledger template with three dimensions: token (billed-equivalent), infra/CI, and LLM-API-in-CI (P9) |
| `templates/consistency-validators/` | **Layer B.1 Layer 3** consistency validators — workflow + deterministic `validators.py` (10 checks: frontmatter-schema, no-orphan-decs, cross-references-bidirectional, topic-tags, counter-atomicity, principle-count-coherence, entity-count-coherence, band-unit, llm-ci-cost, evidence-schema) + the vendored canonical `evidence.v1` schema (`schemas/`, byte-synced to the spec by CI). Stdlib-only; uses PyYAML and jsonschema automatically when installed |
| `templates/naming-validator/` | **Layer B.1 naming enforcement** (DEC-0008/DEC-0009/DEC-0010, v2) — one `naming_validator.py`, three surfaces: `--check` CI merge gate, `--hook` Claude Code pre-write block (with `settings.example.json`), and the same `--check` as a periodic corpus **sweeper**. Enforces the universal ID grammar (`PREFIX-NNNN-YYYYMMDD-slug.md`), retired prefixes (`DR-`, `IN-`, `OC-`, `BR-`, `SKILL-`, `RUN-`, `REF-`, and the DEC-0008_2 renames `LP-`/`CF-`/`AP-`…), the DEC kind axis + goal edges, the Goal/Priority pyramid, ContextPack kinds (incl. handoff), the slice coordinate (`SLC…`), and the corpus index (`_index.md`) — every message names the correct form; `--transition` tolerates pre-v2 forms while a corpus migrates |
| `templates/counter-discipline/` | **Layer B.1 counter discipline** (P9 Shared-Resource Pre-flight, mechanized) — `claim_id.py` re-scans a corpus for the real max claimed number of an entity, reconciles it against `.counters/`, and claims the next id atomically (lockfile + temp-write + `os.replace`) under the DEC-0008_5 universal grammar |
| `calibration/` | **Layer B.1 Calibration discipline** — deterministic `calibrate.py` (stdlib) parses session `.jsonl` → percentiles (clamped to the observed range) → **canonical** + data-driven **observed** bands; `band-calibration-register.md` is the append-only audit trail |

## Use it

Everything here is **stdlib-only Python 3 (3.9+)** and plain YAML — no install, no dependencies.

**1. Run the consistency validators** on your corpus (exit code is non-zero on any finding, so it drops straight into CI):

```bash
python3 templates/consistency-validators/validators.py \
  --root . --checks all \
  --topic-taxonomy path/to/your/topics.md
# a runtime that tags entities under a mapped frontmatter key:  --entity-key your_key
```

`--checks all` runs all 10 checks; `evidence-schema` validates any `*.evidence.json` / `*.evidence.v1.json` records under `--root` against the canonical [evidence.v1](https://github.com/SliceOps/spec/blob/main/reference/evidence/evidence-v1.md) schema (vendored in `templates/consistency-validators/schemas/`), and reports `SKIPPED` (green) when the corpus has none.

To run it from CI **without vendoring a copy**, see [`templates/consistency-validators/consistency-validators.yml`](templates/consistency-validators/consistency-validators.yml) — it checks the repo out and runs the script. (The SliceOps spec repo runs exactly this on every PR — dogfooding.)

**2. Adopt the CI guardrails** — copy the levers you want from [`templates/ci-guardrails/`](templates/ci-guardrails/) into your `.github/workflows/`; each file's header documents the equivalent for non-GitHub CI. They are bootstrap defaults (P9), not post-incident retrofit.

**3. Calibrate token / context bands** from real session logs:

```bash
python3 calibration/calibrate.py --root path/to/session-jsonl/ --label my-baseline
```

**4. Track cost** with the three-dimension [`templates/cost-ledger/`](templates/cost-ledger/) template (token billed-equivalent + infra/CI + LLM-API-in-CI).

**5. Claim a new artifact id** with [`templates/counter-discipline/claim_id.py`](templates/counter-discipline/claim_id.py) before writing an entity file — it re-scans the corpus for the real max, reconciles `.counters/`, and claims atomically:

```bash
python3 templates/counter-discipline/claim_id.py --root . --entity INS --slug agent-drift-observed
```

> Design posture: these are **reference templates you adapt**, not a black-box dependency — bind `--root` and the conventions to your layout. The validator is stdlib-only but **uses PyYAML automatically when it's installed** (robust parsing) and **jsonschema when it's installed** (full Draft 2020-12 evidence validation), falling back to documented subsets otherwise (the evidence fallback covers required fields, enums, patterns, top-level `additionalProperties`, and the slice-merge completeness rule — NOT format annotations like RFC 3339 date-times, string length bounds, nested `additionalProperties`, or other deep conditional subtleties); path checks are OS-agnostic (Windows/Linux); an unconfigured `--topic-taxonomy` reports `SKIPPED` (green), a *configured-but-missing* one is a hard error, and a corpus with zero evidence records reports `SKIPPED` (green).

## Roadmap (pending)

- Layer 3 Phase 3 validators (glossary-coverage, supersession-chain acyclicity, vocabulary-changes↔glossary sync)
- `validate-folder-structure` (lightweight-pivot structure)
- `validate-shared-resource-preflight`
- slice-forecaster and DAG builder

## Design posture

The **patterns** are vendor-agnostic / stack-agnostic (Layer B.2). Concrete instances (GitHub Actions YAML, specific package managers) are Layer C.2 — each header documents the equivalent for other CI providers so adopters instantiate their own. Guardrails are **bootstrap defaults, never post-incident retrofit** (P9).

## Contributing

Contributions are welcome under the MIT license and a DCO sign-off (`git commit -s`).
See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md);
report security issues per [`SECURITY.md`](SECURITY.md).

## License

Licensed under the [MIT License](LICENSE). Copyright (c) 2026 Andrés Ramírez Sierra.

Code files carry an `SPDX-License-Identifier: MIT` header so per-file scope stays unambiguous when files are reused individually.

SliceOps™ is a trademark of [Andrés Ramírez Sierra](https://andres.co) (EUIPO filing #019381071, pending registration); trademark usage is governed separately by [`TRADEMARK.md`](https://github.com/SliceOps/spec/blob/main/TRADEMARK.md) in [sliceops-spec](https://github.com/SliceOps/spec). The MIT license does not transfer trademark rights.

---

SliceOps™ is an open framework authored by [Andrés Ramírez Sierra](https://andres.co). Trademark and copyright held personally.
