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
# Stdlib only by default. If PyYAML is importable it is used for robust
# frontmatter + workflow parsing; otherwise a minimal stdlib parser handles the
# documented subset (see read_frontmatter). If jsonschema is importable the
# evidence-schema check runs full Draft 2020-12 validation; otherwise a
# documented stdlib subset applies (see _validate_evidence_stdlib). No
# dependency is REQUIRED.

import argparse
import json
import os
import re
import sys
from collections import defaultdict

try:  # optional: robust YAML when present, stdlib fallback otherwise
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None

try:  # optional: full Draft 2020-12 evidence validation when present,
    #           documented stdlib-subset fallback otherwise (same policy as PyYAML)
    import jsonschema as _jsonschema
except ImportError:  # pragma: no cover
    _jsonschema = None

FM = re.compile(r"^---\n(.*?)\n---", re.S)


def _norm_parts(path):
    """Path segments, OS-agnostic (os.walk yields '\\' on Windows, '/' elsewhere)."""
    return set(os.path.normpath(path).split(os.sep))


# Frozen lifecycle dirs: immutable history, not live corpus (excluded everywhere).
# Since spec v1.2.0 decisions/ folders are FLAT and the DEC-D- prefix carries the
# frozen (deprecated/superseded) state — the dir names remain excluded for
# pre-v1.2.0 corpora; DEC-D- files are the flat-layout equivalent (see find_docs).
_SKIP_DIRS = {".git", "99-archive", "archive", "superseded", "deprecated"}
_FROZEN_FILE = re.compile(r"^DEC-D-")   # v1.2.0 flat-layout frozen records
_WF_MARKER = os.path.join(".github", "workflows")


def read_frontmatter(path):
    """Parse YAML frontmatter into (dict, body).

    Uses PyYAML when importable. The stdlib fallback supports the documented
    subset used across SliceOps artifacts: `key: scalar`, inline `key: [a, b]`,
    block lists (`- item` under a key), `#` comments and trailing inline
    comments. It does NOT handle nested maps, multi-line block scalars (`|`/`>`),
    or inline `{}` maps — install PyYAML, or keep frontmatter within the subset,
    if you need those.
    """
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = FM.match(text)
    if not m:
        return {}, text
    fm_text, body = m.group(1), text[m.end():]

    if _yaml is not None:
        try:
            data = _yaml.safe_load(fm_text)
            if isinstance(data, dict):
                return {k: ([] if v is None else v) for k, v in data.items()}, body
        except _yaml.YAMLError:
            pass  # fall through to the minimal parser

    fm, key = {}, None
    for line in fm_text.splitlines():
        if re.match(r"^\s*#", line) or not line.strip():
            continue
        kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if kv:
            key = kv.group(1)
            val = kv.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                items = [x.strip().strip("'\"") for x in val[1:-1].split(",")]
                fm[key] = [x for x in items if x]
            elif val and not val.startswith("#"):
                fm[key] = val.split(" #")[0].strip().strip("'\"")
            else:
                fm[key] = []
        elif key and re.match(r"^\s*-\s+", line):
            fm.setdefault(key, [])
            if not isinstance(fm[key], list):
                fm[key] = []
            item = re.sub(r"^\s*-\s+", "", line).split(" #")[0].strip()
            fm[key].append(item.strip("'\""))
    return fm, body


_VERSION_DIR = re.compile(r"^v\d+\.\d+\.\d+$")


def _current_version_dir(root):
    """Frozen published spec versions (spec/vX.Y.Z) are immutable history and
    carry their own era's literals — only the CURRENT version (the spec/latest
    symlink target) is live corpus for coherence checks. Returns None when the
    corpus has no versioned spec (non-spec corpora: nothing is skipped)."""
    try:
        return os.path.basename(os.readlink(os.path.join(root, "spec", "latest")))
    except OSError:
        return None


