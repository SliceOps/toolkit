#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Regression tests for the SliceOps naming validator (DEC-0008/0009/0010, v2).
# Stdlib only (unittest + tempfile), Python 3.9+ — runs anywhere the validator runs.

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATOR = os.path.join(_HERE, "..", "templates", "naming-validator", "naming_validator.py")
_spec = importlib.util.spec_from_file_location("naming_validator", _VALIDATOR)
nv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nv)


def _write(root, relpath, text):
    path = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _v(path, text, **kw):
    return nv.validate_file(path, text, **kw)


# Canonical v2 fixtures — universal grammar PREFIX-NNNN-YYYYMMDD-slug.md.
DEC_OK = "---\nentity: DecisionRecord\nstatus: approved\ncreated: 2026-05-01\n---\n# x\n"
DEC_OK_PATH = "decisions/DEC-0001-20260501-ok.md"


def _dec(kind=None, status="approved", created="2026-05-01", extra=""):
    lines = ["---", "entity: DecisionRecord", f"status: {status}", f"created: {created}"]
    if kind:
        lines.append(f"kind: {kind}")
    if extra:
        lines.append(extra)
    lines += ["---", "# x", ""]
    return "\n".join(lines)


class RetiredPrefixes(unittest.TestCase):
    def test_each_retired_prefix_names_the_correct_form(self):
        cases = {
            "corpus/DR-0001-20260101-a.md": "DEC-",
            "corpus/IR-0001-20260101-a.md": "INS-",
            "corpus/IN-0001-20260101-a.md": "INS-",
            "corpus/OC-0001-20260101-a.md": "OUTC-",
            "corpus/BR-0001-20260101-a.md": "OUTC-",
            "corpus/SKILL-0001-20260101-a.md": "CAP-",
            "corpus/RUN-0001-20260101-a.md": "CAP-",
            "corpus/REF-0001-20260101-a.md": "CAP-",
        }
        for path, want in cases.items():
            errs = _v(path, "")
            self.assertTrue(errs, path)
            self.assertIn(want, errs[0])

    def test_dec0008_retired_prefixes_name_the_plain_word_canonical(self):
        # LP-/CF-/AP- retired by DEC-0008.2 (Conclusion/Frame/Priority renames).
        cases = {
            "corpus/LP-0001-20260101-a.md": "CONC-",
            "corpus/CF-0001-20260101-a.md": "FRAME-",
            "corpus/AP-0001-20260101-a.md": "PRI-",
        }
        for path, want in cases.items():
            errs = _v(path, "")
            self.assertTrue(errs, path)
            self.assertIn(want, errs[0])
            self.assertIn("DEC-0008", errs[0])

    def test_ins_prefix_is_not_misread_as_in(self):
        # INS-0013 must not trip the IN- rule (lookahead requires IN-<digit>).
        self.assertEqual(_v("corpus/INS-0013-20260712-obs.md",
                            "---\nentity: InsightRecord\nstatus: active\n---\n"), [])

    def test_infra_is_not_misread_as_in(self):
        self.assertEqual(_v("notes/IN-progress-notes.md", ""), [])


class FlatDecisions(unittest.TestCase):
    def test_lifecycle_subfolder_is_flagged(self):
        for sub in ("accepted", "rfcs", "superseded", "deprecated"):
            errs = _v(f"10-decisions/{sub}/DEC-0001-20260101-x.md", DEC_OK)
            self.assertTrue(any("FLAT" in e for e in errs), sub)

    def test_flat_folder_passes(self):
        self.assertEqual(_v("10-decisions/DEC-0001-20260101-x.md", DEC_OK), [])


