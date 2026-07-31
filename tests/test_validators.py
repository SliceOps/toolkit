#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Regression tests for the SliceOps consistency validators.
#
# Per the 2026-06-19 dogfooding audit (§2, toolkit verdict): "a validator
# toolkit with no test of its validators." This suite pins the documented
# false-positive fixes so they cannot silently regress:
#   - date-based slugs must NOT trip counter-atomicity        (commit 883c391)
#   - principle-count must NOT trip on band sub-ranges        (commit f46f1c2)
#   - band-unit must NOT trip on the negation/clarifying form (commit e45c2a4)
#   - entity-count must NOT trip on the singular "Entity" title
# plus positive cases proving each check still catches the real defect.
#
# Stdlib only (unittest + tempfile), Python 3.9+ — no third-party deps, so it
# runs anywhere the validators themselves run.

import importlib.util
import os
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATORS = os.path.join(
    _HERE, "..", "templates", "consistency-validators", "validators.py"
)
_spec = importlib.util.spec_from_file_location("validators", _VALIDATORS)
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)


def _write(root, relpath, text):
    path = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class CounterAtomicity(unittest.TestCase):
    def test_date_slugs_do_not_collide(self):
        # Two same-year date-based DECs + a CF — uniqueness is date+slug, not a
        # counter. The "2026" must not be mis-read as a counter (commit 883c391).
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/DEC-2026-05-12-three-layer.md", "x")
            _write(d, "decisions/DEC-2026-06-15-license.md", "x")
            _write(d, "cf/CF-2026-05-14-glossary.md", "x")
            self.assertEqual(v.check_counter_atomicity(d), [])

    def test_lifecycle_infix_date_slugs_do_not_collide(self):
        # v1.2.0 flat layout: two same-date DEC-D- records must not be misread
        # as counter "2026" colliding (lifecycle infix in the date-skip).
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/DEC-D-2026-05-12-canonical-principles.md", "x")
            _write(d, "decisions/DEC-D-2026-05-12-spec-repo-structure.md", "x")
            self.assertEqual(v.check_counter_atomicity(d), [])

    def test_lifecycle_infix_counter_id_reuse_is_caught(self):
        # A new DEC-041 reusing the id held by a deprecated DEC-D-041 collides.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "10-decisions/DEC-D-041-old.md", "x")
            _write(d, "10-decisions/DEC-041-new.md", "x")
            errs = v.check_counter_atomicity(d)
            self.assertEqual(len(errs), 1)

    def test_real_counter_collision_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "insights/INS-001-a.md", "x")
            _write(d, "insights/INS-001-b.md", "x")
            errs = v.check_counter_atomicity(d)
            self.assertEqual(len(errs), 1)
            self.assertIn("INS", errs[0])


class SubsliceRate(unittest.TestCase):
    # DEC-0014_4: the sub-slice rate is an observability signal, never a gate.

    def test_no_slices_is_skip(self):
        # A corpus with no slice coordinates has nothing to observe → None (SKIP).
        with tempfile.TemporaryDirectory() as d:
            _write(d, "doc.md", "prose with no coordinates at all")
            self.assertIsNone(v.check_subslice_rate(d))

    def test_rate_counts_suffixed_over_total(self):
        # Three distinct coordinates, one carrying a sub-slice suffix → 1/3.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tracker.md",
                   "SLC0010 done. SLC0011 done. SLC0010b emerged mid-impl.")
            info = v.check_subslice_rate(d)
            self.assertIsNotNone(info)
            self.assertIn("1/3", info[0])
            self.assertIn("33.3%", info[0])

    def test_legacy_dotted_suffix_recognized(self):
        # The read-tolerated dotted form's [a-z] tail counts too.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tracker.md",
                   "BL-02.SEC-API.SL-010 and BL-02.SEC-API.SL-010b")
            info = v.check_subslice_rate(d)
            self.assertIn("1/2", info[0])

    def test_soft_waterline_note_over_threshold(self):
        # Over the 15% soft waterline, a prompt line is appended — but it is
        # still INFO (the runner never fails on a reporter).
        with tempfile.TemporaryDirectory() as d:
            _write(d, "tracker.md", "SLC0010 and SLC0010b")  # 1/2 = 50%
            info = v.check_subslice_rate(d)
            self.assertTrue(any("plan finer" in line for line in info))

    def test_reporter_registered_and_never_fails(self):
        # subslice-rate is registered as a reporter, not a hard check.
        self.assertIn("subslice-rate", v.REPORTER_CHECKS)


