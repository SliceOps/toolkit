# SliceOps Toolkit

> CI guardrail templates, validators, and tooling for SliceOps™ adopters.

**Status: public · v0.1.0.** Companion to [sliceops-spec](https://github.com/SliceOps/spec). Licensed under the [MIT License](LICENSE) (ratified 2026-06-15, `DR-2026-06-15-sliceops-license-ratification`).

## What's here

| Path | Purpose |
|---|---|
| `templates/ci-guardrails/` | **Layer B.2 CI/Pipeline Cost Economy** reference templates (5 levers) — bootstrap defaults materializing P9 Shared-Resource Pre-flight |
| `templates/llm-ci-economy/` | **Layer B.2 sub-domain LLM-Inference-Cost-Economy** — workflow demonstrating prompt-caching, model-tier, diff-only context, trigger-set minimalism LLM-aware, and green-not-skipped draft gate |
| `templates/cost-ledger/` | **Layer B.1** cost-ledger template with three dimensions: token (billed-equivalent), infra/CI, and LLM-API-in-CI (P9) |
| `templates/consistency-validators/` | **Layer B.1 Layer 3** consistency validators — workflow and deterministic `validators.py` (cross-references-bidirectional, no-orphan-decs, frontmatter-schema, topic-tags, counter-atomicity) |
| `calibration/` | **Layer B.1 Calibration discipline** — deterministic `calibrate.py` (stdlib) parses session `.jsonl`, then percentiles, then bands; `band-calibration-register.md` is the append-only audit trail (v1 baseline 2026-06-15) |

## Use it

Everything here is **stdlib-only Python 3 (3.9+)** and plain YAML — no install, no dependencies.

**1. Run the consistency validators** on your corpus (exit code is non-zero on any finding, so it drops straight into CI):

```bash
python3 templates/consistency-validators/validators.py \
  --root . --checks all \
  --topic-taxonomy path/to/your/topics.md
# a runtime that tags entities under a mapped frontmatter key:  --entity-key your_key
```

To run it from CI **without vendoring a copy**, see [`templates/consistency-validators/consistency-validators.yml`](templates/consistency-validators/consistency-validators.yml) — it checks the repo out and runs the script. (The SliceOps spec repo runs exactly this on every PR — dogfooding.)

**2. Adopt the CI guardrails** — copy the levers you want from [`templates/ci-guardrails/`](templates/ci-guardrails/) into your `.github/workflows/`; each file's header documents the equivalent for non-GitHub CI. They are bootstrap defaults (P9), not post-incident retrofit.

**3. Calibrate token / context bands** from real session logs:

```bash
python3 calibration/calibrate.py --root path/to/session-jsonl/ --label my-baseline
```

**4. Track cost** with the three-dimension [`templates/cost-ledger/`](templates/cost-ledger/) template (token billed-equivalent + infra/CI + LLM-API-in-CI).

> Design posture: these are **reference templates you adapt**, not a black-box dependency — bind `--root` and the conventions to your layout, swap the stdlib frontmatter parser for a real YAML one if you prefer, and so on.

## Roadmap (pending)

- Layer 3 Phase 3 validators (glossary-coverage, supersession-chain acyclicity, vocabulary-changes↔glossary sync)
- `validate-folder-structure` (lightweight-pivot structure)
- `validate-shared-resource-preflight`
- slice-forecaster and DAG builder

## Design posture

The **patterns** are vendor-agnostic / stack-agnostic (Layer B.2). Concrete instances (GitHub Actions YAML, specific package managers) are Layer C.2 — each header documents the equivalent for other CI providers so adopters instantiate their own. Guardrails are **bootstrap defaults, never post-incident retrofit** (P9).

## License

Licensed under the [MIT License](LICENSE). Copyright (c) 2026 Andrés Ramírez Sierra.

Code files carry an `SPDX-License-Identifier: MIT` header so per-file scope stays unambiguous when files are reused individually.

SliceOps™ is a trademark of [Andrés Ramírez Sierra](https://andres.co) (EUIPO filing #019381071, pending registration); trademark usage is governed separately by [`TRADEMARK.md`](https://github.com/SliceOps/spec/blob/main/TRADEMARK.md) in [sliceops-spec](https://github.com/SliceOps/spec). The MIT license does not transfer trademark rights.

---

SliceOps™ is an open framework authored by [Andrés Ramírez Sierra](https://andres.co). Trademark and copyright held personally.
