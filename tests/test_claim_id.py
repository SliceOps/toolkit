#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Regression tests for templates/counter-discipline/claim_id.py (DEC-0008.5
# rule 1: the P9 Shared-Resource Pre-flight, mechanized).
# Stdlib only (unittest + tempfile), Python 3.9+.

import importlib.util
import os
import tempfile
import threading
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_CLAIM_ID = os.path.join(_HERE, "..", "templates", "counter-discipline", "claim_id.py")
_spec = importlib.util.spec_from_file_location("claim_id", _CLAIM_ID)
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)


def _touch(root, relpath):
    path = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("")
    return path


class SequentialClaims(unittest.TestCase):
    def test_claims_increment_sequentially_from_empty_corpus(self):
        with tempfile.TemporaryDirectory() as d:
            claimed = [ci.claim(d, "SESS")[0] for _ in range(5)]
            self.assertEqual(claimed, [1, 2, 3, 4, 5])

    def test_claimed_id_is_zero_padded_min_four_digits_in_filename(self):
        with tempfile.TemporaryDirectory() as d:
            claimed, filename = ci.claim(d, "INS", date="20260712", slug="agent-drift")
            self.assertEqual(claimed, 1)
            self.assertEqual(filename, "INS-0001-20260712-agent-drift.md")

    def test_five_digit_counter_is_unpadded_beyond_minimum(self):
        with tempfile.TemporaryDirectory() as d:
            _touch(d, "insights/INS-9999-20260101-a.md")
            claimed, filename = ci.claim(d, "INS", date="20260712", slug="x")
            self.assertEqual(claimed, 10000)
            self.assertEqual(filename, "INS-10000-20260712-x.md")


class ReconciliationAgainstRealMax(unittest.TestCase):
    def test_reconciles_when_real_max_exceeds_counter_file(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".counters"))
            with open(os.path.join(d, ".counters", "ins.txt"), "w") as fh:
                fh.write("003\n")
            _touch(d, "insights/INS-0010-20260101-a.md")
            claimed, _ = ci.claim(d, "INS")
            self.assertEqual(claimed, 11)

    def test_reconciles_when_counter_file_exceeds_real_max(self):
        # A counter file may be AHEAD of what's on disk (a claim was made but
        # the artifact commit hasn't landed yet, or was made in a sibling
        # worktree) — the file's value must not be regressed.
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".counters"))
            with open(os.path.join(d, ".counters", "ins.txt"), "w") as fh:
                fh.write("0020\n")
            _touch(d, "insights/INS-0003-20260101-a.md")
            claimed, _ = ci.claim(d, "INS")
            self.assertEqual(claimed, 21)

    def test_scan_real_max_ignores_other_entities(self):
        with tempfile.TemporaryDirectory() as d:
            _touch(d, "decisions/DEC-0099-20260101-x.md")
            _touch(d, "insights/INS-0002-20260101-a.md")
            self.assertEqual(ci.scan_real_max(d, "INS"), 2)

    def test_scan_real_max_ignores_counters_directory_itself(self):
        # .counters/ins.txt must never be misread as an artifact filename.
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".counters"))
            with open(os.path.join(d, ".counters", "ins.txt"), "w") as fh:
                fh.write("0099\n")
            self.assertEqual(ci.scan_real_max(d, "INS"), 0)


class LifecycleInfix(unittest.TestCase):
    def test_dec_d_prefix_advances_the_shared_dec_counter(self):
        # DEC-0008.5 rule 3: one counter per entity, SHARED across lifecycle
        # prefixes — an existing DEC-D-0041 makes the next claim 0042.
        with tempfile.TemporaryDirectory() as d:
            _touch(d, "decisions/DEC-D-0041-20260101-deprecated.md")
            claimed, _ = ci.claim(d, "DEC")
            self.assertEqual(claimed, 42)

    def test_dec_p_prefix_advances_the_shared_dec_counter(self):
        with tempfile.TemporaryDirectory() as d:
            _touch(d, "decisions/DEC-P-0007-20260101-pending.md")
            claimed, _ = ci.claim(d, "DEC")
            self.assertEqual(claimed, 8)

    def test_mixed_lifecycle_prefixes_share_one_max(self):
        with tempfile.TemporaryDirectory() as d:
            _touch(d, "decisions/DEC-0003-20260101-a.md")
            _touch(d, "decisions/DEC-P-0005-20260101-b.md")
            _touch(d, "decisions/DEC-D-0002-20260101-c.md")
            claimed, _ = ci.claim(d, "DEC")
            self.assertEqual(claimed, 6)


