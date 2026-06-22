#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SliceOps Layer B.1 — Layer 3 consistency validators (reference implementation).
# Determinism-over-Regeneration (B.2): a fixed deterministic script, written
# once and reused — NOT AI-regenerated per run. Same corpus -> same result.
#
# Vendor-agnostic pattern; this is a GitHub-Actions-friendly instance (exit
# code != 0 fails the job). Adopters bind --root and conventions to their layout.
#
# Usage:
#   python3 validators.py --root <corpus-root> [--checks all|<name,...>]
#
# Stdlib only (no third-party YAML dep) — minimal frontmatter parsing keeps the
# starter portable. Adopters may swap in a real YAML parser.

import argparse
import os
import re
import sys
from collections import defaultdict

FM = re.compile(r"^---\n(.*?)\n---", re.S)


def read_frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = FM.match(text)
    if not m:
        return {}, text
    fm, body = {}, text[m.end():]
    key = None
    for line in m.group(1).splitlines():
        if re.match(r"^\s*#", line) or not line.strip():
            continue
        kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if kv:
            key = kv.group(1)
            val = kv.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                items = [x.strip().strip("'\"") for x in val[1:-1].split(",")]
                fm[key] = [x for x in items if x]
            elif val:
                fm[key] = val.strip("'\"")
            else:
                fm[key] = []
        elif key and re.match(r"^\s*-\s+", line):
            fm.setdefault(key, [])
            if not isinstance(fm[key], list):
                fm[key] = []
            fm[key].append(re.sub(r"^\s*-\s+", "", line).strip().strip("'\""))
    return fm, body


def find_docs(root):
    for dirpath, _, files in os.walk(root):
        # Skip VCS + frozen lifecycle dirs: superseded/deprecated DECs and the
        # archive are immutable history — not live corpus, so not validated for
        # live consistency (they keep stale vocabulary + one-way refs by design).
        if any(s in dirpath for s in ("/.git", "/99-archive", "/archive",
                                      "/superseded", "/deprecated")):
            continue
        for f in files:
            if f.endswith(".md") and f != "README.md":
                yield os.path.join(dirpath, f)


def doc_id(path):
    return os.path.splitext(os.path.basename(path))[0]


def check_frontmatter_schema(docs, entity_key="entity"):
    req = ["conflicts-with", "related-decs", "topics",
           "vocabulary-changes", "consistency-check"]
    errs = []
    for p, (fm, _) in docs.items():
        if fm.get(entity_key) != "DecisionRecord":
            continue
        for k in req:
            if k not in fm:
                errs.append(f"{doc_id(p)}: missing Layer 1 field '{k}'")
    return errs


def check_no_orphan(docs, entity_key="entity"):
    errs = []
    for p, (fm, body) in docs.items():
        if fm.get(entity_key) != "DecisionRecord":
            continue
        if not fm.get("related-decs") and not fm.get("topics"):
            if "isolation-justified" not in body:
                errs.append(f"{doc_id(p)}: orphan DEC (no related-decs, no "
                            f"topics) without 'isolation-justified' marker")
    return errs


def check_bidirectional(docs, entity_key="entity"):
    # `related-decs` declares a *topically-adjacent* relation between two
    # DecisionRecords — a symmetric relation, so it must be reciprocated. The
    # check applies ONLY when BOTH ends are DecisionRecords present in the live
    # corpus: a non-DR source (InsightRecord/LearningPattern/OutcomeRecord/etc.)
    # references decisions one-way by design (the DR tracks it via a separate
    # cognitive-link field, not `related-decs`), and a target that is frozen
    # (superseded/deprecated — excluded by find_docs) or external is not ours to
    # reciprocate. This is the calibrated convention, not a suppression.
    by_id = {doc_id(p): fm for p, (fm, _) in docs.items()}

    def is_dr(did):
        return by_id.get(did, {}).get(entity_key) == "DecisionRecord"

    errs = []
    for did, fm in by_id.items():
        if fm.get(entity_key) != "DecisionRecord":
            continue
        for ref in fm.get("related-decs", []):
            rid = os.path.splitext(os.path.basename(ref))[0]
            if not is_dr(rid):
                continue
            back = [os.path.splitext(os.path.basename(x))[0]
                    for x in by_id[rid].get("related-decs", [])]
            if did not in back:
                errs.append(f"{did} -> {rid} not reciprocated")
    return errs


def check_topic_tags(docs, taxonomy_path):
    if not taxonomy_path or not os.path.exists(taxonomy_path):
        return ["topic-tags: taxonomy file not found (skipped — configure path)"]
    with open(taxonomy_path, encoding="utf-8") as fh:
        canon = set(re.findall(r"^###\s+([a-z0-9-]+)", fh.read(), re.M))
    errs = []
    for p, (fm, _) in docs.items():
        for t in fm.get("topics", []):
            if t not in canon:
                errs.append(f"{doc_id(p)}: topic '{t}' not in taxonomy")
    return errs


