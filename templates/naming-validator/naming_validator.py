#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SliceOps Layer B.1 — naming validator (spec v1.2.0 naming.md).
# The standard SELF-IMPOSES at the point of write (published-not-enforced is
# the failure mode this closes — LP-003). One tool, three surfaces:
#
#   1. CHECK / CI merge gate:   python3 naming_validator.py --check <path> [<path>...]
#   2. Agent pre-write hook:    python3 naming_validator.py --hook   (PreToolUse JSON on stdin)
#   3. Vault sweeper (no CI):   python3 naming_validator.py --check <vault-root>   (cron/systemd/launchd)
#
# Exit codes: 0 = clean · 1 = violations (--check) · 2 = block write (--hook).
# Every violation message names the CORRECT form. Stdlib only (3.9+), no deps,
# OS-agnostic — runs identically on Linux (gb10) and macOS (MacBook).
#
# Determinism-over-Regeneration (B.2): deterministic rules, same input -> same result.

import argparse
import json
import os
import re
import sys

SPEC = "spec v1.2.0 naming.md"

# entity -> canonical prefix (the 13 Layer B.1 entities; DEC lifecycle variants in §3)
CANON = {
    "DecisionRecord": "DEC-", "InsightRecord": "INS-", "OutcomeRecord": "OUTC-",
    "Capability": "CAP-", "Goal": "GOAL-", "LearningPattern": "LP-",
    "CognitiveFramework": "CF-", "ContextPack": "CP-", "ActivePriority": "AP-",
    "RelationshipContext": "REL-", "Preference": "PREF-", "Value": "VAL-",
    "Session": "SESS-",
}
DEC_PREFIXES = ("DEC-P-", "DEC-D-", "DEC-")  # longest first

# Implementation aliases (naming.md §8): runtime names -> canonical B.1 name.
IMPL_ALIAS = {
    "AgentContextPack": "ContextPack", "AgentSkill": "Capability",
    "GoalObjective": "Goal", "ValuePrinciple": "Value",
    "AgentPreference": "Preference",
}

# Retired filename prefixes (naming.md §1/§7): (regex, display, correct form).
RETIRED = [
    (re.compile(r"^DR-"), "DR-", "DEC- (approved) / DEC-P- (pending) / DEC-D- (deprecated) — lifecycle in the prefix"),
    (re.compile(r"^IR-"), "IR-", "INS-"),
    (re.compile(r"^IN-(?=\d)"), "IN-", "INS-"),
    (re.compile(r"^OC-"), "OC-", "OUTC-"),
    (re.compile(r"^BR-"), "BR-", "OUTC- with kind: retrospective"),
    (re.compile(r"^SKILL-"), "SKILL-", "CAP-"),
    (re.compile(r"^RUN-"), "RUN-", "CAP- (a runbook is a Capability component: kind: runbook)"),
    (re.compile(r"^REF-"), "REF-", "retired catch-all: coding standards -> CAP-, patterns -> LP-, third-party integrations -> vendor connector entity"),
]

DEC_STATUS = {"pending", "approved", "deprecated"}
LEGACY_STATUS = {"proposed": "pending", "ratified": "approved", "active": "approved",
                 "accepted": "approved", "superseded": "deprecated"}
OUTC_KINDS = {"retrospective", "postmortem", "result"}
CAP_KINDS = {"standard", "runbook", "playbook"}
LIFECYCLE_DIRS = {"accepted", "rfcs", "superseded", "deprecated"}

EXCLUDE_DIRS = {".git", ".github", ".obsidian", ".wrangler", ".claude", ".worktrees",
                ".stversions", "node_modules", "build", "dist", "public",
                "99-archive", "archive", ".counters", "_meta", "__MACOSX"}