class PrincipleCountCoherence(unittest.TestCase):
    def _principles(self, n=12):
        return "\n".join("## P%d — Principle %d\n\nbody" % (i, i)
                         for i in range(1, n + 1))

    def test_band_subranges_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "spec/v1.0.0/principles.md", self._principles(12))
            # Band sub-ranges and the matching full-set range are legitimate.
            _write(d, "doc.md", "Bands group P1-P3, P4-P10 and the set P1-P12.")
            self.assertEqual(v.check_principle_count_coherence(d), [])

    def test_correct_count_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "spec/v1.0.0/principles.md", self._principles(12))
            _write(d, "doc.md", "There are 12 canonical principles.")
            self.assertEqual(v.check_principle_count_coherence(d), [])

    def test_wrong_count_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "spec/v1.0.0/principles.md", self._principles(12))
            _write(d, "doc.md", "There are 11 canonical principles.")
            errs = v.check_principle_count_coherence(d)
            self.assertEqual(len(errs), 1)
            self.assertIn("11", errs[0])


class EntityCountCoherence(unittest.TestCase):
    def _catalog(self, root, n=13):
        for i in range(1, n + 1):
            _write(root, "reference/entity-catalog/%02d-entity.md" % i, "x")

    def test_singular_title_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            self._catalog(d, 13)
            _write(d, "doc.md", "Layer B.1 Cognitive Entity is the category.")
            self.assertEqual(v.check_entity_count_coherence(d), [])

    def test_correct_count_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            self._catalog(d, 13)
            _write(d, "doc.md", "The catalog has 13 cognitive entities.")
            self.assertEqual(v.check_entity_count_coherence(d), [])

    def test_wrong_count_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            self._catalog(d, 13)
            _write(d, "doc.md", "The catalog has 12 entities.")
            errs = v.check_entity_count_coherence(d)
            self.assertEqual(len(errs), 1)
            self.assertIn("12", errs[0])


class BandUnit(unittest.TestCase):
    def test_clarifying_form_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "doc.md",
                   "Token-band measured in total-with-cache inflates it; "
                   "the canonical unit is billed-equivalent.")
            self.assertEqual(v.check_band_unit(d), [])

    def test_antipattern_claim_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "doc.md", "Token-band is measured in total-with-cache.")
            errs = v.check_band_unit(d)
            self.assertEqual(len(errs), 1)


class Frontmatter(unittest.TestCase):
    def test_list_and_comment_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "x.md",
                       "---\n# a comment\nentity: DecisionRecord\n"
                       "topics:\n  - alpha\n  - beta\n---\nBODY\n")
            fm, body = v.read_frontmatter(p)
            self.assertEqual(fm.get("entity"), "DecisionRecord")
            self.assertEqual(fm.get("topics"), ["alpha", "beta"])
            self.assertIn("BODY", body)

    def test_missing_layer1_fields_caught_for_decisionrecords(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "dec.md", "---\nentity: DecisionRecord\n---\nbody")
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            errs = v.check_frontmatter_schema(docs)
            # All 5 Layer-1 fields missing.
            self.assertEqual(len(errs), 5)

    _LAYER1 = ("conflicts-with: []\nrelated-decs: []\ntopics: [alpha]\n"
               "vocabulary-changes: []\nconsistency-check: ok\n")

    def _ratified(self, created, approver_line=""):
        return ("---\nentity: DecisionRecord\nstatus: ratified\n"
                f"created: {created}\n{approver_line}" + self._LAYER1 + "---\nbody")

    def test_ratified_after_cutoff_requires_approver(self):
        # P3 author≠approver (spec v1.1.0): ratified + created >= 2026-07-03
        # with no approver is an error.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "dec.md", self._ratified("2026-07-03"))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            errs = v.check_frontmatter_schema(docs)
            self.assertEqual(len(errs), 1)
            self.assertIn("approver", errs[0])

    def test_ratified_after_cutoff_with_approver_passes(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "dec.md",
                   self._ratified("2026-08-01", "approver: someone\n"))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            self.assertEqual(v.check_frontmatter_schema(docs), [])

    def test_approved_after_cutoff_requires_approver(self):
        # v1.2.0 homologated status: 'approved' triggers the same P3 gate.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "dec.md", self._ratified("2026-07-10").replace(
                "status: ratified", "status: approved"))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            errs = v.check_frontmatter_schema(docs)
            self.assertTrue(any("approver" in e for e in errs))

    def test_ratified_before_cutoff_is_exempt(self):
        # Legacy DECs are back-filled fix-on-touch, never bulk-required.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "dec.md", self._ratified("2026-07-02"))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            self.assertEqual(v.check_frontmatter_schema(docs), [])


