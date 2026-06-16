# Band Calibration Register

Living, versioned record of every band calibration. Each entry is one row — append-only. Drift over time is auditable; the script version and model-landscape lines make every calibration reproducible.

Schema:

| Label | Date | Dataset | Context-band percentiles | Token-band (billed-eq) percentiles | Model landscape | Script version | Proposed bands |
|---|---|---|---|---|---|---|---|

---

## v1 — baseline (2026-06-15)

| Field | Value |
|---|---|
| **Label** | baseline-v1 |
| **Date** | 2026-06-15 |
| **Dataset** | 258 sessions, 66,451 turns (aggregated all-Session-Types; per-type calibration deferred to next cycle once tagging is in place) |
| **Context-band percentiles (peak per-session footprint)** | p25=179K · p50=259K · p75=385K · p90=609K · p95=951K · max=1.0M |
| **Token-band billed-equivalent percentiles** | p25=2.8M · p50=5.2M · p75=9.4M · p90=30.6M |
| **Token-band net-new percentiles** | p25=965K · p50=1.7M · p75=3.5M · p90=10.7M |
| **Model landscape** | Frontier long-context (~1M, calibration model class) · Frontier peers (~1M+) · Claude-class (~200K) · GPT-class (~128K) · Local-medium (~32K) · Local-small (~8K) |
| **Script version** | v1 (this folder's `calibrate.py` at the time of the baseline) |
| **Proposed bands — context-band** | XS<32K · S 32–128K · M 128–200K · L 200–512K · XL>512K |
| **Proposed bands — token-band (billed-equivalent)** | XS<2M · S 2–5M · M 5–10M · L 10–20M · XL>20M |
| **Headline finding** | Median peak footprint 259K leads to **>50% of sessions exceed a 200K window**, which makes context-band the **primary filter** in Model Triage — empirically validated, not theoretical. Token-band M (5–10M) covers the median of real work. |
| **Caveat** | Aggregate sample — mixes all Session-Types. DEV-only bands are expected to skew smaller; per-type recalibration deferred until session-index tagging by Session-Type matures. |

---

## Recalibration log (append below — newest first)

<!-- Next entry goes above this comment; preserve as append-only. -->