class DecLifecycle(unittest.TestCase):
    def test_prefix_status_mismatch(self):
        errs = _v("decisions/DEC-P-0001-20260101-x.md",
                  "---\nentity: DecisionRecord\nstatus: approved\ncreated: 2026-01-01\n---\n")
        self.assertTrue(any("does not match status" in e for e in errs))

    def test_legacy_status_blocked_by_default_tolerated_with_flags(self):
        text = "---\nentity: DecisionRecord\nstatus: ratified\ncreated: 2026-01-01\n---\n"
        self.assertTrue(any("legacy status" in e for e in _v("d/DEC-0001-20260101-x.md", text)))
        self.assertEqual(_v("d/DEC-0001-20260101-x.md", text, tolerate_legacy=True), [])
        self.assertEqual(_v("d/DEC-0001-20260101-x.md", text, transition=True), [])

    def test_coherent_lifecycle_passes(self):
        ok = [("decisions/DEC-0001-20260101-x.md", "approved"),
              ("decisions/DEC-P-0001-20260101-x.md", "pending"),
              ("decisions/DEC-D-0001-20260101-x.md", "deprecated")]
        for path, st in ok:
            self.assertEqual(
                _v(path, f"---\nentity: DecisionRecord\nstatus: {st}\ncreated: 2026-01-01\n---\n"), [], path)


class EntityPrefix(unittest.TestCase):
    def test_entity_without_prefix_suggests_filename(self):
        errs = _v("corpus/priorities/handoffs.md",
                  "---\ndatta_entity: Priority\nstatus: active\nserves-goal: GOAL-0001-20260101-x\nrank: 1\n---\n")
        self.assertTrue(any("PRI-handoffs.md" in e for e in errs))

    def test_implementation_alias_maps_to_canonical(self):
        errs = _v("corpus/skills/CAP-0001-20260101-review.md",
                  "---\ndatta_entity: AgentSkill\nstatus: active\n---\n")
        self.assertTrue(any("implementation alias" in e and "Capability" in e for e in errs))

    def test_dec0008_old_entity_names_are_implementation_aliases(self):
        # LearningPattern/CognitiveFramework/ActivePriority are now aliases of
        # Conclusion/Frame/Priority — never their own prefix (DEC-0008.2).
        cases = [
            ("corpus/LP-0001-20260101-x.md", "LearningPattern", "Conclusion"),
            ("corpus/CF-0001-20260101-x.md", "CognitiveFramework", "Frame"),
            ("corpus/AP-0001-20260101-x.md", "ActivePriority", "Priority"),
        ]
        for path, old, new in cases:
            errs = _v(path, f"---\nentity: {old}\nstatus: active\n---\n")
            self.assertTrue(any("implementation alias" in e and new in e for e in errs), path)

    def test_non_catalog_entity_is_out_of_scope(self):
        self.assertEqual(_v("knowledge/ledger-notes.md",
                            "---\ndatta_entity: KnowledgeItem\nstatus: active\n---\n"), [])

    def test_freeform_without_entity_passes(self):
        self.assertEqual(_v("notes/scratch-idea.md", "just prose\n"), [])


class EnumChecks(unittest.TestCase):
    def test_outcome_requires_kind(self):
        errs = _v("corpus/outcomes/OUTC-0001-20260101-x.md",
                  "---\ndatta_entity: OutcomeRecord\nstatus: final\n---\n")
        self.assertTrue(any("kind" in e for e in errs))
        self.assertEqual(_v("corpus/outcomes/OUTC-0001-20260101-x.md",
                            "---\ndatta_entity: OutcomeRecord\nkind: result\n---\n"), [])

    def test_capability_component_needs_backreference(self):
        errs = _v("corpus/CAP-0002-20260101-runbook.md",
                  "---\nentity: Capability\nkind: runbook\n---\n")
        self.assertTrue(any("capability:" in e for e in errs))
        self.assertEqual(_v("corpus/CAP-0002-20260101-runbook.md",
                            "---\nentity: Capability\nkind: runbook\ncapability: pdf-parsing\n---\n"), [])