def find_docs(root):
    current = _current_version_dir(root)
    for dirpath, _, files in os.walk(root):
        # Skip VCS + frozen lifecycle dirs (immutable history, not live corpus).
        # OS-agnostic part match — os.walk yields '\\' on Windows.
        parts = _norm_parts(dirpath)
        if parts & _SKIP_DIRS:
            continue
        if any(_VERSION_DIR.match(p) and p != current for p in parts):
            continue  # frozen published version dir (kept for audit, own-era literals)
        for f in files:
            if f.endswith(".md") and f != "README.md" and not _FROZEN_FILE.match(f):
                yield os.path.join(dirpath, f)


def doc_id(path):
    return os.path.splitext(os.path.basename(path))[0]


def check_frontmatter_schema(docs, entity_key="entity"):
    req = ["conflicts-with", "related-decs", "topics",
           "vocabulary-changes", "consistency-check"]
    # P3 author≠approver (spec v1.1.0, DEC-2026-07-02-author-approver-separation;
    # status vocabulary homologated to 'approved' in spec v1.2.0 — legacy
    # 'ratified' still recognized on read): DECs approved on/after this date must
    # record the approving human. Earlier DECs are back-filled fix-on-touch (P12),
    # never bulk-required.
    approver_cutoff = "2026-07-03"
    errs = []
    for p, (fm, _) in docs.items():
        if fm.get(entity_key) != "DecisionRecord":
            continue
        for k in req:
            if k not in fm:
                errs.append(f"{doc_id(p)}: missing Layer 1 field '{k}'")
        # str() normalizes PyYAML date objects to ISO form, so the lexical
        # comparison holds in both parser modes; missing 'created' is exempt.
        status = str(fm.get("status", "")).strip()
        if (status in ("approved", "ratified")
                and str(fm.get("created", "")).strip() >= approver_cutoff
                and not str(fm.get("approver", "") or "").strip()):
            errs.append(
                f"{doc_id(p)}: status '{status}' with no 'approver' recorded "
                f"(P3 author≠approver — required for DECs created "
                f"on/after {approver_cutoff})")
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
    # Not configured → genuinely skip (return None; main reports SKIPPED, green).
    if not taxonomy_path:
        return None
    # Configured but missing → a real misconfiguration, not a skip.
    if not os.path.exists(taxonomy_path):
        return [f"topic-tags: configured taxonomy not found: {taxonomy_path}"]
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
        if ".git" in _norm_parts(dirpath):
            continue
        for f in files:
            # date-based naming (incl. v1.2.0 lifecycle infix DEC-P-/DEC-D-):
            # no counter to collide — uniqueness is date+slug.
            if re.match(r"^[A-Za-z]+(?:-[PD])?-\d{4}-\d{2}-\d{2}-", f):
                continue
            # counter-based; the DEC-P-/DEC-D- lifecycle infix normalizes to the
            # base prefix so an id is never reused across lifecycle states
            # (a new DEC-041 collides with an existing DEC-D-041).
            m = re.match(r"^([A-Z]+)(?:-[PD])?-0*(\d+)(?:[-.]|$)", f)
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


def _latest_principles(root):
    """Resolve principles.md at the HIGHEST spec version: prefer spec/latest/
    (symlink), else the highest-semver spec/vX.Y.Z/, else retained v1.0.0.
    (The former hardcoded v1.0.0 was itself the version-drift this checker
    exists to prevent — it would read a stale file once the count changes.)"""
    latest = os.path.join(root, "spec", "latest", "principles.md")
    if os.path.exists(latest):
        return latest
    specdir, best = os.path.join(root, "spec"), None
    if os.path.isdir(specdir):
        for d in os.listdir(specdir):
            m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", d)
            p = os.path.join(specdir, d, "principles.md")
            if m and os.path.exists(p):
                key = tuple(int(x) for x in m.groups())
                if best is None or key > best[0]:
                    best = (key, p)
    if best:
        return best[1]
    legacy = os.path.join(root, "spec", "v1.0.0", "principles.md")
    return legacy if os.path.exists(legacy) else None


def check_principle_count_coherence(root):
    """Count P-NN headings in principles.md, then compare against literals
    elsewhere in the spec. The canonical count is what principles.md *is*;
    every literal that disagrees is drift (the denormalized count drift
    failure mode formalized in the spec)."""
    principles_md = _latest_principles(root)
    if not principles_md:
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
    seen = set()
    for dirpath, _, files in os.walk(root):
        in_wf_dir = _WF_MARKER in os.path.normpath(dirpath)
        for f in files:
            if not (f.endswith(".yml") or f.endswith(".yaml")):
                continue
            if in_wf_dir or "workflow" in f.lower():
                p = os.path.join(dirpath, f)
                if p not in seen:
                    seen.add(p)
                    yield p