def check_counter_atomicity(root):
    # Counter collisions apply to COUNTER-based artifacts (INS-NNN, LP-NNN,
    # HANDOFF-NNN, DEC-NNN, SL-NNN). DATE-based slugs (DR-/CF-YYYY-MM-DD-...)
    # carry no counter — their uniqueness is the date+slug — so the year must
    # not be mis-read as a counter and false-positive every same-year file.
    seen = defaultdict(list)
    for dirpath, _, files in os.walk(root):
        if "/.git" in dirpath:
            continue
        for f in files:
            if re.match(r"^[A-Za-z]+-\d{4}-\d{2}-\d{2}-", f):
                continue  # date-based naming, no counter to collide
            m = re.match(r"^([A-Z]+)-0*(\d+)(?:[-.]|$)", f)
            if m:
                seen[(m.group(1), m.group(2))].append(os.path.join(dirpath, f))
    errs = [f"counter collision {pfx}-{num}: {paths}"
            for (pfx, num), paths in seen.items() if len(paths) > 1]
    return errs


PRINCIPLE_RE = re.compile(r"^##\s+P(\d+)\s+—", re.M)
ENTITY_FILE_RE = re.compile(r"^(\d+)-[a-z0-9-]+\.md$")
# Count CLAIMS only: the phrase "N canonical principles" or the full-set range
# P1-P12. Band sub-ranges (P1-P3, P4-P10, ...) are NOT count claims — the
# full-set alternative anchors on P12 so sub-ranges do not false-positive.
COUNT_PRINCIPLE_RE = re.compile(
    r"\b(\d+)\s+canonical\s+principles?\b|\bP1\s*[-–]\s*P(12)\b", re.I
)
COUNT_ENTITY_RE = re.compile(
    # Only the plural form or a quantified specific-noun form is canonical
    # count language (e.g., "13 entities", "13 cognitive entities",
    # "13 entity specs", "13 entity types", "13 entity catalog").
    # Avoids matching "Layer B.1 Cognitive Entity" (a title — the "1" comes
    # from "B.1" and "Entity" is the singular categorical, not a count).
    r"(?<![.\w])(\d+)\s+(?:canonical\s+)?(?:cognitive\s+)?"
    r"(?:entities\b|entity\s+(?:specs|types|catalog))",
    re.I,
)
BAND_UNIT_BAD_RE = re.compile(
    # Only flag a *declarative* claim that token-band is measured in
    # total-with-cache (the anti-pattern). Negation forms like
    # "Token-band ... NOT total-with-cache" (legitimate clarification)
    # are NOT a claim.
    r"token[-\s]band\b[^.\n]{0,80}\b(?:in|as|=|equals?|measured\s+(?:in|as))\s+"
    r"total[-\s]with[-\s]cache\b",
    re.I,
)
LLM_ENDPOINT_RE = re.compile(
    r"api\.anthropic\.com|api\.openai\.com|generativelanguage\.googleapis\.com"
    r"|bedrock[-.\w]*\binvoke|\b(claude|gpt-?\d|gemini|sonnet|haiku|opus)\b",
    re.I,
)


def check_principle_count_coherence(root):
    """Count P-NN headings in principles.md, then compare against literals
    elsewhere in the spec. The canonical count is what principles.md *is*;
    every literal that disagrees is drift (the denormalized count drift
    failure mode formalized in the spec)."""
    principles_md = os.path.join(root, "spec", "v1.0.0", "principles.md")
    if not os.path.exists(principles_md):
        return []  # nothing canonical to compare against
    with open(principles_md, encoding="utf-8") as fh:
        text = fh.read()
    nums = [int(n) for n in PRINCIPLE_RE.findall(text)]
    if not nums:
        return ["principle-count-coherence: principles.md has no P-NN headings"]
    canonical = max(nums)
    errs = []
    for p in find_docs(root):
        if p == principles_md:
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                body = fh.read()
        except OSError:
            continue
        for m in COUNT_PRINCIPLE_RE.finditer(body):
            literal = int(next(g for g in m.groups() if g))
            if literal != canonical:
                line = body[: m.start()].count("\n") + 1
                rel = os.path.relpath(p, root)
                errs.append(
                    f"{rel}:{line}: literal '{m.group(0)}' "
                    f"disagrees with canonical {canonical}"
                )
    return errs


def check_entity_count_coherence(root):
    """Count NN-*.md files in reference/entity-catalog, then compare against
    literals 'N entities' / 'N cognitive entities' / 'N-entity' elsewhere."""
    cat_dir = os.path.join(root, "reference", "entity-catalog")
    if not os.path.isdir(cat_dir):
        return []
    canonical = sum(
        1 for f in os.listdir(cat_dir) if ENTITY_FILE_RE.match(f)
    )
    if canonical == 0:
        return []
    errs = []
    for p in find_docs(root):
        try:
            with open(p, encoding="utf-8") as fh:
                body = fh.read()
        except OSError:
            continue
        for m in COUNT_ENTITY_RE.finditer(body):
            literal = int(next(g for g in m.groups() if g))
            if literal != canonical:
                line = body[: m.start()].count("\n") + 1
                rel = os.path.relpath(p, root)
                errs.append(
                    f"{rel}:{line}: literal '{m.group(0)}' "
                    f"disagrees with canonical {canonical}"
                )
    return errs


