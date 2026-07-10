#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Regression tests for the SliceOps naming validator (spec v1.1.0 naming.md).
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


DEC_OK = "---\nentity: DecisionRecord\nstatus: approved\n---\n# x\n"


class RetiredPrefixes(unittest.TestCase):
    def test_each_retired_prefix_names_the_correct_form(self):
        cases = {
            "brain/DR-2026-01-01-a.md": "DEC-",
            "brain/IR-2026-01-01-a.md": "INS-",
            "brain/IN-2026-01-01-a.md": "INS-",
            "brain/OC-2026-01-01-a.md": "OUTC-",
            "brain/BR-2026-01-01-a.md": "OUTC-",
            "brain/SKILL-a.md": "CAP-",
            "brain/RUN-001-a.md": "CAP-",
            "brain/REF-001-a.md": "CAP-",
        }
        for path, want in cases.items():
            errs = _v(path, "")
            self.assertTrue(errs, path)
            self.assertIn(want, errs[0])

    def test_ins_prefix_is_not_misread_as_in(self):
        # INS-013 must not trip the IN- rule (lookahead requires IN-<digit>).
        self.assertEqual(_v("brain/INS-013-obs.md",
                            "---\nentity: InsightRecord\nstatus: active\n---\n"), [])

    def test_infra_is_not_misread_as_in(self):
        self.assertEqual(_v("notes/IN-progress-notes.md", ""), [])


class FlatDecisions(unittest.TestCase):
    def test_lifecycle_subfolder_is_flagged(self):
        for sub in ("accepted", "rfcs", "superseded", "deprecated"):
            errs = _v(f"10-decisions/{sub}/DEC-001-x.md", DEC_OK)
            self.assertTrue(any("FLAT" in e for e in errs), sub)

    def test_flat_folder_passes(self):
        self.assertEqual(_v("10-decisions/DEC-001-x.md", DEC_OK), [])


class DecLifecycle(unittest.TestCase):
    def test_prefix_status_mismatch(self):
        errs = _v("decisions/DEC-P-2026-01-01-x.md",
                  "---\nentity: DecisionRecord\nstatus: approved\n---\n")
        self.assertTrue(any("does not match status" in e for e in errs))

    def test_legacy_status_blocked_by_default_tolerated_with_flag(self):
        text = "---\nentity: DecisionRecord\nstatus: ratified\n---\n"
        self.assertTrue(any("legacy status" in e for e in _v("d/DEC-001-x.md", text)))
        self.assertEqual(_v("d/DEC-001-x.md", text, tolerate_legacy=True), [])

    def test_coherent_lifecycle_passes(self):
        ok = [("decisions/DEC-2026-01-01-x.md", "approved"),
              ("decisions/DEC-P-2026-01-01-x.md", "pending"),
              ("decisions/DEC-D-2026-01-01-x.md", "deprecated")]
        for path, st in ok:
            self.assertEqual(
                _v(path, f"---\nentity: DecisionRecord\nstatus: {st}\n---\n"), [], path)


class EntityPrefix(unittest.TestCase):
    def test_entity_without_prefix_suggests_filename(self):
        errs = _v("brain/active-priorities/handoffs.md",
                  "---\ndatta_entity: ActivePriority\nstatus: active\n---\n")
        self.assertTrue(any("AP-handoffs.md" in e for e in errs))

    def test_implementation_alias_maps_to_canonical(self):
        errs = _v("brain/skills/CAP-review.md",
                  "---\ndatta_entity: AgentSkill\nstatus: active\n---\n")
        self.assertTrue(any("implementation alias" in e and "Capability" in e for e in errs))

    def test_non_catalog_entity_is_out_of_scope(self):
        self.assertEqual(_v("knowledge/ledger-notes.md",
                            "---\ndatta_entity: KnowledgeItem\nstatus: active\n---\n"), [])

    def test_freeform_without_entity_passes(self):
        self.assertEqual(_v("notes/scratch-idea.md", "just prose\n"), [])


class EnumChecks(unittest.TestCase):
    def test_outcome_requires_kind(self):
        errs = _v("brain/outcomes/OUTC-2026-01-01-x.md",
                  "---\ndatta_entity: OutcomeRecord\nstatus: final\n---\n")
        self.assertTrue(any("kind" in e for e in errs))
        self.assertEqual(_v("brain/outcomes/OUTC-2026-01-01-x.md",
                            "---\ndatta_entity: OutcomeRecord\nkind: result\n---\n"), [])

    def test_capability_component_needs_backreference(self):
        errs = _v("brain/CAP-002-runbook.md",
                  "---\nentity: Capability\nkind: runbook\n---\n")
        self.assertTrue(any("capability:" in e for e in errs))
        self.assertEqual(_v("brain/CAP-002-runbook.md",
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


class CheckAndHook(unittest.TestCase):
    def test_run_check_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "decisions/DEC-2026-01-01-ok.md", DEC_OK)
            self.assertEqual(nv.run_check([d]), 0)
            _write(d, "decisions/DR-2026-01-02-bad.md", DEC_OK)
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
        self.assertIn("DEC-P-2026-08-01-new.md", err)

    def test_hook_allows_homologated_write(self):
        code, _ = self._hook({"tool_name": "Write", "tool_input": {
            "file_path": "/x/decisions/DEC-P-2026-08-01-new.md",
            "content": "---\nentity: DecisionRecord\nstatus: pending\n---\n"}})
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


if __name__ == "__main__":
    unittest.main()
