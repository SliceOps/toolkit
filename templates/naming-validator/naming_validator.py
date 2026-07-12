#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SliceOps Layer B.1 — naming validator (DEC-0008 / DEC-0009 / DEC-0010, v2).
# The standard SELF-IMPOSES at the point of write (published-not-enforced is
# the failure mode this closes — LP-003 / CONC- successor). One tool, three surfaces:
#
#   1. CHECK / CI merge gate:   python3 naming_validator.py --check <path> [<path>...]
#   2. Agent pre-write hook:    python3 naming_validator.py --hook   (PreToolUse JSON on stdin)
#   3. Vault sweeper (no CI):   python3 naming_validator.py --check <vault-root>   (cron/systemd/launchd)
#
# Exit codes: 0 = clean · 1 = violations (--check) · 2 = block write (--hook).
# Every violation message names the CORRECT form. Stdlib only (3.9+), no deps,
# OS-agnostic — runs identically on Linux and macOS.
#
# Determinism-over-Regeneration (B.2): deterministic rules, same input -> same result.
#
# Normative source: DEC-0008 (cognition cycle + universal ID grammar + kind axis
# + pyramid), DEC-0009 (ContextPack kinds incl. handoff), DEC-0010 (_index.md
# reserved-name infrastructure). This script points at the DECs in every
# message and never redefines the catalog table (DEC-0008.2.1 is single source).

import argparse
import json
import os
import re
import sys

DEC8 = "DEC-0008"
DEC9 = "DEC-0009"
DEC10 = "DEC-0010"

# entity -> canonical prefix (the 13-entity catalog, DEC-0008.2.1; DEC lifecycle
# variants carry state in the prefix per DEC-0008.5 rule 3).
CANON = {
    "DecisionRecord": "DEC-", "InsightRecord": "INS-", "OutcomeRecord": "OUTC-",
    "Capability": "CAP-", "Goal": "GOAL-", "Conclusion": "CONC-",
    "Frame": "FRAME-", "ContextPack": "CP-", "Priority": "PRI-",
    "RelationshipContext": "REL-", "Preference": "PREF-", "Value": "VAL-",
    "Session": "SESS-",
}
DEC_PREFIXES = ("DEC-P-", "DEC-D-", "DEC-")  # longest first

# Implementation aliases (naming.md §8, runtime enum names) -> canonical entity.
IMPL_ALIAS = {
    "AgentContextPack": "ContextPack", "AgentSkill": "Capability",
    "GoalObjective": "Goal", "ValuePrinciple": "Value",
    "AgentPreference": "Preference",
    # DEC-0008.2 renames: the OLD entity names are now implementation aliases
    # of the plain-word canonical ones — never their own prefix again.
    "LearningPattern": "Conclusion", "CognitiveFramework": "Frame",
    "ActivePriority": "Priority",
}

# Retired filename prefixes: (regex, display, correct form, citation).
# Longest-match-first ordering matters within a shared leading letter (LP-/L*
# does not collide with anything else here, so simple list order is enough).
RETIRED = [
    (re.compile(r"^DR-"), "DR-", "DEC- (approved) / DEC-P- (pending) / DEC-D- (deprecated) — lifecycle in the prefix", DEC8),
    (re.compile(r"^IR-"), "IR-", "INS-", DEC8),
    (re.compile(r"^IN-(?=\d)"), "IN-", "INS-", DEC8),
    (re.compile(r"^OC-"), "OC-", "OUTC-", DEC8),
    (re.compile(r"^BR-"), "BR-", "OUTC- with kind: retrospective", DEC8),
    (re.compile(r"^SKILL-"), "SKILL-", "CAP-", DEC8),
    (re.compile(r"^RUN-"), "RUN-", "CAP- (a runbook is a Capability component: kind: runbook)", DEC8),
    (re.compile(r"^REF-"), "REF-", "retired catch-all: coding standards -> CAP-, patterns -> CONC-, third-party integrations -> vendor connector entity", DEC8),
    (re.compile(r"^LP-"), "LP-", "CONC- (Conclusion — DEC-0008.2 rename)", DEC8),
    (re.compile(r"^CF-"), "CF-", "FRAME- (Frame — DEC-0008.2 rename)", DEC8),
    (re.compile(r"^AP-"), "AP-", "PRI- (Priority — DEC-0008.2 rename)", DEC8),
]

