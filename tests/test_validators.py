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
        # Two same-year date-based DRs + a CF — uniqueness is date+slug, not a
        # counter. The "2026" must not be mis-read as a counter (commit 883c391).
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/accepted/DR-2026-05-12-three-layer.md", "x")
            _write(d, "decisions/accepted/DR-2026-06-15-license.md", "x")
            _write(d, "cf/CF-2026-05-14-glossary.md", "x")
            self.assertEqual(v.check_counter_atomicity(d), [])

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
            _write(d, "decisions/accepted/DR-A.md", _dr(["DR-B"]))
            _write(d, "decisions/accepted/DR-B.md", _dr(["DR-A"]))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            self.assertEqual(v.check_bidirectional(docs), [])

    def test_one_way_dr_pair_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/accepted/DR-A.md", _dr(["DR-B"]))
            _write(d, "decisions/accepted/DR-B.md", _dr([]))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            errs = v.check_bidirectional(docs)
            self.assertEqual(len(errs), 1)
            self.assertIn("DR-A -> DR-B", errs[0])

    def test_non_dr_source_is_one_way_ok(self):
        # An InsightRecord referencing a DR must NOT require the DR to reciprocate.
        with tempfile.TemporaryDirectory() as d:
            ins = "---\nentity: InsightRecord\nrelated-decs:\n  - DR-A\n---\nbody"
            _write(d, "insights/INS-1.md", ins)
            _write(d, "decisions/accepted/DR-A.md", _dr([]))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            self.assertEqual(v.check_bidirectional(docs), [])

    def test_frozen_target_is_skipped(self):
        # A live DR referencing a superseded DR: the frozen doc is excluded by
        # find_docs, so the edge is not enforced.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/accepted/DR-A.md", _dr(["DR-OLD"]))
            _write(d, "decisions/superseded/DR-OLD.md", _dr([]))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            self.assertEqual(v.check_bidirectional(docs), [])

    def test_custom_entity_key(self):
        # Runtime-mapped entity key (e.g. datta_entity) is honored.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/accepted/DR-A.md", _dr(["DR-B"], "datta_entity"))
            _write(d, "decisions/accepted/DR-B.md", _dr([], "datta_entity"))
            docs = {p: v.read_frontmatter(p) for p in v.find_docs(d)}
            # Default key 'entity' → sources unrecognized → no enforcement.
            self.assertEqual(v.check_bidirectional(docs), [])
            # Mapped key → the one-way pair is caught.
            errs = v.check_bidirectional(docs, "datta_entity")
            self.assertEqual(len(errs), 1)


if __name__ == "__main__":
    unittest.main()