class Exemptions(unittest.TestCase):
    def test_templates_and_context_files_exempt(self):
        self.assertEqual(_v("reference/templates/dec-template.md",
                            "---\nentity: DecisionRecord\nstatus: pending\n---\n"), [])
        self.assertEqual(_v("README.md", ""), [])
        self.assertEqual(_v("CLAUDE.md", ""), [])

    def test_archive_excluded(self):
        self.assertEqual(_v("99-archive/DR-2020-01-01-old.md", ""), [])

    def test_yaml_inside_code_fences_is_not_frontmatter(self):
        # Catalog docs quote frontmatter in fenced blocks; no top --- block → skip.
        text = "# DecisionRecord spec\n```yaml\nentity: DecisionRecord\nstatus: proposed\n```\n"
        self.assertEqual(_v("reference/entity-catalog/01-decision-record.md", text), [])

    def test_dec0010_reserved_infrastructure_names_exempt(self):
        # AGENTS.md/MEMORY.md/GEMINI.md/_organization.md/_index.md are reserved
        # infrastructure (DEC-0010.5), never entity artifacts under the grammar.
        for base in ("AGENTS.md", "MEMORY.md", "GEMINI.md", "_organization.md", "_index.md"):
            self.assertEqual(_v(base, "---\nentity: DecisionRecord\n---\n"), [], base)

    def test_dec0010_ledger_suffix_pattern_exempt(self):
        for path in ("corpus/slices/ledger.md", "corpus/slices/slice-ledger.md",
                     "corpus/handoff-ledger.md"):
            self.assertEqual(_v(path, "---\nentity: DecisionRecord\n---\n"), [], path)


class UniversalGrammar(unittest.TestCase):
    """DEC-0008.5 — PREFIX-NNNN-YYYYMMDD-slug.md, all 15 grammar prefixes."""

    def test_valid_forms_pass_for_every_grammar_prefix(self):
        cases = [
            ("decisions/DEC-0001-20260712-slug.md", "DecisionRecord"),
            ("decisions/DEC-P-0002-20260712-slug.md", "DecisionRecord"),
            ("decisions/DEC-D-0003-20260712-slug.md", "DecisionRecord"),
            ("insights/INS-0013-20260712-slug.md", "InsightRecord"),
            ("outcomes/OUTC-0001-20260712-slug.md", "OutcomeRecord"),
            ("capabilities/CAP-0001-20260712-slug.md", "Capability"),
            ("goals/GOAL-0001-20260712-slug.md", "Goal"),
            ("conclusions/CONC-0001-20260712-slug.md", "Conclusion"),
            ("frames/FRAME-0001-20260712-slug.md", "Frame"),
            ("packs/CP-0028-20260712-slug.md", "ContextPack"),
            ("priorities/PRI-0001-20260712-slug.md", "Priority"),
            ("relationships/REL-0001-20260712-slug.md", "RelationshipContext"),
            ("prefs/PREF-0001-20260712-slug.md", "Preference"),
            ("values/VAL-0001-20260712-slug.md", "Value"),
            ("sessions/SESS-0001-20260712-slug.md", "Session"),
        ]
        for path, entity in cases:
            fm = f"---\nentity: {entity}\nstatus: active\n---\n"
            if entity == "DecisionRecord":
                st = {"DEC-": "approved", "DEC-P-": "pending", "DEC-D-": "deprecated"}[
                    next(x for x in nv.DEC_PREFIXES if os.path.basename(path).startswith(x))]
                fm = f"---\nentity: DecisionRecord\nstatus: {st}\ncreated: 2026-01-01\n---\n"
            elif entity == "Goal":
                fm = "---\nentity: Goal\nstatus: active\ndecided-by: DEC-0001-20260712-slug\n---\n"
            elif entity == "Priority":
                fm = "---\nentity: Priority\nstatus: open\nserves-goal: GOAL-0001-20260712-slug\nrank: 1\n---\n"
            elif entity == "OutcomeRecord":
                fm = "---\nentity: OutcomeRecord\nkind: result\n---\n"
            errs = _v(path, fm)
            self.assertEqual(errs, [], f"{path}: {errs}")

    def test_min_four_digit_counter_unbounded_above(self):
        self.assertEqual(_v("insights/INS-10000-20260712-slug.md",
                            "---\nentity: InsightRecord\nstatus: active\n---\n"), [])

    def test_three_digit_counter_fails_strict_grammar(self):
        errs = _v("insights/INS-001-20260712-slug.md",
                  "---\nentity: InsightRecord\nstatus: active\n---\n")
        self.assertTrue(any("universal grammar" in e for e in errs))

    def test_date_based_pre_v2_form_fails_strict_grammar(self):
        errs = _v("insights/INS-2026-07-12-slug.md",
                  "---\nentity: InsightRecord\nstatus: active\n---\n")
        self.assertTrue(any("universal grammar" in e for e in errs))

    def test_uppercase_slug_fails_grammar(self):
        errs = _v("insights/INS-0001-20260712-Slug.md",
                  "---\nentity: InsightRecord\nstatus: active\n---\n")
        self.assertTrue(any("universal grammar" in e for e in errs))

    def test_short_date_fails_grammar(self):
        errs = _v("insights/INS-0001-2026712-slug.md",
                  "---\nentity: InsightRecord\nstatus: active\n---\n")
        self.assertTrue(any("universal grammar" in e for e in errs))

    def test_transition_tolerates_date_based_and_three_digit_counter_forms(self):
        self.assertEqual(_v("insights/INS-2026-07-12-slug.md",
                            "---\nentity: InsightRecord\nstatus: active\n---\n", transition=True), [])
        self.assertEqual(_v("insights/INS-001-slug.md",
                            "---\nentity: InsightRecord\nstatus: active\n---\n", transition=True), [])

    def test_grammar_still_applies_by_prefix_lead_without_entity_frontmatter(self):
        # A file with a recognizable entity-prefix lead but no/garbled entity
        # key must still be graded against the grammar (defense in depth).
        errs = _v("misc/CONC-bad-name.md", "no frontmatter here\n")
        self.assertTrue(any("universal grammar" in e for e in errs))


