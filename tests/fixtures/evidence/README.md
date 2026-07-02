# evidence.v1 test fixtures

Byte-copies of the five golden examples in
[sliceops-spec `reference/evidence/examples/`](https://github.com/SliceOps/spec/tree/main/reference/evidence/examples)
(canonical schema ratified `DR-2026-07-02-evidence-v1-canonical-schema`).
Do not edit them here — re-copy from the spec if the golden set changes.

Naming is deliberate (and load-bearing for the toolkit's own CI):

| Fixture | Named | Why |
|---|---|---|
| `valid-full-slice-merge.evidence.json` | **renamed** to the real record glob | Discovered by `check_evidence_schema` — doubles as a live record for the toolkit's CI self-application run (it must validate). |
| `valid-minimal-gated-operation.evidence.json` | **renamed** to the real record glob | Same. |
| `invalid-*.evidence.v1.example.json` (×3) | original spec names kept | `.example.` filenames are excluded from discovery by design — these are deliberately INVALID and must never be picked up as records by any corpus run (toolkit self-run, spec repo, website, brain). Tests copy them into temp dirs under record names to prove each fails for its intended reason. |

All hashes in the fixtures are the spec's fake repeated-digit placeholders.
