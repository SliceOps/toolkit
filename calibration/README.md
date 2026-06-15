# Calibration — band-calibration tooling

Reference implementation of the **Band Calibration discipline** (Capa B.1). The *specification* lives in the SliceOps spec (`reference/sizing/`); this folder is the *executable starter*.

## Files

| File | Role |
|---|---|
| `calibrate.py` | Deterministic Python script: parses a directory of session `.jsonl` files → percentiles → proposed bands. Stdlib only. Determinism-over-Regeneration (B.2). |
| `band-calibration-register.md` | The living, versioned register of every calibration (the audit trail). |

## Why deterministic

Calibration is not stochastic AI generation — it is reproducible measurement. Same corpus + same script version + same weights = same percentiles = same proposed bands. The script is written **once and reused** (Determinism-over-Regeneration); ad-hoc calibration scripts are an anti-pattern (they drift, they cannot be re-run for comparison, they break audit).

## Usage

```bash
python3 calibrate.py \
  --root <directory-of-session-jsonl-files> \
  --label "<baseline-or-recalibration-name>" \
  --model-landscape "<snapshot of model classes/windows at the time>"
```

The script prints percentiles + proposed bands + a single-line summary suitable for copy-paste into `band-calibration-register.md`.

## Where session corpora come from

Most AI coding agent platforms emit per-session `.jsonl` logs (one file per session; one record per turn) including a `usage` dict (input / cache_creation / cache_read / output token counts). Point `--root` at whichever directory tree your platform writes them into. Adopters that use a different log format adapt `session_metrics()` — the **measurement model** (peak per-turn footprint for context-band; weighted billed-equivalent throughput for token-band) is the canonical part.

## Cadence

Quarterly (every ~3–4 months), or immediately when the model landscape changes materially (e.g., local-model class jumps from 32K to 128K mainstream; frontier class crosses ~2M). Calibration hooks into the **Quarterly Curation Ritual** (Layer 6 of the consistency-management mechanism) — it is a Layer 6 item, not a new ritual.

## Vendor billing weights

The two cache weights — `cache_creation × 1.25` and `cache_read × 0.10` — match the canonical vendor pricing convention used for the SliceOps baseline. **Verify against the vendor's pricing card on each recalibration.** If the vendor changes weights or a different vendor is used, update the constants at the top of `calibrate.py` and record the change in the register entry (the script-version + landscape line make it auditable).
