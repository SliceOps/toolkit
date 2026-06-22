# tests/

Regression tests for the consistency validators (`templates/consistency-validators/validators.py`).

Stdlib only (`unittest` + `tempfile`), Python 3.9+ — no third-party deps, so the
suite runs anywhere the validators run.

```bash
python3 -m unittest discover -s tests -v
```

## Why this exists

The 2026-06-19 recursive-dogfooding audit named this repo's central
contradiction: *"a validator toolkit with no test of its validators."* This
suite pins the documented false-positive fixes so they cannot silently regress,
and proves each check still catches the real defect:

| Behaviour pinned | Regression it guards |
|---|---|
| date-based slugs (`DR-2026-…`) do not trip counter-atomicity | commit `883c391` |
| band sub-ranges (`P1-P3`) do not trip principle-count-coherence | commit `f46f1c2` |
| the clarifying/negation form does not trip band-unit | commit `e45c2a4` |
| the singular "Cognitive Entity" title does not trip entity-count | regex lookbehind |
| real collisions / wrong counts / missing Layer-1 fields are still caught | positive cases |
