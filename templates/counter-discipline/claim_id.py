#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SliceOps Layer B.1 — counter-discipline: the P9 Shared-Resource Pre-flight,
# mechanized (DEC-0008.5 rule 1: "every corpus REQUIRES the .counters/
# discipline: re-scan the real max before claiming").
#
# Root-caused by the INS-006 collision incident (parallel chats independently
# created INS-003 + HANDOFF-011): a counter FILE alone can drift from the
# corpus's real max (an artifact created out-of-band, a merge from another
# branch, a human editing by hand). This tool never trusts the counter file in
# isolation — it re-scans the corpus for the real max on every claim,
# reconciles the two, and only then claims max+1, atomically.
#
# Usage:
#   python3 claim_id.py --root <corpus-root> --entity <PREFIX> [--slug <kebab-slug>] [--date YYYYMMDD]
#
# Examples:
#   python3 claim_id.py --root . --entity DEC
#     -> 0011
#   python3 claim_id.py --root . --entity INS --slug agent-drift-observed
#     -> 0014
#     -> INS-0014-20260712-agent-drift-observed.md
#
# Exit codes: 0 = claimed · 1 = error (bad args, lock never released, I/O failure).
# Stdlib only (3.9+), OS-agnostic. Determinism-over-Regeneration (B.2): the
# reconciliation rule is fixed and deterministic — same corpus state -> same
# claimed id (mod the atomic increment itself, which is the point).

import argparse
import errno
import os
import re
import sys
import time

# Grammar per DEC-0008.5: PREFIX-NNNN-YYYYMMDD-slug.md, minimum 4-digit
# zero-padded counter, unbounded above. The DEC lifecycle infix (-P-/-D-)
# shares ONE counter across lifecycle states (DEC-0008.5 rule 3): a new
# DEC-0008 colliding with an existing DEC-D-0008 is a detected error, so the
# infix is stripped before the counter is read — never treated as a separate
# per-lifecycle sequence.
COUNTER_IN_NAME = re.compile(r"^([A-Z]+)(?:-[PD])?-0*(\d+)-")

MIN_WIDTH = 4
EXCLUDE_DIRS = {".git", ".github", ".obsidian", ".wrangler", ".claude", ".worktrees",
                ".stversions", "node_modules", "build", "dist", "public",
                "99-archive", "archive", "_meta", "__MACOSX"}

LOCK_RETRY_DELAY_S = 0.05
LOCK_RETRY_ATTEMPTS = 40  # ~2s worst case — brief per the task spec, not a long poll


def scan_real_max(root, entity):
    """Re-scan the corpus for the real max claimed number for `entity`
    (P9 pre-flight — never trust the counter file alone). Walks .counters/
    itself too? No: .counters/ holds bookkeeping files (ins.txt, dec.txt),
    never artifact filenames, so excluding it from the artifact walk is
    correct — .counters/ is read separately, explicitly, below."""
    real_max = 0
    for dirpath, dirnames, filenames in os.walk(root):
        parts = set(os.path.normpath(dirpath).split(os.sep))
        if parts & EXCLUDE_DIRS or ".counters" in parts:
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and d != ".counters"]
            continue
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if not f.endswith(".md"):
                continue
            m = COUNTER_IN_NAME.match(f)
            if m and m.group(1) == entity:
                real_max = max(real_max, int(m.group(2)))
    return real_max


def counters_dir(root):
    return os.path.join(root, ".counters")


def counter_file(root, entity):
    return os.path.join(counters_dir(root), entity.lower() + ".txt")


def read_counter_file(path):
    if not os.path.isfile(path):
        return 0
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read().strip()
    except OSError:
        return 0
    m = re.match(r"^0*(\d+)", text)
    return int(m.group(1)) if m else 0


class LockTimeout(Exception):
    pass