SKIP_BASENAMES = {"README.md", "CLAUDE.md", "AGENTS.md", "MEMORY.md", "GEMINI.md",
                  "_organization.md", "_index.md", "ledger.md", "CONTRIBUTING.md",
                  "CODE_OF_CONDUCT.md", "GOVERNANCE.md", "SECURITY.md", "LICENSE.md",
                  "DISCLAIMER.md", "DISCLOSURE.md", "TRADEMARK.md", "LEGAL-REVIEW.md",
                  "ATTRIBUTIONS.md", "STATS-PROVENANCE.md"}

FM_KEY = re.compile(r'^\s*(entity|datta_entity|primary-entity|status|kind|capability):\s*"?([A-Za-z0-9 ._:|-]+?)"?\s*(?:#.*)?$')


def frontmatter(text):
    """Top frontmatter block only (never YAML inside code fences)."""
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    fm = {}
    for line in lines[1:120]:
        if line.strip() == "---":
            break
        m = FM_KEY.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            # first occurrence wins for status (top-level), entity keys may repeat
            if key not in fm:
                fm[key] = val
    return fm


def entity_of(fm):
    return fm.get("entity") or fm.get("datta_entity") or fm.get("primary-entity")


def is_exempt(path, base):
    if not base.endswith(".md"):
        return True
    if base in SKIP_BASENAMES or base.startswith("."):
        return True
    if base.endswith("-template.md") or "/templates/" in path.replace(os.sep, "/"):
        return True  # skeletons carry placeholder frontmatter by design
    parts = set(os.path.normpath(path).split(os.sep))
    if parts & EXCLUDE_DIRS:
        return True
    return False


def dec_prefix_for(status):
    return {"pending": "DEC-P-", "deprecated": "DEC-D-"}.get(status, "DEC-")


def validate_file(path, text, tolerate_legacy=False):
    """Returns a list of violation strings for one file."""
    errs = []
    p = path.replace(os.sep, "/")
    base = os.path.basename(p)
    if is_exempt(p, base):
        return errs

    # 1) flat decisions/ — lifecycle subfolders are retired
    m = re.search(r"/(?:10-)?decisions/(accepted|rfcs|superseded|deprecated)/[^/]+\.md$", "/" + p)
    if m:
        errs.append(f"{p}: lifecycle subfolder '{m.group(1)}/' is retired — decisions/ is FLAT; "
                    f"the DEC-/DEC-P-/DEC-D- prefix carries the state ({SPEC} §3)")

    # 2) retired prefixes — always an error, with the correct form
    for rx, display, correct in RETIRED:
        if rx.match(base):
            errs.append(f"{p}: retired prefix '{display}' — use {correct} ({SPEC} §1)")
            break

    fm = frontmatter(text)
    entity = entity_of(fm)
    status = fm.get("status")

    # 3) implementation aliases in the entity key
    if entity in IMPL_ALIAS:
        canonical = IMPL_ALIAS[entity]
        errs.append(f"{p}: entity '{entity}' is an implementation alias — canonical name is "
                    f"'{canonical}' (prefix {CANON[canonical]}) ({SPEC} §8)")
        entity = canonical

    # 4) entity <-> prefix
    if entity in CANON:
        want = CANON[entity]
        if entity == "DecisionRecord":
            if not base.startswith(DEC_PREFIXES):
                suggested = dec_prefix_for(LEGACY_STATUS.get(status, status)) + re.sub(r"^[A-Za-z]+-", "", base)
                errs.append(f"{p}: DecisionRecord file must start with DEC-/DEC-P-/DEC-D- "
                            f"(suggested: {suggested}) ({SPEC} §3)")
        elif not base.startswith(want):
            errs.append(f"{p}: entity {entity} file must start with '{want}' "
                        f"(suggested: {want}{base}) ({SPEC} §1)")

    # 5) DecisionRecord status enum + prefix/status coherence
    if entity == "DecisionRecord" and status:
        if status in LEGACY_STATUS:
            msg = (f"{p}: legacy status '{status}' — write '{LEGACY_STATUS[status]}' "
                   f"(read-tolerated only for archives/non-homologated corpora) ({SPEC} §3)")
            if not tolerate_legacy:
                errs.append(msg)
        elif status not in DEC_STATUS:
            errs.append(f"{p}: status '{status}' not canonical — use pending|approved|deprecated ({SPEC} §3)")
        else:
            want_prefix = dec_prefix_for(status)
            actual = next((x for x in DEC_PREFIXES if base.startswith(x)), None)
            if actual and actual != want_prefix:
                errs.append(f"{p}: prefix '{actual}' does not match status '{status}' "
                            f"(expected prefix {want_prefix}) ({SPEC} §3)")

    # 6) OutcomeRecord kind
    if entity == "OutcomeRecord":
        kind = fm.get("kind")
        if not kind:
            errs.append(f"{p}: OutcomeRecord requires kind: retrospective|postmortem|result ({SPEC} §6)")
        elif kind not in OUTC_KINDS:
            errs.append(f"{p}: OutcomeRecord kind '{kind}' invalid — use retrospective|postmortem|result ({SPEC} §6)")

    # 7) Capability component fields
    if entity == "Capability" and fm.get("kind"):
        kind = fm.get("kind")
        if kind not in CAP_KINDS:
            errs.append(f"{p}: Capability component kind '{kind}' invalid — use standard|runbook|playbook ({SPEC} §5)")
        if not fm.get("capability"):
            errs.append(f"{p}: Capability component (kind: {kind}) requires capability: <mother-slug> ({SPEC} §5)")

    return errs


