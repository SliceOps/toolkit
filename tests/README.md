# tests/

Regression tests for the consistency validators (`templates/consistency-validators/validators.py`).

Stdlib only (`unittest` + `tempfile`), Python 3.9+ — no third-party deps, so the
suite runs anywhere the validators run. When the optional deps (PyYAML,
jsonschema) ARE installed, the suite additionally exercises the full-mode
paths (the jsonschema-mode test class self-skips without it; the fallback
paths are always tested by forcing the optional imports off). CI runs the
suite both ways.

```bash
python3 -m unittest discover -s tests -v
```

## Fixtures

`fixtures/evidence/` carries the spec repo's five golden evidence.v1 examples
(`reference/evidence/examples/`): the two **valid** ones renamed to
`*.evidence.json` so the real discovery glob picks them up (they double as the
toolkit's own live records for the CI self-application run), and the three
deliberately-**invalid** ones keeping their `*.evidence.v1.example.json` names
— `.example.` filenames are excluded from discovery by design, so they never
fail a corpus run. See `fixtures/evidence/README.md`.

## Why this exists

The 2026-06-19 recursive-dogfooding audit named this repo's central
contradiction: *"a validator toolkit with no test of its validators."* This
suite pins the documented false-positive fixes so they cannot silently regress,
and proves each check still catches the real defect:

| Behaviour pinned | Regression it guards |
|---|---|
| date-based slugs (`DEC-2026-…`, incl. lifecycle infix `DEC-D-…`) do not trip counter-atomicity | commit `883c391` |
| band sub-ranges (`P1-P3`) do not trip principle-count-coherence | commit `f46f1c2` |
| the clarifying/negation form does not trip band-unit | commit `e45c2a4` |
| the singular "Cognitive Entity" title does not trip entity-count | regex lookbehind |
| real collisions / wrong counts / missing Layer-1 fields are still caught | positive cases |
| evidence-schema: golden valid records pass, each golden invalid fails for its intended reason — in full-jsonschema AND stdlib-fallback modes | `test_evidence_schema.py` (v0.2.0) |
| evidence-schema: zero records → SKIPPED (green); `.example.` filenames never validated | spec-repo/brain CI safety (they run `--checks all` from toolkit main) |
