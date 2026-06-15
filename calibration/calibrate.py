#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SliceOps Capa B.1 — Band calibration reference implementation.
#
# Determinism-over-Regeneration (B.2): a fixed deterministic script, written
# once and reused — NOT AI-regenerated per calibration. Same corpus + same
# script-version -> same bands.
#
# Inputs: a directory of session .jsonl files (one session per file; each
# line is a turn with a `usage` dict carrying input/cache_creation/cache_read/
# output token counts). The default layout matches AI coding agent platforms
# that emit per-session jsonl logs.
#
# Outputs:
#   - token-band percentiles (billed-equivalent + net-new) and proposed bands
#   - context-band percentiles (peak per-session footprint) and proposed bands
#   - a single-line summary line for the band-calibration-register
#
# Usage:
#   python3 calibrate.py --root <sessions-root> --label <baseline-or-recalibration-name>
#
# Stdlib only.

import argparse
import json
import os
import sys
from statistics import quantiles


# Billing weights — verify against the vendor's pricing card on each
# recalibration. These are the convention used by the SliceOps baseline.
W_CACHE_CREATION = 1.25
W_CACHE_READ = 0.10


def iter_session_files(root):
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".jsonl"):
                yield os.path.join(dirpath, f)


def session_metrics(path):
    """Return (peak_context, billed_eq_total, net_new_total, turns)."""
    peak_context = 0
    billed_eq = 0
    net_new = 0
    turns = 0
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                usage = rec.get("usage") or rec.get("message", {}).get("usage")
                if not isinstance(usage, dict):
                    continue
                turns += 1
                in_t = int(usage.get("input_tokens", 0) or 0)
                cc_t = int(usage.get("cache_creation_input_tokens", 0) or 0)
                cr_t = int(usage.get("cache_read_input_tokens", 0) or 0)
                out_t = int(usage.get("output_tokens", 0) or 0)

                # context-band: peak per-turn footprint
                context = in_t + cc_t + cr_t
                if context > peak_context:
                    peak_context = context

                # token-band billed-equivalent: cost-aligned throughput
                billed_eq += in_t + cc_t * W_CACHE_CREATION + cr_t * W_CACHE_READ + out_t
                # token-band net-new: new work (no cache_read)
                net_new += in_t + cc_t + out_t
    except OSError:
        return None
    if turns == 0:
        return None
    return peak_context, int(billed_eq), net_new, turns


def percentiles(values, points=(25, 50, 75, 90, 95)):
    if not values:
        return {p: 0 for p in points}
    qs = quantiles(values, n=100)
    return {p: int(qs[p - 1]) for p in points}


def propose_bands(p_context, p_billed):
    """Anchor proposed bands to canonical breakpoints (model windows + spec)."""
    context_bands = [
        ("XS", "<32K"), ("S", "32-128K"), ("M", "128-200K"),
        ("L", "200-512K"), ("XL", ">512K"),
    ]
    token_bands = [
        ("XS", "<2M"), ("S", "2-5M"), ("M", "5-10M"),
        ("L", "10-20M"), ("XL", ">20M"),
    ]
    return {"context-band": context_bands, "token-band": token_bands}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="root of session .jsonl files")
    ap.add_argument("--label", default="recalibration",
                    help="label for the calibration register entry")
    ap.add_argument("--model-landscape", default="(unspecified)",
                    help="snapshot of model classes/windows at calibration time")
    args = ap.parse_args()

    contexts, billeds, netnews, turncounts = [], [], [], []
    n_sessions = 0
    for path in iter_session_files(args.root):
        m = session_metrics(path)
        if not m:
            continue
        n_sessions += 1
        c, b, nn, t = m
        contexts.append(c)
        billeds.append(b)
        netnews.append(nn)
        turncounts.append(t)

    if n_sessions == 0:
        print(f"::error::no sessions found under {args.root}", file=sys.stderr)
        sys.exit(2)

    p_ctx = percentiles(contexts)
    p_billed = percentiles(billeds)
    p_netnew = percentiles(netnews)

    print(f"Label: {args.label}")
    print(f"Sessions: {n_sessions}  Turns: {sum(turncounts)}")
    print(f"Model landscape: {args.model_landscape}")
    print()
    print("context-band peak footprint (tokens):")
    for p, v in p_ctx.items():
        print(f"  p{p:>2}: {v:>10}")
    print()
    print("token-band billed-equivalent (tokens):")
    for p, v in p_billed.items():
        print(f"  p{p:>2}: {v:>12}")
    print()
    print("token-band net-new (tokens, no cache_read):")
    for p, v in p_netnew.items():
        print(f"  p{p:>2}: {v:>12}")
    print()
    bands = propose_bands(p_ctx, p_billed)
    print("Proposed bands (anchored to canonical breakpoints + observed distribution):")
    for axis, bs in bands.items():
        print(f"  {axis}: {', '.join(f'{n}{r}' for n, r in bs)}")
    print()
    print("Register one-line summary (copy into band-calibration-register.md):")
    print(
        f"  | {args.label} | N={n_sessions} sessions, {sum(turncounts)} turns "
        f"| ctx p50={p_ctx[50]} p75={p_ctx[75]} p90={p_ctx[90]} "
        f"| billed p50={p_billed[50]} p75={p_billed[75]} p90={p_billed[90]} "
        f"| landscape: {args.model_landscape} |"
    )


if __name__ == "__main__":
    main()
