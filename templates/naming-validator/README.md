# Naming Validator — Layer B.1 (spec v1.2.0)

Enforces the SliceOps canonical naming standard (`sliceops-spec` → `spec/v1.2.0/naming.md`): **one entity = one prefix**, DecisionRecord lifecycle in the prefix (`DEC-`/`DEC-P-`/`DEC-D-`), flat `decisions/` folders, canonical `status:`/`kind:` enums, and retirement of the legacy prefixes (`DR-`, `IN-`, `IR-`, `OC-`, `BR-`, `SKILL-`, `RUN-`, `REF-`).

The standard **self-imposes at the point of write** — this is the enforcement layer that closes the *published-not-enforced* failure mode (LP-003). Stdlib-only Python 3 (3.9+); identical behavior on Linux and macOS. Every violation message names the **correct** form.

## What it checks

| Rule | Violation → message |
|---|---|
| Retired prefixes | `DR-`/`IN-`/`IR-`/`OC-`/`BR-`/`SKILL-`/`RUN-`/`REF-` file → the canonical prefix to use |
| Entity ↔ prefix | frontmatter entity (`entity:` / `datta_entity:` / `primary-entity:`) whose file lacks its canonical prefix → suggested filename |
| Implementation aliases | `AgentSkill`/`AgentContextPack`/`GoalObjective`/`ValuePrinciple`/`AgentPreference` → canonical B.1 name (naming.md §8) |
| DEC lifecycle | `status:` not in `pending\|approved\|deprecated`; prefix/status mismatch (`DEC-P-` with `approved`, …) |
| Flat decisions/ | any `.md` under `decisions/{accepted,rfcs,superseded,deprecated}/` → flatten |
| OutcomeRecord | missing/invalid `kind: retrospective\|postmortem\|result` |
| Capability components | `kind:` not in `standard\|runbook\|playbook`, or component without `capability:` back-reference |

Out of scope (by design): entities outside the 13-entity catalog (vendor extensions — validated by the vendor), files without entity frontmatter and without a retired prefix (freeform notes), `99-archive/` and other excluded dirs (immutable history), `*-template.md` skeletons.

## The three surfaces

**1. CHECK / CI merge gate** — exit ≠ 0 on any violation:

```bash
python3 templates/naming-validator/naming_validator.py --check <corpus-root> [...]
# staged adoption (Etapa 2): tolerate legacy status values while migrating
python3 naming_validator.py --check . --tolerate-legacy-status
```

Workflow template: [`naming-validator.yml`](naming-validator.yml). The SliceOps spec repo runs this gate on every PR (fetched from this toolkit — dogfooding).

**2. Agent pre-write hook (Claude Code)** — blocks the write and tells the agent the correct name:

```bash
cp naming_validator.py <corpus>/.claude/hooks/naming_validator.py
cp settings.example.json <corpus>/.claude/settings.json   # or merge the "hooks" key
```

The hook + settings live **inside** the corpus, so they sync to every machine with the corpus itself (git/Syncthing) — every session on every machine loads the same gate. Mode: `--hook` reads the PreToolUse JSON on stdin; exit 2 blocks and the stderr message (with the correct name) is fed back to the agent. Fails open on unparseable input — CI/sweeper still gate.

**3. Sweeper (vaults without CI)** — same `--check`, on a schedule:

```bash
# cron (Linux) — weekly sweep, report by mail/log:
# 0 8 * * 1  python3 ~/vault/.claude/hooks/naming_validator.py --check ~/vault || notify …
# launchd (macOS): wrap the same command in a LaunchAgent plist.
python3 naming_validator.py --check <vault-root>
```

Covers human edits (Obsidian/VS Code) and any surface the hook does not see.

## Design posture

Reference template you adapt (bind roots/conventions to your layout). The rules mirror `naming.md` — the spec is the single normative source; this script points at it in every message and never redefines the tables.
