#!/usr/bin/env python3
"""Lightweight, data-driven utilities for the R1-R14 cell-fate workflow.

The CLI intentionally avoids claiming any result without input data. It consumes
plain TSV matrices/tables emitted by heavier tools such as scanpy, scVelo,
CellRank, chromVAR, Cicero, SCARlink, or SCENIC+.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd


def read_tsv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t")


def write_tsv(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)


def bh_fdr(p_values: list[float]) -> list[float]:
    n = len(p_values)
    order = np.argsort(p_values)
    ranked = np.empty(n, dtype=float)
    prev = 1.0
    for rank, idx in enumerate(order[::-1], start=1):
        true_rank = n - rank + 1
        val = min(prev, p_values[idx] * n / true_rank)
        ranked[idx] = val
        prev = val
    return ranked.tolist()


def orient_expression(expr: pd.DataFrame, signature_genes: set[str]) -> pd.DataFrame:
    """Return cells x genes expression table."""
    index_overlap = len(set(map(str, expr.index)) & signature_genes)
    col_overlap = len(set(map(str, expr.columns)) & signature_genes)
    if index_overlap > col_overlap:
        expr = expr.T
    return expr


def cmd_score_states(args: argparse.Namespace) -> None:
    expr = pd.read_csv(args.expression, sep="\t", index_col=0)
    signatures = read_tsv(args.signatures)
    gene_col = args.gene_col
    axis_col = args.axis_col
    sig_genes = set(signatures[gene_col].astype(str))
    expr = orient_expression(expr, sig_genes)
    expr = expr.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    if args.log_cpm:
        totals = expr.sum(axis=1).replace(0, np.nan)
        expr = np.log1p(expr.div(totals, axis=0).fillna(0.0) * 1_000_000.0)

    means = expr.mean(axis=0)
    stds = expr.std(axis=0, ddof=0).replace(0, np.nan)
    z = expr.sub(means, axis=1).div(stds, axis=1).fillna(0.0)

    score_rows = []
    missing_rows = []
    for axis, sub in signatures.groupby(axis_col):
        genes = [g for g in sub[gene_col].astype(str) if g in z.columns]
        missing = [g for g in sub[gene_col].astype(str) if g not in z.columns]
        missing_rows.append(
            {
                "state_axis": axis,
                "n_signature_genes": int(sub.shape[0]),
                "n_present_genes": len(genes),
                "missing_genes": ",".join(missing),
            }
        )
        if genes:
            score_rows.append(z[genes].mean(axis=1).rename(axis))
        else:
            score_rows.append(pd.Series(np.nan, index=z.index, name=axis))

    scores = pd.concat(score_rows, axis=1)
    scores.insert(0, "cell_id", scores.index.astype(str))
    score_cols = [c for c in scores.columns if c != "cell_id"]
    labels = pd.DataFrame(
        {
            "cell_id": scores["cell_id"],
            "dominant_state_axis": scores[score_cols].idxmax(axis=1),
            "dominant_state_score": scores[score_cols].max(axis=1),
            "evidence_status": "computed_from_expression_signature_scores",
        }
    )

    write_tsv(scores.reset_index(drop=True), f"{args.output_prefix}.state_scores.tsv")
    write_tsv(labels, f"{args.output_prefix}.state_labels.tsv")
    write_tsv(pd.DataFrame(missing_rows), f"{args.output_prefix}.signature_gene_coverage.tsv")


def cmd_transitions(args: argparse.Namespace) -> None:
    meta = read_tsv(args.metadata)
    required = {args.cell_col, args.state_col, args.time_col}
    missing = sorted(required - set(meta.columns))
    if missing:
        raise SystemExit(f"Missing columns in metadata: {missing}")
    group_cols = [c for c in [args.dataset_col, args.lineage_col] if c and c in meta.columns]
    states = sorted(meta[args.state_col].dropna().astype(str).unique())
    counts = pd.DataFrame(0, index=states, columns=states, dtype=int)
    edge_rows = []

    if group_cols:
        groups = meta.groupby(group_cols, dropna=False)
    else:
        groups = [(("all",), meta)]

    for group_key, sub in groups:
        sub = sub.dropna(subset=[args.state_col, args.time_col]).copy()
        sub[args.time_col] = pd.to_numeric(sub[args.time_col], errors="coerce")
        sub = sub.dropna(subset=[args.time_col]).sort_values(args.time_col)
        for i in range(len(sub) - 1):
            src = str(sub.iloc[i][args.state_col])
            dst = str(sub.iloc[i + 1][args.state_col])
            counts.loc[src, dst] += 1
            edge_rows.append(
                {
                    "group": "|".join(map(str, group_key if isinstance(group_key, tuple) else (group_key,))),
                    "from_cell": sub.iloc[i][args.cell_col],
                    "to_cell": sub.iloc[i + 1][args.cell_col],
                    "from_state": src,
                    "to_state": dst,
                    "from_time": sub.iloc[i][args.time_col],
                    "to_time": sub.iloc[i + 1][args.time_col],
                }
            )

    probs = counts.div(counts.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    matrix = probs.reset_index().rename(columns={"index": "from_state"})
    matrix["evidence_status"] = "computed_from_ordered_pseudotime_neighbors"
    write_tsv(matrix, f"{args.output_prefix}.transition_matrix.tsv")
    write_tsv(pd.DataFrame(edge_rows), f"{args.output_prefix}.transition_edges.tsv")


def permutation_p(x: np.ndarray, y: np.ndarray, n_perm: int, rng: np.random.Generator) -> float:
    n_x = len(x)
    if n_x == 0 or len(y) == 0:
        return math.nan
    observed = abs(float(np.nanmean(x) - np.nanmean(y)))
    pooled = np.concatenate([x, y])
    count = 1
    for _ in range(n_perm):
        rng.shuffle(pooled)
        stat = abs(float(np.nanmean(pooled[:n_x]) - np.nanmean(pooled[n_x:])))
        if stat >= observed:
            count += 1
    return count / (n_perm + 1)


def bootstrap_ci(x: np.ndarray, y: np.ndarray, n_boot: int, rng: np.random.Generator) -> tuple[float, float]:
    if len(x) == 0 or len(y) == 0:
        return math.nan, math.nan
    vals = []
    for _ in range(n_boot):
        xb = rng.choice(x, size=len(x), replace=True)
        yb = rng.choice(y, size=len(y), replace=True)
        vals.append(float(np.nanmean(xb) - np.nanmean(yb)))
    lo, hi = np.nanpercentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def cmd_r14_effects(args: argparse.Namespace) -> None:
    scores = read_tsv(args.state_scores)
    meta = read_tsv(args.metadata)
    if args.cell_col not in scores.columns or args.cell_col not in meta.columns:
        raise SystemExit(f"Both tables must contain cell column: {args.cell_col}")
    if args.perturb_col not in meta.columns:
        raise SystemExit(f"Metadata missing perturbation column: {args.perturb_col}")
    df = scores.merge(meta, on=args.cell_col, how="inner", validate="one_to_one")
    numeric_cols = []
    for c in scores.columns:
        if c == args.cell_col or not pd.api.types.is_numeric_dtype(scores[c]):
            continue
        if not pd.to_numeric(df[c], errors="coerce").dropna().empty:
            numeric_cols.append(c)
    if not numeric_cols:
        raise SystemExit("No numeric state score / probability columns found.")

    rng = np.random.default_rng(args.seed)
    rows = []
    control = df[df[args.perturb_col].astype(str) == str(args.control_label)]
    if control.empty:
        raise SystemExit(f"No control cells found for label: {args.control_label}")

    for perturbation, sub in df.groupby(args.perturb_col):
        perturbation = str(perturbation)
        if perturbation == str(args.control_label):
            continue
        for metric in numeric_cols:
            x = pd.to_numeric(sub[metric], errors="coerce").dropna().to_numpy(float)
            y = pd.to_numeric(control[metric], errors="coerce").dropna().to_numpy(float)
            effect = float(np.nanmean(x) - np.nanmean(y)) if len(x) and len(y) else math.nan
            ci_lo, ci_hi = bootstrap_ci(x, y, args.n_boot, rng)
            p_val = permutation_p(x.copy(), y.copy(), args.n_perm, rng)
            rows.append(
                {
                    "perturbation": perturbation,
                    "metric": metric,
                    "n_perturbed_cells": len(x),
                    "n_control_cells": len(y),
                    "mean_perturbed": float(np.nanmean(x)) if len(x) else math.nan,
                    "mean_control": float(np.nanmean(y)) if len(y) else math.nan,
                    "delta_vs_control": effect,
                    "bootstrap_ci_low": ci_lo,
                    "bootstrap_ci_high": ci_hi,
                    "permutation_p": p_val,
                }
            )

    out = pd.DataFrame(rows)
    if not out.empty:
        out["fdr_bh"] = bh_fdr(out["permutation_p"].fillna(1.0).tolist())
        out["sign_stable"] = (
            (out["bootstrap_ci_low"] > 0) & (out["bootstrap_ci_high"] > 0)
        ) | ((out["bootstrap_ci_low"] < 0) & (out["bootstrap_ci_high"] < 0))
        out["evidence_status"] = "computed_perturbation_effect_requires_design_review"
    write_tsv(out, args.output)


def cmd_grn_support(args: argparse.Namespace) -> None:
    edges = read_tsv(args.edges)
    support_cols = []
    if args.rna_effects:
        rna = read_tsv(args.rna_effects)
        if {"target", "metric"}.issubset(rna.columns):
            rna_support = rna.groupby("target").size().rename("rna_effect_support").reset_index()
            edges = edges.merge(rna_support, on="target", how="left")
            support_cols.append("rna_effect_support")
        elif "metric" in rna.columns and "state_axis" in edges.columns:
            filtered = rna.copy()
            if "fdr_bh" in filtered.columns:
                filtered = filtered[pd.to_numeric(filtered["fdr_bh"], errors="coerce") <= args.rna_fdr]
            if "sign_stable" in filtered.columns:
                filtered = filtered[filtered["sign_stable"].astype(str).str.lower().isin(["true", "1", "yes"])]
            state_support = (
                filtered.groupby("metric").size().rename("rna_state_effect_support").reset_index()
            )
            state_support = state_support.rename(columns={"metric": "state_axis"})
            edges = edges.merge(state_support, on="state_axis", how="left")
            support_cols.append("rna_state_effect_support")
    if args.motif:
        motif = read_tsv(args.motif)
        tf_col = args.motif_tf_col
        if tf_col in motif.columns:
            motif_support = motif.groupby(tf_col).size().rename("motif_support").reset_index()
            motif_support = motif_support.rename(columns={tf_col: "source"})
            edges = edges.merge(motif_support, on="source", how="left")
            support_cols.append("motif_support")
    if args.peak_gene:
        pg = read_tsv(args.peak_gene)
        if "target" in pg.columns:
            pg_support = pg.groupby("target").size().rename("peak_gene_support").reset_index()
            edges = edges.merge(pg_support, on="target", how="left")
            support_cols.append("peak_gene_support")

    for col in support_cols:
        edges[col] = edges[col].fillna(0).astype(int)
    if support_cols:
        edges["integrated_support_score"] = edges[support_cols].gt(0).sum(axis=1)
    else:
        edges["integrated_support_score"] = 0
    edges["evidence_status"] = np.where(
        edges["integrated_support_score"] > 0,
        "partially_supported_by_input_tables",
        "curated_prior_only",
    )
    write_tsv(edges, args.output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="R1-R14 cell-fate workflow utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("score-states", help="Compute cell-level state signature scores")
    p.add_argument("--expression", required=True, help="TSV expression matrix, cells x genes or genes x cells")
    p.add_argument("--signatures", required=True, help="Signature gene set TSV")
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--gene-col", default="human_symbol")
    p.add_argument("--axis-col", default="state_axis")
    p.add_argument("--log-cpm", action="store_true")
    p.set_defaults(func=cmd_score_states)

    p = sub.add_parser("transitions", help="Build pseudotime-neighbor state transition matrix")
    p.add_argument("--metadata", required=True)
    p.add_argument("--output-prefix", required=True)
    p.add_argument("--cell-col", default="cell_id")
    p.add_argument("--state-col", default="dominant_state_axis")
    p.add_argument("--time-col", default="pseudotime")
    p.add_argument("--dataset-col", default="dataset")
    p.add_argument("--lineage-col", default=None)
    p.set_defaults(func=cmd_transitions)

    p = sub.add_parser("r14-effects", help="Estimate perturbation effects on scores/probabilities")
    p.add_argument("--state-scores", required=True)
    p.add_argument("--metadata", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--cell-col", default="cell_id")
    p.add_argument("--perturb-col", default="perturbation")
    p.add_argument("--control-label", default="control")
    p.add_argument("--n-perm", type=int, default=1000)
    p.add_argument("--n-boot", type=int, default=1000)
    p.add_argument("--seed", type=int, default=7)
    p.set_defaults(func=cmd_r14_effects)

    p = sub.add_parser("grn-support", help="Integrate candidate GRN with RNA/motif/peak-gene support tables")
    p.add_argument("--edges", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--rna-effects")
    p.add_argument("--rna-fdr", type=float, default=0.1)
    p.add_argument("--motif")
    p.add_argument("--motif-tf-col", default="source")
    p.add_argument("--peak-gene")
    p.set_defaults(func=cmd_grn_support)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
