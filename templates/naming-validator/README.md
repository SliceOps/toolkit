# Naming Validator — Layer B.1 (DEC-0008 / DEC-0009 / DEC-0010, v2)

Enforces the SliceOps canonical naming standard: the universal ID grammar
(`PREFIX-NNNN-YYYYMMDD-slug.md`), the 13-entity catalog with its plain-word
renames, the DecisionRecord **kind** axis and goal edges, the Goal/Priority
pyramid, ContextPack kinds (including handoffs), the slice coordinate
(`SLC…`), and the corpus index (`_index.md`).

The standard **self-imposes at the point of write** — this is the enforcement
layer that closes the *published-not-enforced* failure mode (CONC- successor
of the former LP-003). Stdlib-only Python 3 (3.9+); identical behavior on
Linux and macOS. Every violation message names the **correct** form and cites
the deciding clause (`DEC-0008.n` / `DEC-0009` / `DEC-0010`).

Normative source — never redefined here, only pointed at:
[`DEC-0008`](https://github.com/SliceOps/spec/blob/main/decisions/DEC-0008-20260712-cognitive-cycle-and-universal-id-scheme.md) (cognition cycle, universal grammar, kind axis, pyramid, slice coordinate),
[`DEC-0009`](https://github.com/SliceOps/spec/blob/main/decisions/DEC-0009-20260712-handoffs-as-a-contextpack-kind.md) (ContextPack kinds incl. handoff),
[`DEC-0010`](https://github.com/SliceOps/spec/blob/main/decisions/DEC-0010-20260712-corpus-index-as-reserved-name-infrastructure.md) (`_index.md` reserved-name infrastructure).

## What it checks

| Rule | Violation → message |
|---|---|
| Universal ID grammar | filename not matching `PREFIX-NNNN-YYYYMMDD-slug.md` (min 4-digit zero-padded counter, unbounded; compact 8-digit date; kebab-case lowercase slug) → suggested shape (DEC-0008.5) |
| Retired prefixes | `DR-`/`IN-`/`IR-`/`OC-`/`BR-`/`SKILL-`/`RUN-`/`REF-`/`LP-`/`CF-`/`AP-` file → the canonical prefix to use (the last three retired by the DEC-0008.2 plain-word renames: `LP-`→`CONC-`, `CF-`→`FRAME-`, `AP-`→`PRI-`) |
| Entity ↔ prefix | frontmatter entity (`entity:` / `datta_entity:` / `primary-entity:`) whose file lacks its canonical prefix → suggested filename |
| Implementation aliases | `AgentSkill`/`AgentContextPack`/`GoalObjective`/`ValuePrinciple`/`AgentPreference`, **and** the pre-DEC-0008 entity names `LearningPattern`/`CognitiveFramework`/`ActivePriority` → canonical plain-word name |
| DEC lifecycle | `status:` not in `pending\|approved\|deprecated`; prefix/status mismatch (`DEC-P-` with `approved`, …); flat `decisions/` (no lifecycle subfolders) |
| DEC kind axis | `kind:` not in `constitutive\|strategic\|tactical`; `strategic` without `defines-goal:`; `tactical` without `serves-goal:`; `constitutive` + `status: approved` without `approver:`; `kind:` missing on a DecisionRecord created on/after 2026-07-13 (earlier DECs back-fill fix-on-touch) (DEC-0008.3) |
| Pyramid | `Goal` without `decided-by:`; `Priority` without `serves-goal:` or integer `rank:`; `priority: high\|medium\|low` (retired — use `rank:`) (DEC-0008.4) |
| ContextPack kinds | `kind:` not in `pack\|brief\|handoff`; `kind: handoff` with `reason:` not in `context-exhausted\|spinoff` (DEC-0009) |
| Slice coordinate | filename leading `SLC` not matching `SLC\d{4,}(SEC\d{2,})?(BL\d{2,})?-YYYYMMDD-slug.md`; frontmatter `originating_slice:` not matching the bare coordinate; the retired dotted form (`BL-XX.SEC-XX.SL-XXX`) → SLC suggestion (DEC-0008.6) |
| Corpus index | (directory `--check` targets only) missing root `_index.md`; any route-table target in `_index.md` that does not resolve on disk (DEC-0010) |
| OutcomeRecord | missing/invalid `kind: retrospective\|postmortem\|result` |
| Capability components | `kind:` not in `standard\|runbook\|playbook`, or component without `capability:` back-reference |

Out of scope (by design): entities outside the 13-entity catalog (vendor
extensions — validated by the vendor), files without entity frontmatter and
without a retired/recognizable entity prefix (freeform notes),
`99-archive/` and other excluded dirs (immutable history), `*-template.md`
skeletons, and the reserved-name infrastructure list (DEC-0010.5):
`README.md`, `CLAUDE.md`/`AGENTS.md`, `MEMORY.md`, `GEMINI.md`,
`_organization.md`, `_index.md`, `*-ledger.md`.

## `--transition`: tolerate pre-v2 forms during migration

Default mode is **strict** (v2 rules only). `--transition` tolerates, instead
of failing on:

- legacy DecisionRecord `status:` values (same set `--tolerate-legacy-status` covers)
- pre-v2 filename grammars: date-based (`PREFIX-YYYY-MM-DD-slug.md`, the
  v1.2.0-era vault scheme) and counter-based 3-digit (`PREFIX-NNN-slug.md`,
  pre-homologation repos)
- a missing root `_index.md`
- the legacy dotted Slice ID (`BL-XX.SEC-XX.SL-XXX`) in `originating_slice:`
- a DecisionRecord created on/after the kind-cutoff with no `kind:` yet

Use it on a corpus mid-migration to the v2 grammar; drop it once the corpus
is fully re-cut. `--hook` mode never accepts `--transition` — agent writes
are always graded against the strict v2 rules, so no new file is born
non-compliant.

## The three surfaces

**1. CHECK / CI merge gate** — exit ≠ 0 on any violation:

```bash
python3 templates/naming-validator/naming_validator.py --check <corpus-root> [...]
# staged adoption: tolerate legacy status values only
python3 naming_validator.py --check . --tolerate-legacy-status
# staged adoption: tolerate the full pre-v2 form set while migrating
python3 naming_validator.py --check . --transition
```

Workflow template: [`naming-validator.yml`](naming-validator.yml). The SliceOps spec repo runs this gate on every PR (fetched from this toolkit — dogfooding).

**2. Agent pre-write hook (Claude Code)** — blocks the write and tells the agent the correct name:

```bash
cp naming_validator.py <corpus>/.claude/hooks/naming_validator.py
cp settings.example.json <corpus>/.claude/settings.json   # or merge the "hooks" key
```

The hook + settings live **inside** the corpus, so they sync to every machine with the corpus itself (git/Syncthing) — every session on every machine loads the same gate. Mode: `--hook` reads the PreToolUse JSON on stdin; exit 2 blocks and the stderr message (with the correct name) is fed back to the agent. Fails open on unparseable input — CI/sweeper still gate. The DEC-0010 `_index.md` check never runs in `--hook` mode (it is a corpus-wide concern; the hook validates one write).

**3. Sweeper (vaults without CI)** — same `--check`, on a schedule:

```bash
# cron (Linux) — weekly sweep, report by mail/log:
# 0 8 * * 1  python3 ~/vault/.claude/hooks/naming_validator.py --check ~/vault || notify …
# launchd (macOS): wrap the same command in a LaunchAgent plist.
python3 naming_validator.py --check <vault-root>
```

Covers human edits (Obsidian/VS Code) and any surface the hook does not see.

## Claiming a new id

This validator checks SHAPE; it does not reserve numbers. To claim the next
real id for an entity under the P9 pre-flight discipline (re-scan the corpus
for the real max before claiming), see
[`../counter-discipline/claim_id.py`](../counter-discipline/claim_id.py).

## Design posture

Reference template you adapt (bind roots/conventions to your layout). The
rules mirror DEC-0008/0009/0010 — the DECs are the single normative source;
this script points at them in every message and never redefines the catalog
table (DEC-0008.2.1 is single source).