def check_band_unit(root):
    """Token-band must be in billed-equivalent, NOT total-with-cache."""
    errs = []
    for p in find_docs(root):
        try:
            with open(p, encoding="utf-8") as fh:
                body = fh.read()
        except OSError:
            continue
        lines = body.splitlines()
        for m in BAND_UNIT_BAD_RE.finditer(body):
            line = body[: m.start()].count("\n") + 1
            # Skip when the line documents the anti-pattern (corrective markers)
            # rather than committing it — e.g. "... NOT total-with-cache;
            # the canonical unit is billed-equivalent".
            ctx = lines[line - 1].lower() if line - 1 < len(lines) else ""
            if any(k in ctx for k in ("billed-equivalent", "inflates",
                                      "canonical unit", "not total",
                                      "instead of", "anti-pattern")):
                continue
            rel = os.path.relpath(p, root)
            errs.append(
                f"{rel}:{line}: token-band described as 'total-with-cache' "
                f"(canonical unit is billed-equivalent)"
            )
    return errs


def iter_workflows(root):
    for dirpath, _, files in os.walk(root):
        if ".github/workflows" in dirpath:
            for f in files:
                if f.endswith(".yml") or f.endswith(".yaml"):
                    yield os.path.join(dirpath, f)
        for f in files:
            if f.endswith(".yml") and "workflow" in f.lower():
                yield os.path.join(dirpath, f)


def check_llm_ci_cost(root):
    """R-LLM-CI-COST — workflows calling a paid-LLM endpoint must:
      (1) have a concurrency cancel-in-progress block,
      (2) NOT trigger on `synchronize` (without an exception comment),
      (3) draft gate end green-not-skipped (the heuristic: no top-level
          `if: ... draft == false` that would skip the whole job — a step-
          level gate setting an output is the right shape)."""
    errs = []
    seen = set()
    for p in iter_workflows(root):
        if p in seen:
            continue
        seen.add(p)
        try:
            with open(p, encoding="utf-8") as fh:
                body = fh.read()
        except OSError:
            continue
        if not LLM_ENDPOINT_RE.search(body):
            continue
        rel = os.path.relpath(p, root)
        if "cancel-in-progress: true" not in body:
            errs.append(f"{rel}: paid-LLM workflow missing "
                        f"`concurrency: cancel-in-progress: true`")
        if "synchronize" in body and "synchronize-allowed" not in body:
            errs.append(f"{rel}: `synchronize` trigger on paid-LLM workflow "
                        f"without `# synchronize-allowed: <ref>` exception")
        # Heuristic: encourage step-level draft gating (skip output feeding if guards)
        if ("draft == false" in body or "draft: false" in body) \
                and "skip=true" not in body:
            errs.append(f"{rel}: top-level draft skip risks `skipped` "
                        f"required-check (use a step-level gate that emits "
                        f"`skip=true` so the job exits green)")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--checks", default="all")
    ap.add_argument("--topic-taxonomy", default="")
    # The portable canonical entity key is `entity`. A runtime may instantiate
    # entities under a mapped key (Layer C.1) — e.g. `--entity-key datta_entity`
    # — without the vendor-neutral spec prescribing that key.
    ap.add_argument("--entity-key", default="entity")
    args = ap.parse_args()

    docs = {p: read_frontmatter(p) for p in find_docs(args.root)}
    all_checks = {
        # Phase 2
        "frontmatter-schema": lambda: check_frontmatter_schema(docs, args.entity_key),
        "no-orphan-decs": lambda: check_no_orphan(docs, args.entity_key),
        "cross-references-bidirectional": lambda: check_bidirectional(docs, args.entity_key),
        "topic-tags": lambda: check_topic_tags(docs, args.topic_taxonomy),
        "counter-atomicity": lambda: check_counter_atomicity(args.root),
        # Phase 2.5
        "principle-count-coherence": lambda: check_principle_count_coherence(args.root),
        "entity-count-coherence": lambda: check_entity_count_coherence(args.root),
        "band-unit": lambda: check_band_unit(args.root),
        "llm-ci-cost": lambda: check_llm_ci_cost(args.root),
    }
    selected = (all_checks if args.checks == "all"
                else {k: all_checks[k] for k in args.checks.split(",")
                      if k in all_checks})

    failed = False
    for name, fn in selected.items():
        errs = fn()
        if errs:
            failed = True
            print(f"::error::[{name}] {len(errs)} issue(s):")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"[{name}] PASS")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
