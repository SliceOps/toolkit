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


if __name__ == "__main__":
    unittest.main()