DEC_STATUS = {"pending", "approved", "deprecated"}
LEGACY_STATUS = {"proposed": "pending", "ratified": "approved", "active": "approved",
                 "accepted": "approved", "superseded": "deprecated"}
OUTC_KINDS = {"retrospective", "postmortem", "result"}
CAP_KINDS = {"standard", "runbook", "playbook"}
DEC_KINDS = {"constitutive", "strategic", "tactical"}
CP_KINDS = {"pack", "brief", "handoff"}
CP_HANDOFF_REASONS = {"context-exhausted", "spinoff"}
LIFECYCLE_DIRS = {"accepted", "rfcs", "superseded", "deprecated"}

# DEC-0008.3: kind: is OBLIGATORY only for DECs created on/after this date
# (earlier DECs are back-filled fix-on-touch — same cutoff pattern as the
# consistency validators' P3 author!=approver check, approver_cutoff).
DEC_KIND_CUTOFF = "2026-07-13"

EXCLUDE_DIRS = {".git", ".github", ".obsidian", ".wrangler", ".claude", ".worktrees",
                ".stversions", "node_modules", "build", "dist", "public",
                "99-archive", "archive", ".counters", "_meta", "__MACOSX"}

# Reserved-name infrastructure (DEC-0010.5): exempt from the universal grammar,
# never entity artifacts. *-ledger.md is a suffix pattern, matched separately.
SKIP_BASENAMES = {"README.md", "CLAUDE.md", "AGENTS.md", "MEMORY.md", "GEMINI.md",
                  "_organization.md", "_index.md", "CONTRIBUTING.md",
                  "CODE_OF_CONDUCT.md", "GOVERNANCE.md", "SECURITY.md", "LICENSE.md",
                  "DISCLAIMER.md", "DISCLOSURE.md", "TRADEMARK.md", "LEGAL-REVIEW.md",
                  "ATTRIBUTIONS.md", "STATS-PROVENANCE.md"}
# DEC-0010.5 gives the glob "*-ledger.md"; the real-world precedent artifact
# (brain/slices/ledger.md) is the bare basename with no hyphenated prefix, so
# this also accepts the exact "ledger.md" — the intent (ledgers are reserved
# operational infrastructure, never entity artifacts) covers both.
LEDGER_SUFFIX = re.compile(r"(^|-)ledger\.md$", re.I)

#  Value class is deliberately permissive (Unicode letters allowed — human
#  names like 'Andrés' in approver: must not be dropped) rather than an
#  ASCII enum-only class: this key set mixes enum-like fields (status, kind)
#  with free-text ones (approver, decided-by). Strict enum SHAPE is validated
#  separately, downstream, against the specific canonical value sets.
FM_KEY = re.compile(r'^\s*(entity|datta_entity|primary-entity|status|kind|capability|'
                     r'originating_slice|serves-goal|defines-goal|decided-by|rank|priority|'
                     r'reason|approver|created):\s*"?([^"#\n]+?)"?\s*(?:#.*)?$')
# defines-goal / serves-value / etc. can be list-valued (`[GOAL-..., ...]`); the
# scalar FM_KEY above only needs to detect PRESENCE for the edge-coherence
# checks, so a non-empty match (scalar or the literal `[...]` text) is enough.

# Universal ID grammar (DEC-0008.5): PREFIX-NNNN-YYYYMMDD-slug.md
# Prefix alternation is longest-first so DEC-P-/DEC-D- match before bare DEC-.
_PREFIX_ALT = "DEC-P|DEC-D|DEC|INS|OUTC|CAP|GOAL|CONC|FRAME|CP|PRI|REL|PREF|VAL|SESS"
UNIVERSAL_GRAMMAR = re.compile(
    r"^(?:%s)-(\d{4,})-(\d{8})-([a-z0-9][a-z0-9-]*)\.md$" % _PREFIX_ALT)
# Any recognizable entity-prefix lead (used to decide whether a name that fails
# the grammar is "close enough" to be graded against it, vs. genuinely freeform).
ENTITY_PREFIX_LEAD = re.compile(r"^(?:%s)-" % _PREFIX_ALT)