def _dr(related, entity_key="entity"):
    body = "---\n%s: DecisionRecord\n" % entity_key
    if related:
        body += "related-decs:\n" + "".join("  - %s\n" % r for r in related)
    else:
        body += "related-decs: []\n"
    return body + "---\nbody"


class BidirectionalConvention(unittest.TestCase):
    def test_reciprocated_dr_pair_passes(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/DEC-A.md", _dr(["DEC-B"]))
            _write(d, "decisions/DEC-B.md", _dr(["DEC-A"]))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            self.assertEqual(v.check_bidirectional(docs), [])

    def test_one_way_dr_pair_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/DEC-A.md", _dr(["DEC-B"]))
            _write(d, "decisions/DEC-B.md", _dr([]))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            errs = v.check_bidirectional(docs)
            self.assertEqual(len(errs), 1)
            self.assertIn("DEC-A -> DEC-B", errs[0])

    def test_non_dr_source_is_one_way_ok(self):
        # An InsightRecord referencing a DR must NOT require the DR to reciprocate.
        with tempfile.TemporaryDirectory() as d:
            ins = "---\nentity: InsightRecord\nrelated-decs:\n  - DEC-A\n---\nbody"
            _write(d, "insights/INS-1.md", ins)
            _write(d, "decisions/DEC-A.md", _dr([]))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            self.assertEqual(v.check_bidirectional(docs), [])

    def test_frozen_target_is_skipped(self):
        # A live DR referencing a superseded DR: the frozen doc is excluded by
        # find_docs, so the edge is not enforced.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/DEC-A.md", _dr(["DEC-D-OLD"]))
            _write(d, "decisions/DEC-D-OLD.md", _dr([]))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            self.assertEqual(v.check_bidirectional(docs), [])

    def test_custom_entity_key(self):
        # Runtime-mapped entity key (e.g. runtime_entity) is honored.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/DEC-A.md", _dr(["DEC-B"], "runtime_entity"))
            _write(d, "decisions/DEC-B.md", _dr([], "runtime_entity"))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            # Default key 'entity' → sources unrecognized → no enforcement.
            self.assertEqual(v.check_bidirectional(docs), [])
            # Mapped key → the one-way pair is caught.
            errs = v.check_bidirectional(docs, "runtime_entity")
            self.assertEqual(len(errs), 1)


class PathPortability(unittest.TestCase):
    def test_norm_parts_membership(self):
        p = os.path.join("a", ".git", "b")
        self.assertIn(".git", v._norm_parts(p))

    def test_find_docs_skips_frozen_and_git(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/DEC-x.md", "x")
            _write(d, "decisions/superseded/legacy-old.md", "x")
            _write(d, ".git/hooks/note.md", "x")
            found = {os.path.basename(p) for p in v.find_docs(d)}
            self.assertEqual(found, {"DEC-x.md"})

    def test_iter_workflows_matches_dir_and_name(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, ".github/workflows/ci.yml", "x")
            _write(d, "templates/my-workflow.yml", "x")
            _write(d, "notes/plain.yml", "x")
            found = {os.path.basename(p) for p in v.iter_workflows(d)}
            self.assertEqual(found, {"ci.yml", "my-workflow.yml"})


class TopicTagsSemantics(unittest.TestCase):
    def test_unconfigured_is_skip_not_error(self):
        self.assertIsNone(v.check_topic_tags({}, ""))

    def test_configured_but_missing_is_error(self):
        errs = v.check_topic_tags({}, "/no/such/taxonomy.md")
        self.assertTrue(errs and "not found" in errs[0])

    def test_valid_taxonomy_flags_unknown_topic(self):
        with tempfile.TemporaryDirectory() as d:
            tax = _write(d, "topics.md", "### alpha\n### beta\n")
            docs = {"x.md": ({"topics": ["alpha", "zzz"]}, "")}
            errs = v.check_topic_tags(docs, tax)
            self.assertEqual(len(errs), 1)
            self.assertIn("zzz", errs[0])


class FrontmatterFallback(unittest.TestCase):
    def test_minimal_parser_subset(self):
        orig = v._yaml
        v._yaml = None  # force the stdlib fallback path
        try:
            with tempfile.TemporaryDirectory() as d:
                p = _write(d, "x.md",
                           "---\nentity: DecisionRecord  # inline comment\n"
                           "topics: [a, b]\n"
                           "related-decs:\n  - DEC-1\n  - DEC-2\n---\nBODY")
                fm, body = v.read_frontmatter(p)
                self.assertEqual(fm["entity"], "DecisionRecord")
                self.assertEqual(fm["topics"], ["a", "b"])
                self.assertEqual(fm["related-decs"], ["DEC-1", "DEC-2"])
                self.assertIn("BODY", body)
        finally:
            v._yaml = orig


class LlmCiCost(unittest.TestCase):
    def _wf(self, d, body):
        return _write(d, ".github/workflows/ai.yml", body)

    def test_endpoint_only_in_comment_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            self._wf(d, "# example only: api.anthropic.com\nname: ci\non: pull_request\n")
            self.assertEqual(v.check_llm_ci_cost(d), [])

    def test_missing_concurrency_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            self._wf(d, "name: ai\non:\n  pull_request:\n    types: [opened]\n"
                        "jobs:\n  x:\n    steps:\n      - run: curl api.anthropic.com\n")
            self.assertTrue(any("cancel-in-progress" in e
                                for e in v.check_llm_ci_cost(d)))

    def test_with_concurrency_ok(self):
        with tempfile.TemporaryDirectory() as d:
            self._wf(d, "name: ai\non:\n  pull_request:\n    types: [opened]\n"
                        "concurrency:\n  group: x\n  cancel-in-progress: true\n"
                        "jobs:\n  x:\n    steps:\n      - run: curl api.anthropic.com\n")
            self.assertFalse(any("cancel-in-progress" in e
                                 for e in v.check_llm_ci_cost(d)))

    def test_synchronize_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            self._wf(d, "name: ai\non:\n  pull_request:\n    types: [opened, synchronize]\n"
                        "concurrency:\n  group: x\n  cancel-in-progress: true\n"
                        "jobs:\n  x:\n    steps:\n      - run: curl api.anthropic.com\n")
            self.assertTrue(any("synchronize" in e for e in v.check_llm_ci_cost(d)))


_PLAN = """# Plan: demo

**Gate status**: READY

- [x] Derivation
- [x] Field completeness

## Slices

| Coordinate | Slice | Tok | Derives from | Depends on | State |
|---|---|---|---|---|---|
| `SLC0001SEC01BL01` | first | `M` | `grafo-de-identidad` | \u2014 | ready |

## Asserted scope

| Coordinate | Why no spec | What would close it |
|---|---|---|
"""


class PlanCompleteness(unittest.TestCase):
    """The plan gate (check #11, DEC-0020 clause 4) — the only check that fires
    before code exists."""

    def _corpus(self, d, plan=_PLAN, dag="graph TD\n  SLC0001SEC01BL01\n"):
        _write(d, "60-execution/62-plans/plan.md", plan)
        if dag is not None:
            _write(d, "60-execution/63-dags/dag.md", dag)

    def test_no_plans_is_skip(self):
        # A corpus that does not plan here is silent, not failing — same
        # contract as evidence-schema.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "30-decisions/DEC-0001-20260101-x.md", "---\nentity: DecisionRecord\n---\n")
            self.assertIsNone(v.check_plan_completeness(d))

    def test_complete_plan_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d)
            self.assertEqual([], v.check_plan_completeness(d))

    def test_unchecked_box_while_claiming_ready_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, _PLAN.replace("- [x] Derivation", "- [ ] Derivation"))
            self.assertTrue(any("unchecked" in e for e in v.check_plan_completeness(d)))

    def test_blocked_gate_may_carry_unchecked_boxes(self):
        # Declaring yourself blocked is honest, not a defect. Only a plan that
        # CLAIMS ready must satisfy every box.
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, _PLAN.replace("**Gate status**: READY",
                                          "**Gate status**: BLOCKED \u2014 spec missing")
                              .replace("- [x] Derivation", "- [ ] Derivation"))
            self.assertEqual([], v.check_plan_completeness(d))

    def test_missing_gate_line_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, _PLAN.replace("**Gate status**: READY", ""))
            self.assertTrue(any("Gate status" in e for e in v.check_plan_completeness(d)))

    def test_slice_without_substrate_spec_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, _PLAN.replace("`grafo-de-identidad`", "\u2014"))
            self.assertTrue(any("cites no substrate spec" in e
                                for e in v.check_plan_completeness(d)))

    def test_asserted_scope_declaration_is_accepted(self):
        # Asserted scope is a declaration, not an omission: a slice with no spec
        # is allowed precisely because it is named.
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, _PLAN.replace("`grafo-de-identidad`", "\u2014").replace(
                "| Coordinate | Why no spec | What would close it |\n|---|---|---|",
                "| Coordinate | Why no spec | What would close it |\n|---|---|---|\n"
                "| `SLC0001SEC01BL01` | spec pending | write it |"))
            self.assertEqual([], v.check_plan_completeness(d))

    def test_slice_missing_from_dag_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, dag="graph TD\n  SLC0002SEC01BL01\n")
            self.assertTrue(any("not in the derived DAG" in e
                                for e in v.check_plan_completeness(d)))

    def test_renamed_derives_column_is_caught_not_silently_skipped(self):
        # Columns are located by header. A plan that renames the column must fail
        # loudly rather than disable the derivation check.
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, _PLAN.replace("| Derives from ", "| Origin "))
            self.assertTrue(any("no 'Derives from' column" in e
                                for e in v.check_plan_completeness(d)))

    def test_registered_and_gates(self):
        # Unlike subslice-rate, this one IS a gate: it must not be a reporter.
        self.assertNotIn("plan-completeness", v.REPORTER_CHECKS)


