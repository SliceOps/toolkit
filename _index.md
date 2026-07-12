# _index.md — SliceOps Toolkit corpus index

Reserved-name infrastructure (DEC-0010): the map of where to look for what, so
no agent or human reads this repo wholesale. Loading chain: `README.md` (thin,
always loaded) → this file (small, says WHERE) → the exact path below.

## Route table

| Looking for… | Open |
|---|---|
| What's in this toolkit, how to use it | [`README.md`](README.md) |
| Naming validator (DEC-0008/0009/0010 enforcement, v2) | [`templates/naming-validator/README.md`](templates/naming-validator/README.md), [`templates/naming-validator/naming_validator.py`](templates/naming-validator/naming_validator.py) |
| Counter-discipline / claiming a new artifact id (P9 pre-flight) | [`templates/counter-discipline/claim_id.py`](templates/counter-discipline/claim_id.py) |
| Consistency validators (Layer 3, 10 checks incl. evidence.v1) | [`templates/consistency-validators/README.md`](templates/consistency-validators/README.md), [`templates/consistency-validators/validators.py`](templates/consistency-validators/validators.py) |
| CI guardrail templates (Layer B.2 levers) | [`templates/ci-guardrails/README.md`](templates/ci-guardrails/README.md) |
| LLM-inference-cost-economy workflow | [`templates/llm-ci-economy/README.md`](templates/llm-ci-economy/README.md) |
| Cost-ledger template | [`templates/cost-ledger/README.md`](templates/cost-ledger/README.md) |
| Token/context band calibration | [`calibration/README.md`](calibration/README.md), [`calibration/calibrate.py`](calibration/calibrate.py) |
| Regression tests for everything above | [`tests/README.md`](tests/README.md) |
| Contributing, code of conduct, security policy | [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), [`SECURITY.md`](SECURITY.md) |

Points, never copies (DEC-0010.3) — descriptions live at the destination, not here.