# Slice coordinate (DEC-0008.6): filename form and the bare frontmatter form.
SLC_FILENAME = re.compile(r"^SLC\d{4,}(SEC\d{2,})?(BL\d{2,})?-\d{8}-[a-z0-9-]+\.md$")
SLC_COORD = re.compile(r"^SLC\d{4,}(SEC\d{2,})?(BL\d{2,})?$")
SLC_LEAD = re.compile(r"^SLC")
# Legacy dotted Slice ID (BL-XX.SEC-XX.SL-XXX), retired by DEC-0008.6.
SLC_LEGACY_DOTTED = re.compile(r"^BL-?\d+\.SEC-?\d+\.SL-?\d+$", re.I)

# --transition-tolerated PRE-v2 filename forms (retired by DEC-0008.5 but not
# yet migrated everywhere): date-based (naming homologation v1.2.0 grammar)
# and counter-based 3-digit (pre-homologation repos, e.g. INS-001-a.md).
PRE_V2_DATE_BASED = re.compile(r"^(?:%s)-\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*\.md$" % _PREFIX_ALT)
PRE_V2_COUNTER_BASED = re.compile(r"^(?:%s)-\d{3}-[a-z0-9][a-z0-9-]*\.md$" % _PREFIX_ALT)


def frontmatter(text):
    """Top frontmatter block only (never YAML inside code fences)."""
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    fm = {}
    for line in lines[1:200]:
        if line.strip() == "---":
            break
        m = FM_KEY.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if key not in fm:
                fm[key] = val
        else:
            # list-valued edge fields (`defines-goal: [GOAL-0001-...]`) — the
            # scalar regex above requires a bare-word value, so catch the
            # bracketed list form separately, presence-only.
            m2 = re.match(r'^\s*(defines-goal|serves-goal|conflicts-with):\s*(\[.*\])\s*(?:#.*)?$', line)
            if m2 and m2.group(1) not in fm:
                fm[m2.group(1)] = m2.group(2)
    return fm


def entity_of(fm):
    return fm.get("entity") or fm.get("datta_entity") or fm.get("primary-entity")


def is_reserved_name(base):
    return base in SKIP_BASENAMES or bool(LEDGER_SUFFIX.search(base))


def is_exempt(path, base):
    if not base.endswith(".md"):
        return True
    if is_reserved_name(base) or base.startswith("."):
        return True
    if base.endswith("-template.md") or "/templates/" in path.replace(os.sep, "/"):
        return True  # skeletons carry placeholder frontmatter by design
    parts = set(os.path.normpath(path).split(os.sep))
    if parts & EXCLUDE_DIRS:
        return True
    return False


def dec_prefix_for(status):
    return {"pending": "DEC-P-", "deprecated": "DEC-D-"}.get(status, "DEC-")


def _has_value(fm, key):
    v = fm.get(key)
    return v is not None and str(v).strip() not in ("", "[]", "null", "None")


def _suggest_universal_name(base, entity, status, created, transition):
    """Best-effort suggested filename under the universal grammar, used in
    messages. Falls back to a generic NNNN/date placeholder when unknown —
    messages always show the correct SHAPE even without real counter state
    (claim_id.py is the tool that reserves a real number)."""
    prefix = CANON.get(entity, "")
    if entity == "DecisionRecord":
        prefix = dec_prefix_for(status)
    date8 = re.sub(r"-", "", created) if created and re.match(r"^\d{4}-\d{2}-\d{2}$", created) else "YYYYMMDD"
    slug = re.sub(r"\.md$", "", base)
    slug = re.sub(r"^[A-Za-z]+(?:-[PD])?-", "", slug)   # strip the leading prefix (incl. DEC-P-/DEC-D-)
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug)      # then a pre-v2 date-based lead, if present
    slug = re.sub(r"^\d{4,}-", "", slug)                 # else a pre-v2/legacy counter lead, if present
    slug = slug.lower() or "slug"
    return f"{prefix}NNNN-{date8}-{slug}.md"