def iter_targets(paths):
    for target in paths:
        if os.path.isfile(target):
            yield target
        elif os.path.isdir(target):
            for dp, dns, fns in os.walk(target):
                dns[:] = [d for d in dns if d not in EXCLUDE_DIRS]
                for f in sorted(fns):
                    if f.endswith(".md"):
                        yield os.path.join(dp, f)


def run_check(paths, tolerate_legacy=False):
    violations = []
    for path in iter_targets(paths):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        violations.extend(validate_file(path, text, tolerate_legacy))
    for v in violations:
        print(f"NAMING: {v}")
    print(f"naming-validator: {'PASS' if not violations else f'{len(violations)} violation(s)'}")
    return 1 if violations else 0


def run_hook():
    """Claude Code PreToolUse hook (matcher: Write|Edit). Reads the tool call as
    JSON on stdin; exit 2 BLOCKS the write and feeds stderr back to the agent.
    Fails OPEN on unparseable input (availability > strictness; CI still gates)."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path.endswith(".md"):
        return 0
    # Write carries full content; Edit validates path-level rules only
    # (content-level drift is caught by --check in CI / the sweeper).
    content = tool_input.get("content") or ""
    errs = validate_file(file_path, content, tolerate_legacy=False)
    if errs:
        sys.stderr.write(
            "SliceOps naming validator — write BLOCKED (spec v1.2.0 naming.md):\n"
            + "\n".join(f"  - {e}" for e in errs)
            + "\nUse the canonical name indicated above and retry.\n")
        return 2
    return 0


def main():
    ap = argparse.ArgumentParser(description="SliceOps naming validator (spec v1.2.0)")
    ap.add_argument("--check", nargs="+", metavar="PATH",
                    help="validate files/directories; exit 1 on violations (CI gate / sweeper)")
    ap.add_argument("--hook", action="store_true",
                    help="Claude Code PreToolUse hook mode (JSON on stdin; exit 2 blocks)")
    ap.add_argument("--tolerate-legacy-status", action="store_true",
                    help="do not fail on legacy DecisionRecord status values (staged Etapa-2 adoption)")
    args = ap.parse_args()
    if args.hook:
        sys.exit(run_hook())
    if args.check:
        sys.exit(run_check(args.check, args.tolerate_legacy_status))
    ap.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