class _CounterLock:
    """A simple os.O_CREAT|O_EXCL lockfile alongside the counter file, with
    brief retries. Exclusive create is atomic on every OS this toolkit
    targets (POSIX and Windows both honor O_EXCL); no third-party lock
    library needed for a single-host claim (multi-host coordination is out of
    scope for a stdlib-only per-corpus tool — the corpus itself, via git,
    is the multi-host merge point)."""

    def __init__(self, path):
        self.lock_path = path + ".lock"
        self._fd = None

    def __enter__(self):
        for attempt in range(LOCK_RETRY_ATTEMPTS):
            try:
                self._fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, str(os.getpid()).encode("utf-8"))
                return self
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                time.sleep(LOCK_RETRY_DELAY_S)
        raise LockTimeout(
            f"could not acquire lock {self.lock_path} after "
            f"{LOCK_RETRY_ATTEMPTS * LOCK_RETRY_DELAY_S:.1f}s — a stale lock from a "
            f"crashed process? remove it by hand if so, then retry.")

    def __exit__(self, exc_type, exc, tb):
        if self._fd is not None:
            os.close(self._fd)
        try:
            os.remove(self.lock_path)
        except OSError:
            pass
        return False


def _atomic_write(path, text):
    """write temp + os.replace — the write itself is atomic on POSIX and
    Windows (os.replace uses ReplaceFile / MoveFileEx with the replace flag);
    the .lock guard above serializes CONCURRENT claims, this makes each
    individual write crash-safe (no torn/partial counter file)."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = None, None
    try:
        fd, tmp = __import__("tempfile").mkstemp(dir=d, prefix=".tmp-counter-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        fd = None  # fdopen closed it
        os.replace(tmp, path)
        tmp = None
    finally:
        if fd is not None:
            os.close(fd)
        if tmp is not None and os.path.exists(tmp):
            os.remove(tmp)


def claim(root, entity, date=None, slug=None):
    """Runs the full P9 pre-flight + atomic claim. Returns (claimed_int, filename_or_None)."""
    cdir = counters_dir(root)
    os.makedirs(cdir, exist_ok=True)
    cfile = counter_file(root, entity)

    with _CounterLock(cfile):
        real_max = scan_real_max(root, entity)
        file_max = read_counter_file(cfile)
        # Reconcile: use the GREATER of the two (a parallel claim may have
        # advanced the file past what's on disk as artifacts yet, e.g. a
        # claim made moments ago whose file isn't created yet; conversely an
        # artifact may exist that never went through this tool).
        base = max(real_max, file_max)
        claimed = base + 1
        _atomic_write(cfile, str(claimed).zfill(MIN_WIDTH) + "\n")

    filename = None
    if slug is not None:
        date8 = date or time.strftime("%Y%m%d")
        filename = f"{entity}-{str(claimed).zfill(MIN_WIDTH)}-{date8}-{slug}.md"
    return claimed, filename


def main():
    ap = argparse.ArgumentParser(
        description="SliceOps counter-discipline — claim the next id for an entity "
                     "under the DEC-0008.5 universal grammar (P9 pre-flight, mechanized).")
    ap.add_argument("--root", required=True, metavar="PATH", help="corpus root to scan and claim within")
    ap.add_argument("--entity", required=True, metavar="PREFIX",
                    help="entity prefix, e.g. DEC, INS, CP, GOAL, CONC, FRAME, PRI, OUTC, CAP, REL, PREF, VAL, SESS")
    ap.add_argument("--slug", metavar="SLUG", help="kebab-case slug; if given, also prints the full filename")
    ap.add_argument("--date", metavar="YYYYMMDD", help="creation date, compact form (default: today)")
    args = ap.parse_args()

    entity = args.entity.strip().upper()
    if not re.match(r"^[A-Z]+$", entity):
        print(f"claim_id: --entity must be letters only (e.g. DEC, INS, CP) — got '{args.entity}'", file=sys.stderr)
        sys.exit(1)
    if args.slug is not None and not re.match(r"^[a-z0-9][a-z0-9-]*$", args.slug):
        print(f"claim_id: --slug must be kebab-case lowercase (DEC-0008.5 rule 4) — got '{args.slug}'", file=sys.stderr)
        sys.exit(1)
    if args.date is not None and not re.match(r"^\d{8}$", args.date):
        print(f"claim_id: --date must be YYYYMMDD (8 digits, compact) — got '{args.date}'", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(args.root):
        print(f"claim_id: --root '{args.root}' is not a directory", file=sys.stderr)
        sys.exit(1)

    try:
        claimed, filename = claim(args.root, entity, args.date, args.slug)
    except LockTimeout as e:
        print(f"claim_id: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"claim_id: I/O error claiming the counter: {e}", file=sys.stderr)
        sys.exit(1)

    print(str(claimed).zfill(MIN_WIDTH))
    if filename:
        print(filename)
    sys.exit(0)


if __name__ == "__main__":
    main()