class DecKindAxis(unittest.TestCase):
    """DEC-0008.3 — kind axis + edge coherence, cutoff 2026-07-13."""

    def test_strategic_without_defines_goal_is_error(self):
        text = _dec(kind="strategic", created="2026-08-01")
        errs = _v("decisions/DEC-0001-20260801-x.md", text)
        self.assertTrue(any("strategic" in e and "defines-goal" in e for e in errs))

    def test_strategic_with_defines_goal_passes(self):
        text = _dec(kind="strategic", created="2026-08-01",
                    extra="defines-goal: [GOAL-0001-20260801-x]")
        self.assertEqual(_v("decisions/DEC-0001-20260801-x.md", text), [])

    def test_tactical_without_serves_goal_is_error(self):
        text = _dec(kind="tactical", created="2026-08-01")
        errs = _v("decisions/DEC-0001-20260801-x.md", text)
        self.assertTrue(any("tactical" in e and "serves-goal" in e for e in errs))

    def test_tactical_with_serves_goal_passes(self):
        text = _dec(kind="tactical", created="2026-08-01",
                    extra="serves-goal: GOAL-0001-20260801-x")
        self.assertEqual(_v("decisions/DEC-0001-20260801-x.md", text), [])

    def test_constitutive_approved_without_approver_is_error(self):
        text = _dec(kind="constitutive", status="approved", created="2026-08-01")
        errs = _v("decisions/DEC-0001-20260801-x.md", text)
        self.assertTrue(any("constitutive" in e and "approver" in e for e in errs))

    def test_constitutive_approved_with_approver_passes(self):
        text = _dec(kind="constitutive", status="approved", created="2026-08-01",
                    extra="approver: Andrés Ramírez Sierra")
        self.assertEqual(_v("decisions/DEC-0001-20260801-x.md", text), [])

    def test_constitutive_pending_without_approver_passes(self):
        # approver only REQUIRED once status is approved.
        text = _dec(kind="constitutive", status="pending", created="2026-08-01")
        self.assertEqual(_v("decisions/DEC-P-0001-20260801-x.md", text), [])

    def test_invalid_kind_value_is_error(self):
        text = _dec(kind="operational", created="2026-08-01")
        errs = _v("decisions/DEC-0001-20260801-x.md", text)
        self.assertTrue(any("kind 'operational' invalid" in e for e in errs))

    def test_kind_required_on_or_after_cutoff(self):
        text = _dec(kind=None, created="2026-07-13")
        errs = _v("decisions/DEC-0001-20260713-x.md", text)
        self.assertTrue(any("requires" in e and "kind" in e for e in errs))

    def test_kind_not_required_before_cutoff(self):
        text = _dec(kind=None, created="2026-07-12")
        self.assertEqual(_v("decisions/DEC-0001-20260712-x.md", text), [])

    def test_kind_missing_after_cutoff_tolerated_under_transition(self):
        text = _dec(kind=None, created="2026-08-01")
        self.assertEqual(_v("decisions/DEC-0001-20260801-x.md", text, transition=True), [])

    def test_unicode_approver_name_is_recognized(self):
        # Regression: approver values must not be restricted to ASCII (the
        # v1 FM_KEY value class dropped non-ASCII names like 'Andrés').
        text = _dec(kind="constitutive", status="approved", created="2026-08-01",
                    extra="approver: Andrés Ramírez Sierra")
        errs = _v("decisions/DEC-0001-20260801-x.md", text)
        self.assertFalse(any("approver" in e for e in errs), errs)