_DECADES = ("00-context", "10-insights", "20-conclusions", "30-decisions", "40-goals",
            "50-products", "60-execution", "70-outcomes", "99-archive")


class ScaffoldCompleteness(unittest.TestCase):
    """DEC-0023 clause 4 — every canonical decade exists and says what it holds."""

    def _corpus(self, d, manifest='{"spec":"2.2.0","corpus":"engineering"}',
                decades=_DECADES, readmes=True):
        _write(d, "sliceops.json", manifest)
        for dec in decades:
            _write(d, f"{dec}/README.md" if readmes else f"{dec}/x.md", "# x\n")

    def test_not_a_corpus_is_skip(self):
        # No container manifest anywhere: a tree that is not a SliceOps corpus
        # is not a failing one.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "src/main.py", "print(1)\n")
            self.assertIsNone(v.check_scaffold_completeness(d))

    def test_complete_scaffold_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d)
            self.assertEqual([], v.check_scaffold_completeness(d))

    def test_absent_decade_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, decades=[x for x in _DECADES if x != "40-goals"])
            self.assertTrue(any("'40-goals' is absent" in e
                                for e in v.check_scaffold_completeness(d)))

    def test_decade_without_readme_is_caught(self):
        # The README is the point: an empty folder alone is silent.
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d, readmes=False)
            errs = v.check_scaffold_completeness(d)
            self.assertEqual(len(_DECADES), len(errs))
            self.assertTrue(all("has no README" in e for e in errs))

    def test_empty_decade_is_not_an_error(self):
        # DEC-0023 clause 3: emptiness is a declared gap, never a defect.
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d)   # every decade holds only its README
            self.assertEqual([], v.check_scaffold_completeness(d))

    def test_pointer_manifest_is_not_a_corpus(self):
        # A code repository carries no container (DEC-0011_1), so it is never
        # asked for decades.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "sliceops.json", '{"ref":"../_sliceops","remote":"https://x"}')
            self.assertIsNone(v.check_scaffold_completeness(d))

    def test_published_standard_uses_a_publishing_layout(self):
        # DEC-0002 + DEC-0022 clause 3: its decision record IS the deliverable,
        # so it is laid out for readers of a standard, not on decades.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "sliceops.json",
                   '{"spec":"2.2.0","corpus":"engineering",'
                   '"extensions":{"published-standard":"x"}}')
            _write(d, "decisions/DEC-0001-20260101-x.md", "# x\n")
            self.assertIsNone(v.check_scaffold_completeness(d))

    def test_free_decades_are_not_required(self):
        # 80/90 stay opt-in (DEC-0023 clause 1).
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d)
            self.assertFalse(any("80-" in e or "90-" in e
                                 for e in v.check_scaffold_completeness(d)))

    def test_worktrees_are_not_second_corpora(self):
        # A git worktree under .claude/ is another checkout of the same corpus.
        # Counting it produced the 17 false collisions DEC-0019 records.
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d)
            _write(d, ".claude/worktrees/wt/sliceops.json",
                   '{"spec":"2.2.0","corpus":"engineering"}')
            self.assertEqual([], v.check_scaffold_completeness(d))


    def test_undeclared_corpus_is_caught(self):
        # The blind spot this closes: the check finds corpora by their manifest, so
        # a corpus that never declared one was invisible — a tree carrying three
        # decade folders passed as clean.
        with tempfile.TemporaryDirectory() as d:
            for dec in ("10-decisions", "70-execution", "80-operations"):
                _write(d, f"{dec}/x.md", "# x\n")
            errs = v.check_scaffold_completeness(d)
            self.assertTrue(any("looks like a corpus" in e for e in errs))

    def test_canonical_number_with_wrong_name_is_named(self):
        # 70-execution occupies the number the canon reserves for 70-outcomes: a
        # pre-DEC-0011 layout, not free adopter space.
        with tempfile.TemporaryDirectory() as d:
            for dec in ("10-decisions", "70-execution"):
                _write(d, f"{dec}/x.md", "# x\n")
            errs = v.check_scaffold_completeness(d)
            self.assertTrue(any("reserved name is '70-outcomes'" in e for e in errs))
            self.assertTrue(any("reserved name is '10-insights'" in e for e in errs))

    def test_free_decade_number_is_not_flagged_as_wrong_name(self):
        with tempfile.TemporaryDirectory() as d:
            for dec in ("80-operations", "90-vendor"):
                _write(d, f"{dec}/x.md", "# x\n")
            self.assertFalse(any("reserved name" in e
                                 for e in v.check_scaffold_completeness(d)))

    def test_one_decade_folder_is_not_a_corpus(self):
        # Two or more, so a lone NN-name folder in an ordinary project is not a
        # finding.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01-drafts/x.md", "# x\n")
            self.assertIsNone(v.check_scaffold_completeness(d))

    def test_declared_corpus_subfolders_are_not_a_nested_corpus(self):
        # 00-context/01-values, 02-preferences… are decade-shaped. Descending into
        # a declared corpus would read them as an undeclared one.
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d)
            for sub in ("01-values", "02-preferences", "03-mental-models"):
                _write(d, f"00-context/{sub}/x.md", "# x\n")
            self.assertEqual([], v.check_scaffold_completeness(d))

    def test_undeclared_corpus_is_reported_once_not_per_nesting_level(self):
        with tempfile.TemporaryDirectory() as d:
            for dec in ("10-decisions", "40-architecture"):
                _write(d, f"eng/{dec}/x.md", "# x\n")
            for sub in ("00-cross-cutting", "01-integration-core"):
                _write(d, f"eng/40-architecture/{sub}/x.md", "# x\n")
            errs = v.check_scaffold_completeness(d)
            self.assertEqual(1, len([e for e in errs if "looks like a corpus" in e]))

    def test_non_utf8_file_does_not_crash_the_run(self):
        # Observed on a real corpus: a latin-1 byte in one file took down the whole
        # run through read_frontmatter.
        with tempfile.TemporaryDirectory() as d:
            self._corpus(d)
            with open(os.path.join(d, "30-decisions", "latin.md"), "wb") as fh:
                fh.write("---\nentity: DecisionRecord\nname: informaci\u00f3n\n---\n".encode("latin-1"))
            self.assertEqual([], v.check_scaffold_completeness(d))
            v.read_frontmatter(os.path.join(d, "30-decisions", "latin.md"))

    def test_registered_and_gates(self):
        self.assertNotIn("scaffold-completeness", v.REPORTER_CHECKS)


if __name__ == "__main__":
    unittest.main()