def validate_file(path, text, tolerate_legacy=False, transition=False):
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
                    f"the DEC-/DEC-P-/DEC-D- prefix carries the state ({DEC8}.5)")

    # 2) retired prefixes — always an error (even under --transition: these are
    #    dead names, never a pre-v2-but-valid form), with the correct form
    for rx, display, correct, cite in RETIRED:
        if rx.match(base):
            errs.append(f"{p}: retired prefix '{display}' — use {correct} ({cite})")
            break

    fm = frontmatter(text)
    entity = entity_of(fm)
    status = fm.get("status")
    created = fm.get("created")

    # 3) implementation aliases in the entity key (includes the DEC-0008.2 renames)
    if entity in IMPL_ALIAS:
        canonical = IMPL_ALIAS[entity]
        errs.append(f"{p}: entity '{entity}' is an implementation alias — canonical name is "
                    f"'{canonical}' (prefix {CANON[canonical]}) ({DEC8}.2)")
        entity = canonical

    # 4) entity <-> prefix
    if entity in CANON:
        want = CANON[entity]
        if entity == "DecisionRecord":
            if not base.startswith(DEC_PREFIXES):
                suggested = dec_prefix_for(LEGACY_STATUS.get(status, status)) + re.sub(r"^[A-Za-z]+-", "", base)
                errs.append(f"{p}: DecisionRecord file must start with DEC-/DEC-P-/DEC-D- "
                            f"(suggested: {suggested}) ({DEC8}.5)")
        elif not base.startswith(want):
            errs.append(f"{p}: entity {entity} file must start with '{want}' "
                        f"(suggested: {want}{base}) ({DEC8}.5)")

    # 5) DecisionRecord status enum + prefix/status coherence
    if entity == "DecisionRecord" and status:
        if status in LEGACY_STATUS:
            msg = (f"{p}: legacy status '{status}' — write '{LEGACY_STATUS[status]}' "
                   f"(read-tolerated only for archives/non-homologated corpora) ({DEC8}.2.1)")
            if not (tolerate_legacy or transition):
                errs.append(msg)
        elif status not in DEC_STATUS:
            errs.append(f"{p}: status '{status}' not canonical — use pending|approved|deprecated ({DEC8}.2.1)")
        else:
            want_prefix = dec_prefix_for(status)
            actual = next((x for x in DEC_PREFIXES if base.startswith(x)), None)
            if actual and actual != want_prefix:
                errs.append(f"{p}: prefix '{actual}' does not match status '{status}' "
                            f"(expected prefix {want_prefix}) ({DEC8}.2.1)")

    # 6) OutcomeRecord kind
    if entity == "OutcomeRecord":
        kind = fm.get("kind")
        if not kind:
            errs.append(f"{p}: OutcomeRecord requires kind: retrospective|postmortem|result ({DEC8}.2.1)")
        elif kind not in OUTC_KINDS:
            errs.append(f"{p}: OutcomeRecord kind '{kind}' invalid — use retrospective|postmortem|result ({DEC8}.2.1)")

    # 7) Capability component fields
    if entity == "Capability" and fm.get("kind"):
        kind = fm.get("kind")
        if kind not in CAP_KINDS:
            errs.append(f"{p}: Capability component kind '{kind}' invalid — use standard|runbook|playbook ({DEC8}.2.1)")
        if not fm.get("capability"):
            errs.append(f"{p}: Capability component (kind: {kind}) requires capability: <mother-slug> ({DEC8}.2.1)")

    # 8) DecisionRecord kind axis + edge coherence (DEC-0008.3)
    if entity == "DecisionRecord":
        kind = fm.get("kind")
        kind_required = bool(created) and str(created).strip() >= DEC_KIND_CUTOFF
        if kind:
            if kind not in DEC_KINDS:
                errs.append(f"{p}: DecisionRecord kind '{kind}' invalid — use constitutive|strategic|tactical ({DEC8}.3)")
            else:
                if kind == "strategic" and not _has_value(fm, "defines-goal"):
                    errs.append(f"{p}: kind: strategic requires defines-goal: [<GOAL id>...] ({DEC8}.3)")
                if kind == "tactical" and not _has_value(fm, "serves-goal"):
                    errs.append(f"{p}: kind: tactical requires serves-goal: <GOAL id> ({DEC8}.3)")
                if kind == "constitutive" and status == "approved" and not _has_value(fm, "approver"):
                    errs.append(f"{p}: kind: constitutive with status: approved requires approver: <name> ({DEC8}.3)")
        elif kind_required and not transition:
            errs.append(f"{p}: DecisionRecord created on/after {DEC_KIND_CUTOFF} requires "
                        f"kind: constitutive|strategic|tactical ({DEC8}.3; earlier DECs are back-filled fix-on-touch)")

    # 9) Pyramid — Goal.decided-by, Priority.serves-goal + rank (DEC-0008.4)
    if entity == "Goal":
        if not _has_value(fm, "decided-by"):
            errs.append(f"{p}: Goal requires decided-by: <DEC id> ({DEC8}.4)")
    if entity == "Priority":
        if not _has_value(fm, "serves-goal"):
            errs.append(f"{p}: Priority requires serves-goal: <GOAL id> ({DEC8}.4)")
        if fm.get("priority") in ("high", "medium", "low"):
            errs.append(f"{p}: priority: {fm.get('priority')} is retired — use rank: <int> ({DEC8}.4)")
        elif not _has_value(fm, "rank"):
            errs.append(f"{p}: Priority requires rank: <int> (unique within owner+horizon) ({DEC8}.4)")
        else:
            rank = fm.get("rank")
            if not re.match(r"^-?\d+$", str(rank).strip()):
                errs.append(f"{p}: Priority rank '{rank}' is not an integer ({DEC8}.4)")

    # 10) ContextPack kinds + handoff reason (DEC-0009)
    if entity == "ContextPack":
        kind = fm.get("kind")
        if kind:
            if kind not in CP_KINDS:
                errs.append(f"{p}: ContextPack kind '{kind}' invalid — use pack|brief|handoff ({DEC9})")
            elif kind == "handoff":
                reason = fm.get("reason")
                if reason and reason not in CP_HANDOFF_REASONS:
                    errs.append(f"{p}: ContextPack kind: handoff reason '{reason}' invalid — "
                                f"use context-exhausted|spinoff ({DEC9})")

    # 11) Slice coordinate — frontmatter form (DEC-0008.6)
    slice_val = fm.get("originating_slice")
    if slice_val and slice_val not in ("null", "None"):
        if SLC_LEGACY_DOTTED.match(slice_val):
            if not transition:
                errs.append(f"{p}: originating_slice '{slice_val}' uses the retired dotted Slice ID "
                            f"(BL-XX.SEC-XX.SL-XXX) — use the SLC coordinate, e.g. SLC0012SEC03BL02 "
                            f"({DEC8}.6)")
        elif SLC_LEAD.match(slice_val) and not SLC_COORD.match(slice_val):
            errs.append(f"{p}: originating_slice '{slice_val}' does not match the SLC coordinate "
                        f"grammar SLC\\d{{4,}}(SEC\\d{{2,}})?(BL\\d{{2,}})? ({DEC8}.6)")

    # 12) Slice coordinate — filename form (DEC-0008.6)
    if SLC_LEAD.match(base) and not SLC_FILENAME.match(base):
        if not (transition and (PRE_V2_DATE_BASED.match(base) or PRE_V2_COUNTER_BASED.match(base))):
            errs.append(f"{p}: slice-coordinate filename must match "
                        f"SLC\\d{{4,}}(SEC\\d{{2,}})?(BL\\d{{2,}})?-YYYYMMDD-slug.md ({DEC8}.6)")

    # 13) Universal ID grammar (DEC-0008.5) — applies to any file that carries
    #     a recognized catalog entity, OR whose name leads with a recognized
    #     entity prefix (so a malformed name is still caught even if the
    #     frontmatter entity key itself is missing/misspelled).
    grammar_applies = (entity in CANON) or ENTITY_PREFIX_LEAD.match(base)
    if grammar_applies and not UNIVERSAL_GRAMMAR.match(base):
        if transition and (PRE_V2_DATE_BASED.match(base) or PRE_V2_COUNTER_BASED.match(base)):
            pass  # pre-v2 form tolerated in transition mode
        else:
            suggestion = _suggest_universal_name(base, entity, status, created, transition)
            errs.append(f"{p}: filename does not match the universal grammar "
                        f"PREFIX-NNNN-YYYYMMDD-slug.md (suggested shape: {suggestion}) ({DEC8}.5)")

    return errs