class Pyramid(unittest.TestCase):
    """DEC-0008.4 — Goal.decided-by, Priority.serves-goal + rank."""

    def test_goal_requires_decided_by(self):
        errs = _v("goals/GOAL-0001-20260801-x.md",
                  "---\nentity: Goal\nstatus: active\n---\n")
        self.assertTrue(any("decided-by" in e for e in errs))

    def test_goal_with_decided_by_passes(self):
        self.assertEqual(_v("goals/GOAL-0001-20260801-x.md",
                            "---\nentity: Goal\nstatus: active\ndecided-by: DEC-0001-20260801-x\n---\n"), [])

    def test_priority_requires_serves_goal_and_rank(self):
        errs = _v("priorities/PRI-0001-20260801-x.md",
                  "---\nentity: Priority\nstatus: open\n---\n")
        self.assertTrue(any("serves-goal" in e for e in errs))
        self.assertTrue(any("rank" in e for e in errs))

    def test_priority_bucket_value_is_retired_in_favor_of_rank(self):
        errs = _v("priorities/PRI-0001-20260801-x.md",
                  "---\nentity: Priority\nstatus: open\nserves-goal: GOAL-0001-20260801-x\npriority: high\n---\n")
        self.assertTrue(any("rank" in e and "retired" in e for e in errs))

    def test_priority_non_integer_rank_is_error(self):
        errs = _v("priorities/PRI-0001-20260801-x.md",
                  "---\nentity: Priority\nstatus: open\nserves-goal: GOAL-0001-20260801-x\nrank: high\n---\n")
        self.assertTrue(any("not an integer" in e for e in errs))

    def test_priority_complete_passes(self):
        self.assertEqual(_v("priorities/PRI-0001-20260801-x.md",
                            "---\nentity: Priority\nstatus: open\nserves-goal: GOAL-0001-20260801-x\nrank: 1\n---\n"), [])