def _strip_yaml_comments(text):
    """Drop `#` comments not inside quotes — so comment/doc text never trips the
    content heuristics below."""
    out = []
    for line in text.splitlines():
        in_s = in_d = False
        cut = None
        for i, ch in enumerate(line):
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            elif ch == "#" and not in_s and not in_d:
                cut = i
                break
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def check_llm_ci_cost(root):
    """R-LLM-CI-COST — workflows calling a paid-LLM endpoint must:
      (1) have a concurrency cancel-in-progress block,
      (2) NOT trigger on `synchronize` (without an exception comment),
      (3) draft gate end green-not-skipped (the heuristic: no top-level
          `if: ... draft == false` that would skip the whole job — a step-
          level gate setting an output is the right shape)."""
    errs = []
    for p in iter_workflows(root):
        try:
            with open(p, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError:
            continue
        code = _strip_yaml_comments(raw)        # ignore comments/docs
        if not LLM_ENDPOINT_RE.search(code):
            continue
        rel = os.path.relpath(p, root)

        data = None
        if _yaml is not None:
            try:
                data = _yaml.safe_load(raw)
            except _yaml.YAMLError:
                data = None
        struct = isinstance(data, dict)

        # (1) concurrency cancel-in-progress — structural when possible
        if struct:
            conc = data.get("concurrency")
            cancel = isinstance(conc, dict) and conc.get("cancel-in-progress") is True
        else:
            cancel = "cancel-in-progress: true" in code
        if not cancel:
            errs.append(f"{rel}: paid-LLM workflow missing "
                        f"`concurrency.cancel-in-progress: true`")

        # (2) synchronize trigger — note YAML parses the `on:` key as boolean True
        if struct:
            on = data.get("on", data.get(True))
            pr = on.get("pull_request") if isinstance(on, dict) else None
            types = pr.get("types") or [] if isinstance(pr, dict) else []
            has_sync = "synchronize" in types
        else:
            has_sync = "synchronize" in code
        if has_sync and "synchronize-allowed" not in raw:
            errs.append(f"{rel}: `synchronize` trigger on paid-LLM workflow "
                        f"without a `# synchronize-allowed: <ref>` exception")

        # (3) draft gating — heuristic (job/step shapes vary too much to assert
        # structurally); flag a job-level draft skip that would yield a `skipped`
        # required check instead of a green step-level gate.
        if ("draft == false" in code or "draft: false" in code) \
                and "skip=true" not in code:
            errs.append(f"{rel}: job-level draft skip risks a `skipped` required "
                        f"check — use a step-level gate emitting `skip=true` so "
                        f"the job still exits green")
    return errs


# ---------------------------------------------------------------------------
# Check #10 — evidence-schema (evidence.v1, canonical record format)
# Spec: sliceops-spec reference/evidence/evidence-v1.md +
# reference/evidence/evidence.v1.schema.json (ratified
# DR-2026-07-02-evidence-v1-canonical-schema). The schema vendored under
# schemas/ MUST stay byte-identical to the spec canonical — the toolkit CI
# byte-compares it against the raw spec-main URL on every PR (drift fails).
# ---------------------------------------------------------------------------

# Discovery glob: ONLY files ending '.evidence.json' or '.evidence.v1.json'
# under --root are evidence records. Any filename containing '.example.' is a
# golden fixture, NEVER a record — the spec repo ships three deliberately
# INVALID examples (*.evidence.v1.example.json) that must not break its CI.
_EVIDENCE_SUFFIXES = (".evidence.json", ".evidence.v1.json")
_EVIDENCE_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "schemas", "evidence.v1.schema.json",
)


