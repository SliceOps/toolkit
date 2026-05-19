#!/usr/bin/env python3
# SliceOps Capa B.1 — Layer 3 consistency validators (reference implementation).
# Determinism-over-Regeneration (B.2): a fixed deterministic script, written
# once and reused — NOT AI-regenerated per run. Same corpus -> same result.
#
# Vendor-agnostic pattern; this is a GitHub-Actions-friendly instance (exit
# code != 0 fails the job). Adopters bind --root + conventions to their layout.
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
        if "/.git" in dirpath or "/99-archive" in dirpath:
            continue
        for f in files:
            if f.endswith(".md") and f != "README.md":
                yield os.path.join(dirpath, f)


def doc_id(path):
    return os.path.splitext(os.path.basename(path))[0]


def check_frontmatter_schema(docs):
    req = ["conflicts-with", "related-decs", "topics",
           "vocabulary-changes", "consistency-check"]
    errs = []
    for p, (fm, _) in docs.items():
        if fm.get("entity") != "DecisionRecord":
            continue
        for k in req:
            if k not in fm:
                errs.append(f"{doc_id(p)}: missing Layer 1 field '{k}'")
    return errs


def check_no_orphan(docs):
    errs = []
    for p, (fm, body) in docs.items():
        if fm.get("entity") != "DecisionRecord":
            continue
        if not fm.get("related-decs") and not fm.get("topics"):
            if "isolation-justified" not in body:
                errs.append(f"{doc_id(p)}: orphan DEC (no related-decs, no "
                            f"topics) without 'isolation-justified' marker")
    return errs


def check_bidirectional(docs):
    by_id = {doc_id(p): fm for p, (fm, _) in docs.items()}
    errs = []
    for did, fm in by_id.items():
        for ref in fm.get("related-decs", []):
            rid = os.path.splitext(os.path.basename(ref))[0]
            if rid in by_id:
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
    seen = defaultdict(list)
    for dirpath, _, files in os.walk(root):
        if "/.git" in dirpath:
            continue
        for f in files:
            m = re.match(r"^([A-Z]+)-(\d+)", f)
            if m:
                seen[(m.group(1), m.group(2))].append(os.path.join(dirpath, f))
    errs = [f"counter collision {pfx}-{num}: {paths}"
            for (pfx, num), paths in seen.items() if len(paths) > 1]
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--checks", default="all")
    ap.add_argument("--topic-taxonomy", default="")
    args = ap.parse_args()

    docs = {p: read_frontmatter(p) for p in find_docs(args.root)}
    all_checks = {
        "frontmatter-schema": lambda: check_frontmatter_schema(docs),
        "no-orphan-decs": lambda: check_no_orphan(docs),
        "cross-references-bidirectional": lambda: check_bidirectional(docs),
        "topic-tags": lambda: check_topic_tags(docs, args.topic_taxonomy),
        "counter-atomicity": lambda: check_counter_atomicity(args.root),
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