class SliceCoordinate(unittest.TestCase):
    """DEC-0008.6 — SLC filename and frontmatter forms."""

    def test_valid_slc_filename_forms_pass(self):
        for base in ("SLC0012SEC03BL02-20260712-slug.md", "SLC0034-20260712-slug.md"):
            self.assertEqual(_v(f"slices/{base}", "no entity frontmatter\n"), [], base)

    def test_invalid_slc_filename_is_error(self):
        errs = _v("slices/SLC12-20260712-slug.md", "no entity frontmatter\n")  # SLC too short (<4 digits)
        self.assertTrue(any("SLC" in e for e in errs))

    def test_slc_filename_with_dots_is_error(self):
        errs = _v("slices/SLC0012.SEC03-20260712-slug.md", "no entity frontmatter\n")
        self.assertTrue(any("SLC" in e for e in errs))

    def test_frontmatter_slc_coordinate_valid_forms_pass(self):
        for coord in ("SLC0012SEC03BL02", "SLC0034"):
            errs = _v("corpus/INS-0001-20260712-x.md",
                      f"---\nentity: InsightRecord\noriginating_slice: {coord}\n---\n")
            self.assertFalse(any("originating_slice" in e for e in errs), (coord, errs))

    def test_frontmatter_slc_coordinate_invalid_form_is_error(self):
        errs = _v("corpus/INS-0001-20260712-x.md",
                  "---\nentity: InsightRecord\noriginating_slice: SLC12\n---\n")
        self.assertTrue(any("originating_slice" in e for e in errs))

    def test_legacy_dotted_slice_id_is_error_with_suggestion(self):
        errs = _v("corpus/INS-0001-20260712-x.md",
                  "---\nentity: InsightRecord\noriginating_slice: BL-02.SEC-03.SL-012\n---\n")
        self.assertTrue(any("dotted" in e and "SLC" in e for e in errs))

    def test_legacy_dotted_slice_id_tolerated_under_transition(self):
        self.assertEqual(_v("corpus/INS-0001-20260712-x.md",
                            "---\nentity: InsightRecord\noriginating_slice: BL-02.SEC-03.SL-012\n---\n",
                            transition=True), [])

    def test_null_originating_slice_is_not_flagged(self):
        self.assertEqual(_v("corpus/INS-0001-20260712-x.md",
                            "---\nentity: InsightRecord\noriginating_slice: null\n---\n"), [])


class ContextPackKinds(unittest.TestCase):
    """DEC-0009 — ContextPack kind: pack|brief|handoff, handoff reason."""

    def test_valid_kinds_pass(self):
        for kind in ("pack", "brief", "handoff"):
            text = f"---\nentity: ContextPack\nkind: {kind}\n---\n"
            self.assertEqual(_v(f"packs/CP-0001-20260712-{kind}.md", text), [], kind)

    def test_invalid_kind_is_error(self):
        errs = _v("packs/CP-0001-20260712-x.md",
                  "---\nentity: ContextPack\nkind: summary\n---\n")
        self.assertTrue(any("pack|brief|handoff" in e for e in errs))

    def test_handoff_reason_enum(self):
        for reason in ("context-exhausted", "spinoff"):
            text = f"---\nentity: ContextPack\nkind: handoff\nreason: {reason}\n---\n"
            self.assertEqual(_v(f"packs/CP-0001-20260712-h.md", text), [], reason)

    def test_handoff_bad_reason_is_error(self):
        errs = _v("packs/CP-0001-20260712-h.md",
                  "---\nentity: ContextPack\nkind: handoff\nreason: fyi\n---\n")
        self.assertTrue(any("reason 'fyi' invalid" in e for e in errs))

    def test_handoff_without_reason_is_not_flagged(self):
        # reason: is only validated for its ENUM when present (task spec: "if
        # present, must be ...") — no unconditional requiredness stated.
        self.assertEqual(_v("packs/CP-0001-20260712-h.md",
                            "---\nentity: ContextPack\nkind: handoff\n---\n"), [])


