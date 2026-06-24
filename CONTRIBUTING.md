# Contributing to the SliceOps™ Toolkit

This repository is the **code and tooling layer** of SliceOps (consistency
validators, CI-guardrail templates, the band-calibration script). It is public and
open to contributions; every pull request requires maintainer approval before merge
(P3 — Human-in-the-Loop Authority).

The binding legal terms (license scope, trademark separation, the contribution
license) live in the SliceOps specification repository and are authoritative there:
[`governance/IPR_POLICY.md`](https://github.com/SliceOps/spec/blob/main/governance/IPR_POLICY.md).

By opening a pull request you agree to both of the following:

1. **Contribution license — Inbound = Outbound.** This repository's code is licensed
   under the **MIT License** ([`LICENSE`](LICENSE)); your contribution is licensed the
   same way. Contributing grants no trademark rights.
2. **Developer Certificate of Origin (DCO).** You certify that you have the right to
   submit the contribution, by signing off your commits.

## Sign off your commits (DCO)

SliceOps uses the **Developer Certificate of Origin 1.1** (full text in [`DCO`](DCO))
instead of a Contributor License Agreement. Sign off every commit with `-s`:

```
git commit -s -m "Your message"
```

This appends a line certifying the DCO:

```
Signed-off-by: Your Name <you@example.com>
```

Use a real name and email. Every commit in a pull request must be signed off, and no
CLA is required.

## Workflow

1. **Fork** the repository and **branch** off `main` (`feat/<slug>` or `fix/<slug>`).
2. Keep it **atomic: one slice, one pull request** (P4). Declare the scope in the
   pull-request description.
3. The tooling is **stdlib-only Python 3 (3.9+)** with no dependencies. Run the tests
   in [`tests/`](tests/) before opening a pull request.
4. Code files carry an `SPDX-License-Identifier: MIT` header; keep it on new files.
5. A maintainer must approve before merge (P3). AI-assisted contributions are welcome
   but reviewed by a human first; critical changes are never auto-merged.

## Changes to the framework itself

A change to a principle, a reference pattern, or canonical vocabulary belongs in the
**spec**, through its RFC process, not here. See
[SliceOps/spec](https://github.com/SliceOps/spec).

## Code of conduct

All participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## References

- [`LICENSE`](LICENSE) — MIT License (this repository's code).
- [`DCO`](DCO) — Developer Certificate of Origin 1.1.
- [IPR_POLICY](https://github.com/SliceOps/spec/blob/main/governance/IPR_POLICY.md) — binding IP and contribution terms (authoritative, in the spec).
- [TRADEMARK](https://github.com/SliceOps/spec/blob/main/TRADEMARK.md) and [DISCLOSURE](https://github.com/SliceOps/spec/blob/main/DISCLOSURE.md) — trademark usage and framework-neutrality policy (in the spec).