def _parse_index_targets(index_path, index_text):
    """Extract relative markdown link/path targets from an _index.md route
    table. Matches markdown links `[text](target)` and bare backticked paths
    `` `path/to/file.md` `` — the two forms DEC-0010.3 route tables use.
    Ignores absolute URLs (http/https/mailto) and in-page anchors (#...)."""
    targets = []
    for m in re.finditer(r"\]\(([^)]+)\)", index_text):
        targets.append(m.group(1))
    for m in re.finditer(r"`([^`\s]+\.md(?:#[^`]*)?)`", index_text):
        targets.append(m.group(1))
    out = []
    for t in targets:
        t = t.strip()
        if not t or t.startswith(("http://", "https://", "mailto:", "#")):
            continue
        t = t.split("#", 1)[0]
        if t:
            out.append(t)
    return out


def check_index(root, transition=False):
    """DEC-0010: every corpus root carries _index.md; every route target
    resolves. Only meaningful for a directory root (a single-file --check or
    --hook invocation has no 'corpus' to index)."""
    errs = []
    index_path = os.path.join(root, "_index.md")
    if not os.path.isfile(index_path):
        if not transition:
            errs.append(f"{root}: missing root _index.md ({DEC10}.1/.4 — every corpus root "
                        f"requires a route-table index)")
        return errs
    try:
        with open(index_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return errs
    for target in _parse_index_targets(index_path, text):
        if target.startswith("/"):
            candidate = os.path.join(root, target.lstrip("/"))
        else:
            candidate = os.path.normpath(os.path.join(root, target))
        if not os.path.exists(candidate):
            errs.append(f"{index_path}: route target '{target}' does not resolve "
                        f"(broken path — {DEC10}.4)")
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


def run_check(paths, tolerate_legacy=False, transition=False):
    violations = []
    for path in iter_targets(paths):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        violations.extend(validate_file(path, text, tolerate_legacy, transition))
    # DEC-0010 corpus-index check: only for directory roots passed on --check
    # (never in --hook mode, which validates a single written file — DEC-0010
    # doesn't apply to per-file writes; a --check invocation on loose files
    # with no directory argument has no corpus root to index either).
    for target in paths:
        if os.path.isdir(target):
            violations.extend(check_index(target, transition))
    for v in violations:
        print(f"NAMING: {v}")
    print(f"naming-validator: {'PASS' if not violations else f'{len(violations)} violation(s)'}")
    return 1 if violations else 0


def run_hook():
    """Claude Code PreToolUse hook (matcher: Write|Edit). Reads the tool call as
    JSON on stdin; exit 2 BLOCKS the write and feeds stderr back to the agent.
    Fails OPEN on unparseable input (availability > strictness; CI still gates).
    Never runs the DEC-0010 _index.md check — that is a corpus-wide concern,
    not a single-file one (see run_check)."""
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
    errs = validate_file(file_path, content, tolerate_legacy=False, transition=False)
    if errs:
        sys.stderr.write(
            f"SliceOps naming validator — write BLOCKED ({DEC8} / {DEC9} / {DEC10}):\n"
            + "\n".join(f"  - {e}" for e in errs)
            + "\nUse the canonical name/shape indicated above and retry.\n")
        return 2
    return 0


def main():
    ap = argparse.ArgumentParser(description="SliceOps naming validator (DEC-0008/0009/0010, v2)")
    ap.add_argument("--check", nargs="+", metavar="PATH",
                    help="validate files/directories; exit 1 on violations (CI gate / sweeper)")
    ap.add_argument("--hook", action="store_true",
                    help="Claude Code PreToolUse hook mode (JSON on stdin; exit 2 blocks)")
    ap.add_argument("--tolerate-legacy-status", action="store_true",
                    help="do not fail on legacy DecisionRecord status values (staged Etapa-2 adoption)")
    ap.add_argument("--transition", action="store_true",
                    help="tolerate pre-v2 forms during migration: legacy statuses, pre-v2 filename "
                         "grammar (date-based / 3-digit counter-based), missing _index.md, and the "
                         "legacy dotted Slice ID. Default is strict (v2 rules only).")
    args = ap.parse_args()
    if args.hook:
        sys.exit(run_hook())
    if args.check:
        sys.exit(run_check(args.check, args.tolerate_legacy_status, args.transition))
    ap.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