def find_evidence_records(root):
    for dirpath, _, files in os.walk(root):
        if _norm_parts(dirpath) & _SKIP_DIRS:
            continue
        for f in files:
            if ".example." in f:
                continue  # golden fixture (possibly deliberately invalid)
            if f.endswith(_EVIDENCE_SUFFIXES):
                yield os.path.join(dirpath, f)


def _validate_evidence_stdlib(rec, schema):
    """Documented STDLIB SUBSET of evidence.v1 validation (jsonschema absent).

    Covers: required top-level fields; the schemaVersion const; enum
    membership (status, actor.type, check category/status/severity,
    redaction.status); pattern checks (evidenceId, operationType,
    provenance.sliceId + commitSha, decisionRefs, artifact/trace hashes —
    exactly 64|96|128 lowercase hex — and reverse-DNS extensions keys);
    additionalProperties rejection at the top level; required sub-fields of
    actor/artifacts/checks/traceRefs/redaction; and the slice-merge P6
    completeness rule (functional+quality+security check categories, >=1
    decisionRefs, provenance.sliceId+commitSha).

    Does NOT cover: format annotations (RFC 3339 date-time), string
    length bounds, nested additionalProperties, or other deep conditional
    subtleties — install jsonschema for full Draft 2020-12 validation.

    Enums, patterns and required lists are read from the vendored schema at
    run time, never duplicated here (the denormalized-copy drift this toolkit
    exists to catch).
    """
    errs = []
    props, defs = schema["properties"], schema["$defs"]

    def enum_ok(value, allowed, label):
        if value not in allowed:
            errs.append(f"{label}: {value!r} not one of {allowed}")

    def pattern_ok(value, pat, label):
        if not isinstance(value, str) or not re.fullmatch(pat, value):
            errs.append(f"{label}: {value!r} does not match '{pat}'")

    for k in schema["required"]:
        if k not in rec:
            errs.append(f"missing required field '{k}'")
    for k in rec:
        if k not in props:
            errs.append(f"unknown top-level field '{k}' (additionalProperties:"
                        f" false — vendor/adopter data goes under 'extensions')")

    if "schemaVersion" in rec and rec["schemaVersion"] != props["schemaVersion"]["const"]:
        errs.append(f"schemaVersion: {rec['schemaVersion']!r} != "
                    f"'{props['schemaVersion']['const']}'")
    if "evidenceId" in rec:
        pattern_ok(rec["evidenceId"], props["evidenceId"]["pattern"], "evidenceId")
    if "operationType" in rec:
        pattern_ok(rec["operationType"], props["operationType"]["pattern"],
                   "operationType")
    if "status" in rec:
        enum_ok(rec["status"], props["status"]["enum"], "status")

    actor = rec.get("actor")
    if isinstance(actor, dict):
        for rk in props["actor"]["required"]:
            if rk not in actor:
                errs.append(f"actor: missing required field '{rk}'")
        if "type" in actor:
            enum_ok(actor["type"], props["actor"]["properties"]["type"]["enum"],
                    "actor.type")
    elif "actor" in rec:
        errs.append("actor: must be an object")

    art_def = defs["artifact"]
    for i, a in enumerate(rec.get("artifacts") or []):
        if not isinstance(a, dict):
            errs.append(f"artifacts[{i}]: must be an object")
            continue
        for rk in art_def["required"]:
            if rk not in a:
                errs.append(f"artifacts[{i}]: missing required field '{rk}'")
        if "hash" in a:
            pattern_ok(a["hash"], art_def["properties"]["hash"]["pattern"],
                       f"artifacts[{i}].hash")

    chk_def = defs["check"]
    categories = set()
    for i, c in enumerate(rec.get("checks") or []):
        if not isinstance(c, dict):
            errs.append(f"checks[{i}]: must be an object")
            continue
        for rk in chk_def["required"]:
            if rk not in c:
                errs.append(f"checks[{i}]: missing required field '{rk}'")
        for field in ("category", "status", "severity"):
            if field in c:
                enum_ok(c[field], chk_def["properties"][field]["enum"],
                        f"checks[{i}].{field}")
        if c.get("category") in chk_def["properties"]["category"]["enum"]:
            categories.add(c["category"])

    trace_def = defs["traceRef"]
    for i, t in enumerate(rec.get("traceRefs") or []):
        if not isinstance(t, dict):
            errs.append(f"traceRefs[{i}]: must be an object")
            continue
        for rk in trace_def["required"]:
            if rk not in t:
                errs.append(f"traceRefs[{i}]: missing required field '{rk}'")
        if "traceHash" in t:
            pattern_ok(t["traceHash"],
                       trace_def["properties"]["traceHash"]["pattern"],
                       f"traceRefs[{i}].traceHash")

    prov = rec.get("provenance")
    if isinstance(prov, dict):
        if "sliceId" in prov:
            pattern_ok(prov["sliceId"], defs["sliceId"]["pattern"],
                       "provenance.sliceId")
        if "commitSha" in prov:
            pattern_ok(prov["commitSha"],
                       props["provenance"]["properties"]["commitSha"]["pattern"],
                       "provenance.commitSha")
    elif "provenance" in rec:
        errs.append("provenance: must be an object")

    for i, d in enumerate(rec.get("decisionRefs") or []):
        pattern_ok(d, defs["decisionRef"]["pattern"], f"decisionRefs[{i}]")

    red = rec.get("redaction")
    if isinstance(red, dict):
        for rk in props["redaction"]["required"]:
            if rk not in red:
                errs.append(f"redaction: missing required field '{rk}'")
        if "status" in red:
            enum_ok(red["status"],
                    props["redaction"]["properties"]["status"]["enum"],
                    "redaction.status")
    elif "redaction" in rec:
        errs.append("redaction: must be an object")

    ext = rec.get("extensions")
    if isinstance(ext, dict):
        key_pat = props["extensions"]["propertyNames"]["pattern"]
        for k in ext:
            pattern_ok(k, key_pat, "extensions key")
    elif "extensions" in rec:
        errs.append("extensions: must be an object")

    # Slice-merge P6 completeness (the schema's allOf/if-then conditional,
    # restated here — the one rule the fallback hardcodes rather than reads).
    if rec.get("operationType") == "slice-merge":
        if not isinstance(prov, dict) or "sliceId" not in prov \
                or "commitSha" not in prov:
            errs.append("slice-merge: provenance with sliceId + commitSha "
                        "is required (P6 provenance category)")
        if not rec.get("decisionRefs"):
            errs.append("slice-merge: >=1 decisionRefs entry is required "
                        "(P6 decision category)")
        missing = {"functional", "quality", "security"} - categories
        if missing:
            errs.append(f"slice-merge: checks missing categories "
                        f"{sorted(missing)} (P6/P7 completeness)")
    return errs