class CorpusIndex(unittest.TestCase):
    """DEC-0010 — _index.md required at corpus root; route targets resolve."""

    def test_missing_index_is_error_in_strict_mode(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, DEC_OK_PATH, DEC_OK)
            errs = nv.check_index(d, transition=False)
            self.assertTrue(any("_index.md" in e for e in errs))

    def test_missing_index_tolerated_under_transition(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, DEC_OK_PATH, DEC_OK)
            self.assertEqual(nv.check_index(d, transition=True), [])

    def test_index_present_with_valid_route_passes(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, DEC_OK_PATH, DEC_OK)
            _write(d, "_index.md", f"# Index\n\n- [decisions]({DEC_OK_PATH})\n")
            self.assertEqual(nv.check_index(d), [])

    def test_index_with_broken_route_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "_index.md", "# Index\n\n- [ghost](decisions/DEC-9999-20260101-ghost.md)\n")
            errs = nv.check_index(d)
            self.assertTrue(any("does not resolve" in e and "ghost" in e for e in errs))

    def test_index_check_only_runs_for_directory_targets_via_run_check(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write(d, DEC_OK_PATH, DEC_OK)
            # Passing the single FILE (not the directory) must not demand an index.
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = nv.run_check([path])
            finally:
                out = sys.stdout.getvalue()
                sys.stdout = old_stdout
            self.assertEqual(code, 0, out)
            self.assertNotIn("_index.md", out)

    def test_index_check_runs_for_directory_targets_via_run_check(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, DEC_OK_PATH, DEC_OK)
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = nv.run_check([d])
            finally:
                out = sys.stdout.getvalue()
                sys.stdout = old_stdout
            self.assertEqual(code, 1, out)
            self.assertIn("_index.md", out)

    def test_hook_mode_never_requires_index(self):
        # DEC-0010 is a corpus-wide concern; --hook validates a single write.
        old_in, old_err = sys.stdin, sys.stderr
        sys.stdin = io.StringIO(json.dumps({"tool_name": "Write", "tool_input": {
            "file_path": "/x/" + DEC_OK_PATH, "content": DEC_OK}}))
        sys.stderr = io.StringIO()
        try:
            code = nv.run_hook()
            err = sys.stderr.getvalue()
        finally:
            sys.stdin, sys.stderr = old_in, old_err
        self.assertEqual(code, 0, err)


class CheckAndHook(unittest.TestCase):
    def test_run_check_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, DEC_OK_PATH, DEC_OK)
            _write(d, "_index.md", f"# Index\n\n- [decisions]({DEC_OK_PATH})\n")
            self.assertEqual(nv.run_check([d]), 0)
            _write(d, "decisions/DR-0001-20260102-bad.md", DEC_OK)
            self.assertEqual(nv.run_check([d]), 1)

    def _hook(self, payload):
        old_in, old_err = sys.stdin, sys.stderr
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.stderr = io.StringIO()
        try:
            code = nv.run_hook()
            return code, sys.stderr.getvalue()
        finally:
            sys.stdin, sys.stderr = old_in, old_err

    def test_hook_blocks_with_correct_name(self):
        code, err = self._hook({"tool_name": "Write", "tool_input": {
            "file_path": "/x/decisions/DR-2026-08-01-new.md",
            "content": "---\nentity: DecisionRecord\nstatus: proposed\n---\n"}})
        self.assertEqual(code, 2)
        self.assertIn("DEC-P-", err)

    def test_hook_allows_homologated_write(self):
        # created predates the DEC-0008.3 kind cutoff (2026-07-13) — this test
        # is a general well-formed-write smoke test, not a kind-axis test
        # (DecKindAxis covers the cutoff itself).
        code, _ = self._hook({"tool_name": "Write", "tool_input": {
            "file_path": "/x/decisions/DEC-P-0001-20260701-new.md",
            "content": "---\nentity: DecisionRecord\nstatus: pending\ncreated: 2026-07-01\n---\n"}})
        self.assertEqual(code, 0)

    def test_hook_fails_open_on_garbage(self):
        old_in = sys.stdin
        sys.stdin = io.StringIO("not json at all")
        try:
            self.assertEqual(nv.run_hook(), 0)
        finally:
            sys.stdin = old_in

    def test_hook_ignores_non_markdown(self):
        code, _ = self._hook({"tool_name": "Write", "tool_input": {
            "file_path": "/x/src/DR-legacy-parser.ts", "content": "code"}})
        self.assertEqual(code, 0)

    def test_hook_mode_is_always_strict_never_transition(self):
        # --hook has no --transition flag; pre-v2 forms must still block.
        code, err = self._hook({"tool_name": "Write", "tool_input": {
            "file_path": "/x/insights/INS-001-slug.md",
            "content": "---\nentity: InsightRecord\nstatus: active\n---\n"}})
        self.assertEqual(code, 2)
        self.assertIn("universal grammar", err)


if __name__ == "__main__":
    unittest.main()
