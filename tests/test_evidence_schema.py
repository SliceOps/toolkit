#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Regression tests for check #10 — evidence-schema (evidence.v1 records).
#
# Fixtures under tests/fixtures/evidence/ are the spec repo's golden examples
# (reference/evidence/examples/, DR-2026-07-02-evidence-v1-canonical-schema):
#   - the two VALID ones are renamed *.evidence.json so the real discovery
#     glob picks them up (they double as the toolkit's own self-application
#     records: the CI self-run validates them live);
#   - the three INVALID ones KEEP their *.evidence.v1.example.json names —
#     '.example.' is excluded from discovery by design, so the toolkit's own
#     self-run (and the spec repo's CI, which carries the same fixtures)
#     stays green.
#
# Both validation modes are exercised: full Draft 2020-12 when jsonschema is
# importable (skipped otherwise), and the documented stdlib-subset fallback by
# forcing the optional import off — the same green-with-and-without-optional-
# deps discipline v0.1.1 established for PyYAML.

import importlib.util
import json
import os
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_VALIDATORS = os.path.join(
    _HERE, "..", "templates", "consistency-validators", "validators.py"
)
_spec = importlib.util.spec_from_file_location("validators", _VALIDATORS)
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)

_FIXTURES = os.path.join(_HERE, "fixtures", "evidence")

VALID = [
    "valid-full-slice-merge.evidence.json",
    "valid-minimal-gated-operation.evidence.json",
]
INVALID_BAD_SHA = "invalid-bad-provenance-commit.evidence.v1.example.json"
INVALID_NO_SECURITY = "invalid-slice-merge-missing-security.evidence.v1.example.json"
INVALID_UNKNOWN_FIELD = "invalid-unknown-top-level-field.evidence.v1.example.json"


def _stage(dst, mapping):
    """Copy fixtures into dst as {fixture-name: staged-name}."""
    for src, name in mapping.items():
        shutil.copy(os.path.join(_FIXTURES, src), os.path.join(dst, name))


class _EvidenceCheckMixin:
    """Behaviour shared by both modes; subclasses pin the mode."""

    def test_valid_records_pass(self):
        with tempfile.TemporaryDirectory() as d:
            _stage(d, {name: name for name in VALID})
            self.assertEqual(v.check_evidence_schema(d), [])

    def test_invalid_bad_commit_sha_is_caught(self):
        # provenance.commitSha must match ^[a-f0-9]{7,40}$ — pattern check.
        with tempfile.TemporaryDirectory() as d:
            _stage(d, {INVALID_BAD_SHA: "bad-sha.evidence.json"})
            errs = v.check_evidence_schema(d)
            self.assertTrue(errs)
            self.assertTrue(any("commitSha" in e for e in errs), errs)

    def test_invalid_slice_merge_missing_security_is_caught(self):
        # slice-merge completeness: no category:security check -> rejection.
        with tempfile.TemporaryDirectory() as d:
            _stage(d, {INVALID_NO_SECURITY: "no-security.evidence.json"})
            errs = v.check_evidence_schema(d)
            self.assertTrue(errs)
            self.assertTrue(any("checks" in e for e in errs), errs)

    def test_invalid_unknown_top_level_field_is_caught(self):
        # additionalProperties: false at the top level -> 'rawPayload' rejected.
        with tempfile.TemporaryDirectory() as d:
            _stage(d, {INVALID_UNKNOWN_FIELD: "raw-payload.evidence.json"})
            errs = v.check_evidence_schema(d)
            self.assertTrue(errs)
            self.assertTrue(any("rawPayload" in e for e in errs), errs)

    def test_skip_when_no_records_found(self):
        # Corpora that have not adopted evidence.v1 must SKIP (green), not fail
        # — the spec repo, website, and adopter corpora all run --checks all from main.
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(v.check_evidence_schema(d))

    def test_example_filenames_are_excluded(self):
        # '.example.' anywhere in the name is a golden fixture, never a record
        # — even when the suffix would otherwise match the discovery glob.
        with tempfile.TemporaryDirectory() as d:
            _stage(d, {INVALID_UNKNOWN_FIELD: "leak.example.evidence.json"})
            _stage(d, {INVALID_BAD_SHA: INVALID_BAD_SHA})  # spec-repo shape
            self.assertEqual(list(v.find_evidence_records(d)), [])
            self.assertIsNone(v.check_evidence_schema(d))

    def test_evidence_v1_suffix_is_discovered(self):
        with tempfile.TemporaryDirectory() as d:
            _stage(d, {VALID[1]: "minimal.evidence.v1.json"})
            self.assertEqual(len(list(v.find_evidence_records(d))), 1)
            self.assertEqual(v.check_evidence_schema(d), [])

    def test_invalid_json_is_an_error_not_a_crash(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "broken.evidence.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("{not json")
            errs = v.check_evidence_schema(d)
            self.assertEqual(len(errs), 1)
            self.assertIn("invalid JSON", errs[0])

    def test_frozen_dirs_are_skipped(self):
        # Same lifecycle-dir semantics as every other check (_SKIP_DIRS).
        with tempfile.TemporaryDirectory() as d:
            arch = os.path.join(d, "99-archive")
            os.makedirs(arch)
            _stage(arch, {INVALID_BAD_SHA: "old.evidence.json"})
            self.assertIsNone(v.check_evidence_schema(d))


class EvidenceStdlibFallback(_EvidenceCheckMixin, unittest.TestCase):
    """Force the documented stdlib subset (jsonschema import off)."""

    def setUp(self):
        self._orig = v._jsonschema
        v._jsonschema = None

    def tearDown(self):
        v._jsonschema = self._orig

    def test_fallback_names_the_missing_security_category(self):
        with tempfile.TemporaryDirectory() as d:
            _stage(d, {INVALID_NO_SECURITY: "no-security.evidence.json"})
            errs = v.check_evidence_schema(d)
            self.assertTrue(any("security" in e for e in errs), errs)

    def test_fallback_rejects_bad_extension_key_and_bad_enums(self):
        with open(os.path.join(_FIXTURES, VALID[1]), encoding="utf-8") as fh:
            rec = json.load(fh)
        rec["status"] = "great"                      # not in the enum
        rec["extensions"] = {"nodots": {}}           # not reverse-DNS
        rec["checks"][0]["severity"] = "fatal"       # not in the enum
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "mutated.evidence.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(rec, fh)
            errs = v.check_evidence_schema(d)
            joined = "\n".join(errs)
            self.assertIn("status", joined)
            self.assertIn("extensions key", joined)
            self.assertIn("severity", joined)


@unittest.skipUnless(v._jsonschema is not None,
                     "jsonschema not installed — full-mode tests run in the "
                     "with-optional-deps CI pass")
class EvidenceJsonschemaMode(_EvidenceCheckMixin, unittest.TestCase):
    """Full Draft 2020-12 validation via the real jsonschema library."""


class VendoredSchemaIdentity(unittest.TestCase):
    def test_vendored_schema_is_the_canonical_v1(self):
        # Byte-level sync with spec main is CI's job (sync gate); this pins the
        # semantic identity so a wrong vendored file cannot slip through tests.
        with open(v._EVIDENCE_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertEqual(
            schema["$id"],
            "https://sliceops.org/schemas/evidence/evidence.v1.schema.json")
        self.assertEqual(schema["properties"]["schemaVersion"]["const"],
                         "sliceops.evidence/v1")
        self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