def check_evidence_schema(root):
    """evidence-schema — every evidence.v1 record validates against the
    canonical schema (vendored under schemas/, byte-synced to the spec).

    Skip semantics (same philosophy as topic-tags): a corpus with ZERO
    evidence records genuinely skips (green) — corpora that have not adopted
    evidence.v1 yet must not fail. A vendored schema that is missing or
    unreadable is a hard error (misconfiguration, not a skip)."""
    records = sorted(find_evidence_records(root))
    if not records:
        return None  # no evidence records in corpus -> genuine skip (green)
    try:
        with open(_EVIDENCE_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
    except (OSError, ValueError) as e:
        return [f"vendored schema missing/unreadable "
                f"({_EVIDENCE_SCHEMA_PATH}): {e}"]
    errs = []
    for p in records:
        rel = os.path.relpath(p, root)
        try:
            with open(p, encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, ValueError) as e:
            errs.append(f"{rel}: invalid JSON ({e})")
            continue
        if not isinstance(rec, dict):
            errs.append(f"{rel}: top-level value must be a JSON object")
            continue
        if _jsonschema is not None:  # full Draft 2020-12
            validator = _jsonschema.Draft202012Validator(schema)
            for err in sorted(validator.iter_errors(rec),
                              key=lambda e: str(list(e.absolute_path))):
                loc = "/".join(str(x) for x in err.absolute_path) or "(top level)"
                errs.append(f"{rel}: {loc}: {err.message[:200]}")
        else:  # documented stdlib subset
            errs.extend(f"{rel}: {e}" for e in
                        _validate_evidence_stdlib(rec, schema))
    return errs


# A slice coordinate carrying a one-letter sub-slice suffix, in either grammar:
# SLC form (SLC0010b / SLC0010bSECAPIBL02) or the read-tolerated legacy dotted
# form (BL-02.SEC-API.SL-010b). Group 1 / group 2 capture the suffix if present.
_SUBSLICE_SLC_RE = re.compile(
    r"\bSLC\d{4,}([a-z])?(?:SEC(?:\d{2,}|[A-Z]{2,}))?(?:BL\d{2,})?\b")
_SUBSLICE_DOTTED_RE = re.compile(
    r"\bBL-?\d+\.SEC-?(?:\d+|[A-Z]+)\.SL-?\d+([a-z])?\b")


def check_subslice_rate(root):
    """Observability, NOT a gate (P9 — announced, not cut). Reports the
    sub-slice rate: the share of distinct slice coordinates carrying a
    one-letter sub-slice suffix. Per DEC-0014_4 the rate is a health signal
    for planning altitude — a low rate concentrated in inherently-emergent
    work (tooling/cleanup/meta) is healthy; a rising rate, or one spreading
    into the plannable core of the build, says slices are being cut too
    coarse. Returns INFO lines (never error strings); the runner emits them
    as notices and never fails on them. Returns None when a corpus has no
    slice coordinates (nothing to report)."""
    slices = {}  # coordinate string -> has one-letter suffix (bool)
    for dirpath, _dirs, files in os.walk(root):
        if ".git" in _norm_parts(dirpath):
            continue
        for f in files:
            if not f.endswith((".md", ".txt")):
                continue
            try:
                with open(os.path.join(dirpath, f),
                          encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            for m in _SUBSLICE_SLC_RE.finditer(text):
                slices[m.group(0)] = bool(m.group(1))
            for m in _SUBSLICE_DOTTED_RE.finditer(text):
                slices[m.group(0)] = bool(m.group(1))
    total = len(slices)
    if total == 0:
        return None  # no slice coordinates — nothing to observe
    sub = sum(1 for has in slices.values() if has)
    rate = sub / total
    info = [f"sub-slice rate: {sub}/{total} = {rate * 100:.1f}% of distinct "
            f"slice coordinates carry a sub-slice suffix (DEC-0014_4)"]
    # A soft waterline, not a spec constant and not a failure: at/under it the
    # metric is informational; over it, prompt a look. Tune per corpus.
    if rate > 0.15:
        info.append(
            f"is the {rate * 100:.1f}% concentrated in emergent work "
            f"(tooling/cleanup/meta) or spreading into the plannable build? "
            f"the latter says plan finer (principles P4/P5, DEC-0014_4)")
    return info


# Reporters are observability-only: their output is emitted as notices and
# NEVER sets the failure flag (P9 — degradation announced, never a silent cut).
REPORTER_CHECKS = {"subslice-rate"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--checks", default="all")
    ap.add_argument("--topic-taxonomy", default="")
    # The portable canonical entity key is `entity`. A runtime may instantiate
    # entities under a mapped key (Layer C.1) — e.g. `--entity-key runtime_entity`
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
        # evidence.v1 (check #10, v0.2.0)
        "evidence-schema": lambda: check_evidence_schema(args.root),
        # observability reporter (v0.4.0, DEC-0014_4) — signal, never a gate
        "subslice-rate": lambda: check_subslice_rate(args.root),
    }
    selected = (all_checks if args.checks == "all"
                else {k: all_checks[k] for k in args.checks.split(",")
                      if k in all_checks})

    failed = False
    for name, fn in selected.items():
        result = fn()
        if result is None:                    # genuine skip (topic-tags unconfigured,
            # evidence-schema with zero records, or a reporter with no slices)
            print(f"[{name}] SKIPPED")
        elif name in REPORTER_CHECKS:         # observability — emit, never fail (P9)
            for line in result:
                print(f"::notice::[{name}] {line}")
        elif result:
            failed = True
            print(f"::error::[{name}] {len(result)} issue(s):")
            for e in result:
                print(f"  - {e}")
        else:
            print(f"[{name}] PASS")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
