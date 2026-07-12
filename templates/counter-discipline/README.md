# Counter Discipline — Layer B.1 (`claim_id.py`)

Mechanizes the **P9 Shared-Resource Pre-flight** for the DEC-0008.5 universal
ID grammar (`PREFIX-NNNN-YYYYMMDD-slug.md`): re-scan the corpus for the real
max claimed number before handing out the next one, reconcile it against the
`.counters/` bookkeeping file, and claim atomically.

Root-caused by the INS-006 collision incident (parallel chats independently
claimed the same insight and handoff ids): a counter file trusted in isolation
drifts from the corpus's real state — an artifact created out-of-band, a
merge from another branch or worktree, a human editing by hand. `claim_id.py`
never trusts the counter file alone; every claim re-derives the real max from
the files on disk first.

Stdlib-only Python 3 (3.9+), no dependencies, OS-agnostic.

## Usage

```bash
python3 claim_id.py --root <corpus-root> --entity <PREFIX> [--slug <kebab-slug>] [--date YYYYMMDD]
```

- `--root` — the corpus root to scan and claim within (same root a `.counters/` directory lives at).
- `--entity` — the entity prefix: `DEC`, `INS`, `OUTC`, `CAP`, `GOAL`, `CONC`, `FRAME`, `CP`, `PRI`, `REL`, `PREF`, `VAL`, `SESS` (the DEC-0008.2.1 catalog; case-insensitive input, always upper-cased).
- `--slug` (optional) — kebab-case slug. When given, the tool also prints the full filename under the universal grammar.
- `--date` (optional) — compact `YYYYMMDD`; defaults to today.

```console
$ python3 claim_id.py --root . --entity DEC
0011

$ python3 claim_id.py --root . --entity INS --slug agent-drift-observed
0014
INS-0014-20260712-agent-drift-observed.md
```

Exit codes: `0` claimed · `1` error (bad arguments, or the lock could not be
acquired — see below).

## What it does, step by step

1. **Re-scan** every `.md` file under `--root` (excluding `.git`, `99-archive`,
   `.counters/` itself, and the usual build/VCS noise) for the highest number
   already claimed for `--entity`, matching `^PREFIX(-[PD])?-0*(\d+)-`. The DEC
   lifecycle infix (`-P-`/`-D-`) is stripped before reading the number — **one
   counter is shared across lifecycle states** (DEC-0008.5 rule 3): an
   existing `DEC-D-0041` makes the next claim `0042`, not a fresh `0001` in
   some separate deprecated-only sequence.
2. **Reconcile** against `.counters/<prefix-lowercase>.txt` (created, along
   with the `.counters/` directory itself, if missing) — takes the **greater**
   of the real scanned max and the counter file's value, so neither a stale
   file nor an artifact-not-yet-committed can regress the count.
3. **Claim** `max + 1` and write it back to the counter file **atomically**:
   a `os.O_CREAT | os.O_EXCL` lockfile (`<counter-file>.lock`) serializes
   concurrent claims with brief retries (≈2s worst case before giving up with
   exit 1 and a clear message pointing at a possible stale lock from a
   crashed process); the write itself goes to a temp file in the same
   directory, then `os.replace()`s it into place, so a crash mid-write never
   leaves a torn counter file.
4. **Print** the claimed id, zero-padded to the DEC-0008.5 minimum of 4
   digits (unbounded above — `9999` → `10000` → …), and if `--slug` was
   given, the full filename.

This tool checks nothing about the SHAPE of the rest of the filename or
frontmatter — that is [`../naming-validator/`](../naming-validator/)'s job.
Use them together: claim the id here, then write the file, then let the
naming-validator pre-write hook confirm the shape at the point of write.

## Design posture

Single-host, single-corpus scope by design: multi-host coordination is the
corpus's own merge point (git) — this tool does not attempt distributed
locking across machines. If two machines claim concurrently against
divergent local clones, the collision surfaces as a git merge conflict on the
counter file (or a duplicate filename), which the corpus's normal review
process catches — the same class of conflict counter discipline has always
relied on humans/CI to resolve, now made rarer, not eliminated, by the
narrower single-process race this tool closes.