class CountersDirCreation(unittest.TestCase):
    def test_creates_counters_dir_and_file_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(os.path.isdir(os.path.join(d, ".counters")))
            ci.claim(d, "CP")
            self.assertTrue(os.path.isfile(os.path.join(d, ".counters", "cp.txt")))
            with open(os.path.join(d, ".counters", "cp.txt")) as fh:
                self.assertEqual(fh.read().strip(), "0001")

    def test_lockfile_is_removed_after_a_successful_claim(self):
        with tempfile.TemporaryDirectory() as d:
            ci.claim(d, "GOAL")
            lock_path = ci.counter_file(d, "GOAL") + ".lock"
            self.assertFalse(os.path.exists(lock_path))


class Concurrency(unittest.TestCase):
    def test_concurrent_claims_are_gapless_and_unique(self):
        with tempfile.TemporaryDirectory() as d:
            results = []
            lock = threading.Lock()
            errors = []

            def worker():
                try:
                    claimed, _ = ci.claim(d, "FRAME")
                    with lock:
                        results.append(claimed)
                except Exception as e:  # pragma: no cover - failure diagnostic
                    with lock:
                        errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [])
            self.assertEqual(sorted(results), list(range(1, 13)))
            self.assertEqual(len(set(results)), 12)  # no duplicate claims


class CliValidation(unittest.TestCase):
    def _run(self, argv):
        import io
        import contextlib
        old_argv = ci.sys.argv
        ci.sys.argv = ["claim_id.py"] + argv
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    ci.main()
                except SystemExit as e:
                    return e.code, out.getvalue(), err.getvalue()
        finally:
            ci.sys.argv = old_argv
        return 0, out.getvalue(), err.getvalue()  # pragma: no cover

    def test_cli_prints_claimed_id(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = self._run(["--root", d, "--entity", "ins"])
            self.assertEqual(code, 0)
            self.assertEqual(out.strip(), "0001")

    def test_cli_prints_filename_when_slug_given(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = self._run(["--root", d, "--entity", "DEC", "--slug", "my-slug", "--date", "20260712"])
            self.assertEqual(code, 0)
            lines = out.strip().splitlines()
            self.assertEqual(lines, ["0001", "DEC-0001-20260712-my-slug.md"])

    def test_cli_rejects_uppercase_slug(self):
        with tempfile.TemporaryDirectory() as d:
            code, _, err = self._run(["--root", d, "--entity", "DEC", "--slug", "BadSlug"])
            self.assertEqual(code, 1)
            self.assertIn("kebab-case", err)

    def test_cli_rejects_bad_date_shape(self):
        with tempfile.TemporaryDirectory() as d:
            code, _, err = self._run(["--root", d, "--entity", "DEC", "--slug", "x", "--date", "2026-07-12"])
            self.assertEqual(code, 1)
            self.assertIn("YYYYMMDD", err)

    def test_cli_rejects_missing_root(self):
        code, _, err = self._run(["--root", "/nonexistent/path/xyz", "--entity", "DEC"])
        self.assertEqual(code, 1)
        self.assertIn("not a directory", err)

    def test_cli_lowercases_are_upcased_for_entity(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = self._run(["--root", d, "--entity", "cp"])
            self.assertEqual(code, 0)
            self.assertEqual(out.strip(), "0001")
            self.assertTrue(os.path.isfile(os.path.join(d, ".counters", "cp.txt")))


if __name__ == "__main__":
    unittest.main()
