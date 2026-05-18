# CI Guardrails — Capa B.2 reference templates

Reference implementation of the **CI/Pipeline Cost Economy** Universal Engineering Pattern (Capa B.2), materializing principle **P12 — Shared-Resource Pre-flight**.

These are **bootstrap defaults**, not post-incident retrofits. SliceOps's defining mode is aggressive multi-agent parallelism (Wedge B); CI minutes are a finite, serialized, shared resource that scales with `PR_volume × workflow_weight`. Without these guardrails the framework's main lever silently exhausts the resource (observed empirically: a hardening block hard-stopped an entire pipeline when the included CI minutes ran out under a `$0` default spending limit).

## The five levers

| Template | Lever | Why it matters in SliceOps |
|---|---|---|
| `concurrency-cancel.yml` | Cancel in-progress runs per ref | Dominant lever — savings scale with iteration velocity (push-fix-push), the normal SliceOps mode. Default everywhere. |
| `change-scoped-gating.yml` | Gate heavy jobs on code-vs-docs paths | Huge % of SliceOps PRs are markdown/orchestration; they must not trigger heavy compute. |
| `aggregation-required-gate.yml` | Single `always()` job as THE required check | **Mandatory** when using path-gating — resolves the "skipped required check → PR blocked forever" trap. |
| `draft-skip.yml` | Skip expensive jobs on draft PRs | Drafts aren't mergeable; full suite on `ready_for_review`. |
| `dependency-cache.yml` | Cache package store by lockfile hash | Shortens every paid run; compounds with velocity. |

## Vendor-agnostic by design

The **pattern** is Capa B.2 (vendor-agnostic, stack-agnostic). The concrete YAML here is a GitHub Actions **instance** (Capa C.2). Each header documents the equivalent for GitLab / CircleCI / Buildkite / Jenkins so adopters instantiate their own C.2.

## Adoption rule

Repo scaffolds ship with these by default. Pair `change-scoped-gating` with `aggregation-required-gate` always. Verify the real required-check surface via API before redesigning ("empirical-before-optimize").
