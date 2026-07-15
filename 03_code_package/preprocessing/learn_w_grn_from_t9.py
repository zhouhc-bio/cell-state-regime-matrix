#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


OUT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of/outputs")
OUT.mkdir(parents=True, exist_ok=True)

BASE = Path("/Volumes/T9/PGCS/publication/mechanistic_validation_20260605")

INPUTS = {
    "perturbation_pgcs_validation": BASE / "perturbation_validation/perturbation_pgcs_validation.tsv",
    "gse221321_top_effects": BASE / "perturbation_validation/gse221321_pgcs_top_perturbation_effects.tsv",
    "chromvar_gse239276": BASE / "source_data/gse239276_chromvar_motif_pgcs_associations.tsv",
    "chromvar_gse140203": BASE / "source_data/gse140203_chromvar_motif_pgcs_associations.tsv",
    "peak_gene_gse239276": BASE / "source_data/gse239276_peak_level_peak_gene_associations.tsv",
    "same_cell_peak_gene_gse239276": BASE / "source_data/gse239276_same_cell_peak_gene_links.tsv",
    "crossmodal_gse239276": BASE / "source_data/gse239276_crossmodal_axis_associations.tsv",
    "target_annotation": BASE / "perturbation_validation/target_annotation.tsv",
    "gse216909_pgcs_targets": BASE / "causal_validation/gse216909_pgcs_target_guides.tsv",
    "gse153596_terminal_probabilities": Path("/Volumes/T9/最终投稿包_有序归档/06_处理后数据与统计输出/图源表与统计表/statistical_outputs/gse153596_cellrank_terminal_probabilities.tsv"),
    "gse153596_transition_matrix": Path("/Volumes/T9/最终投稿包_有序归档/06_处理后数据与统计输出/图源表与统计表/statistical_outputs/gse153596_velocity_transition_matrix.tsv"),
}

AXIS_TO_STATE = {
    "P": "Stemness_or_plasticity",
    "G": "PC_score_or_positional_program",
    "S": "Fate_lock_or_senescence",
    "C": "Transitional_or_chromatin_control",
}

MODULE_PATTERNS = [
    ("RA_module", re.compile(r"^(RAR[ABG]?|RXR[ABG]?|ALDH1A[123]|CYP26[ABC]1?|HOX[A-D]?[0-9]+|MEIS[123]?|PBX[1234]?)$", re.I)),
    ("BMP_module", re.compile(r"^(BMP[0-9A-Z]*|BMPR[0-9A-Z]*|SMAD[0-9A-Z]*|ID[0-9A-Z]*|GDF15)$", re.I)),
    ("NOTCH_module", re.compile(r"^(NOTCH[0-9]*|RBPJ|HES[0-9A-Z]*|HEY[0-9A-Z]*|DLL[0-9A-Z]*|JAG[0-9A-Z]*)$", re.I)),
    ("FGF_SHH_module", re.compile(r"^(FGF[0-9A-Z]*|FGFR[0-9A-Z]*|SHH|GLI[0-9A-Z]*|PTCH[0-9A-Z]*|ETV[0-9A-Z]*|SPRY[0-9A-Z]*|DUSP6)$", re.I)),
    ("WNT_stemness_module", re.compile(r"^(WNT[0-9A-Z]*|CTNNB1|TCF7|TCF7L2|LEF1|MYC|KLF4|LGR5|AXIN2)$", re.I)),
    ("p53_Rb_fate_lock_module", re.compile(r"^(TP53|CDKN1A|CDKN2A|RB1|MDM2|E2F[0-9A-Z]*|SERPINE1|GADD45A)$", re.I)),
    ("chromatin_regulator_module", re.compile(r"^(EZH2|SUZ12|EED|ARID[0-9A-Z]*|SMARCA[0-9A-Z]*|KMT[0-9A-Z]*|BMI1|BPTF|EP300|CREBBP)$", re.I)),
]


def clean_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    return df


def read_table(path: Path) -> pd.DataFrame:
    return clean_cols(pd.read_csv(path, sep="\t", encoding="utf-8-sig", low_memory=False))


def module_for_gene(gene: str) -> str:
    g = str(gene).strip().upper()
    for mod, pat in MODULE_PATTERNS:
        if pat.match(g):
            return mod
    return "other_or_unassigned"


def infer_perturbation_mode(row: pd.Series) -> tuple[str, str]:
    text = " ".join(str(row.get(c, "")) for c in ["sample", "member_label", "dataset_id", "target_gene"])
    low = text.lower()
    if any(x in low for x in ["ko", "kd", "sg", "crispr", "guide"]):
        return "loss_of_function", "native_weight = - observed_delta"
    if any(x in low for x in ["oe", "overexpression", "activation", "crispra"]):
        return "gain_of_function", "native_weight = observed_delta"
    return "unknown_direction", "native_weight = observed_delta; sign is perturbation-response direction"


def native_weight(delta: float, mode: str) -> float:
    if mode == "loss_of_function":
        return -delta
    return delta


def sign_label(x: float) -> str:
    if x > 0:
        return "activation_positive"
    if x < 0:
        return "repression_negative"
    return "zero"


def safe_float(x, default=np.nan) -> float:
    try:
        return float(x)
    except Exception:
        return default


def weighted_mean(vals: pd.Series, weights: pd.Series) -> float:
    v = pd.to_numeric(vals, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce").fillna(1.0)
    mask = v.notna() & w.notna() & (w > 0)
    if not mask.any():
        return float(v.mean())
    return float(np.average(v[mask], weights=w[mask]))


def aggregate_gene_state_edges(pgcs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pgcs = pgcs.copy()
    for col in ["mean_difference", "q_value_bh", "p_value", "n_target_cells", "n_control_cells"]:
        if col in pgcs.columns:
            pgcs[col] = pd.to_numeric(pgcs[col], errors="coerce")
    pgcs["target_gene"] = pgcs["target_gene"].astype(str).str.upper()
    pgcs["output_axis"] = pgcs["output_axis"].astype(str).str.upper()
    pgcs["module"] = pgcs["target_gene"].map(module_for_gene)
    modes = pgcs.apply(infer_perturbation_mode, axis=1, result_type="expand")
    pgcs["perturbation_mode"] = modes[0]
    pgcs["sign_inference_rule"] = modes[1]
    pgcs["native_weight_row"] = [
        native_weight(delta, mode)
        for delta, mode in zip(pgcs["mean_difference"].fillna(0.0), pgcs["perturbation_mode"])
    ]
    pgcs["n_cells_total"] = pgcs["n_target_cells"].fillna(0) + pgcs["n_control_cells"].fillna(0)
    pgcs["significant_row"] = pgcs["q_value_bh"].fillna(1.0) <= 0.05

    rows = []
    for (gene, axis), sub in pgcs.groupby(["target_gene", "output_axis"], dropna=False):
        if not gene or not axis or axis == "NAN":
            continue
        weight = weighted_mean(sub["native_weight_row"], sub["n_cells_total"])
        observed_delta = weighted_mean(sub["mean_difference"], sub["n_cells_total"])
        rows.append(
            {
                "source": gene,
                "target": f"STATE_AXIS:{axis}",
                "target_type": "state_axis",
                "output_axis": axis,
                "state_interpretation": AXIS_TO_STATE.get(axis, "unmapped_axis"),
                "module": module_for_gene(gene),
                "observed_perturbation_delta": observed_delta,
                "inferred_native_weight": weight,
                "sign": sign_label(weight),
                "n_observations": int(sub.shape[0]),
                "n_datasets": int(sub["dataset_id"].nunique()) if "dataset_id" in sub.columns else "",
                "n_samples": int(sub["sample"].nunique()) if "sample" in sub.columns else "",
                "min_q_value_bh": float(sub["q_value_bh"].min(skipna=True)),
                "mean_abs_effect": float(sub["mean_difference"].abs().mean(skipna=True)),
                "any_FDR_0_05": bool(sub["significant_row"].any()),
                "supporting_datasets": ";".join(sorted(map(str, sub["dataset_id"].dropna().unique()))) if "dataset_id" in sub.columns else "",
                "evidence_source": "perturbation_pgcs_validation.tsv",
                "evidence_type": "perturbation_to_state_axis_response",
                "sign_inference_rule": ";".join(sorted(set(sub["sign_inference_rule"]))),
            }
        )
    edges = pd.DataFrame(rows)
    if edges.empty:
        return edges, pgcs
    abs_nonzero = edges["inferred_native_weight"].abs()
    threshold = max(0.005, float(abs_nonzero.quantile(0.75)) if len(abs_nonzero) else 0.005)
    edges["sparse_selected"] = (edges["any_FDR_0_05"]) & (edges["inferred_native_weight"].abs() >= threshold)
    edges["sparsity_threshold_abs_weight"] = threshold
    return edges, pgcs


def aggregate_gene_gene_edges(top: pd.DataFrame) -> pd.DataFrame:
    top = top.copy()
    top["Perturbed_gene"] = top["Perturbed_gene"].astype(str).str.upper()
    top["Downstream_gene"] = top["Downstream_gene"].astype(str).str.upper()
    top["Log_fold_change"] = pd.to_numeric(top["Log_fold_change"], errors="coerce")
    top["qvalue"] = pd.to_numeric(top["qvalue"], errors="coerce")
    top["module"] = top["Perturbed_gene"].map(module_for_gene)
    top["downstream_module"] = top["Downstream_gene"].map(module_for_gene)
    top["perturbation_mode"] = top.apply(lambda r: infer_perturbation_mode(r)[0], axis=1)
    top["native_weight_row"] = [native_weight(d, m) for d, m in zip(top["Log_fold_change"].fillna(0.0), top["perturbation_mode"])]
    rows = []
    for (src, dst), sub in top.groupby(["Perturbed_gene", "Downstream_gene"], dropna=False):
        if not src or not dst or src == "NAN" or dst == "NAN":
            continue
        weight = float(sub["native_weight_row"].mean(skipna=True))
        observed_delta = float(sub["Log_fold_change"].mean(skipna=True))
        rows.append(
            {
                "source": src,
                "target": dst,
                "target_type": "gene",
                "output_axis": ";".join(sorted(set(str(x) for x in sub.get("downstream_axes", pd.Series(dtype=str)).dropna() if str(x) and str(x) != "nan"))),
                "state_interpretation": "",
                "module": module_for_gene(src),
                "observed_perturbation_delta": observed_delta,
                "inferred_native_weight": weight,
                "sign": sign_label(weight),
                "n_observations": int(sub.shape[0]),
                "n_datasets": 1,
                "n_samples": "",
                "min_q_value_bh": float(sub["qvalue"].min(skipna=True)),
                "mean_abs_effect": float(sub["Log_fold_change"].abs().mean(skipna=True)),
                "any_FDR_0_05": bool((sub["qvalue"].fillna(1.0) <= 0.05).any()),
                "supporting_datasets": "GSE221321",
                "evidence_source": "gse221321_pgcs_top_perturbation_effects.tsv",
                "evidence_type": "perturbation_to_downstream_gene_response",
                "sign_inference_rule": "native_weight = - observed_delta for KO/KD/loss-of-function member_label",
            }
        )
    edges = pd.DataFrame(rows)
    if edges.empty:
        return edges
    threshold = max(0.05, float(edges["inferred_native_weight"].abs().quantile(0.80)))
    edges["sparse_selected"] = (edges["min_q_value_bh"] <= 0.05) & (edges["inferred_native_weight"].abs() >= threshold)
    edges["sparsity_threshold_abs_weight"] = threshold
    return edges


def add_chromatin_support(edges: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    edges = edges.copy()
    edges["chromvar_support"] = False
    edges["peak_gene_support"] = False
    edges["crossmodal_support"] = False

    motifs = []
    for name in ["chromvar_gse239276", "chromvar_gse140203"]:
        df = tables.get(name)
        if df is None or df.empty:
            continue
        df = df.copy()
        df["BH_FDR"] = pd.to_numeric(df.get("BH_FDR"), errors="coerce")
        df["pgcs_axis"] = df.get("pgcs_axis", "").astype(str).str.upper()
        df["motif_group"] = df.get("motif_group", "").astype(str)
        motifs.append(df[df["BH_FDR"] <= 0.05])
    motif_df = pd.concat(motifs, ignore_index=True) if motifs else pd.DataFrame()

    peak_genes = set()
    for name in ["peak_gene_gse239276", "same_cell_peak_gene_gse239276"]:
        df = tables.get(name)
        if df is None or df.empty:
            continue
        df = df.copy()
        df["BH_FDR"] = pd.to_numeric(df.get("BH_FDR"), errors="coerce")
        if "gene_symbol" in df.columns:
            peak_genes |= set(df.loc[df["BH_FDR"] <= 0.05, "gene_symbol"].astype(str).str.upper())

    cross = tables.get("crossmodal_gse239276")
    cross_axes = set()
    if cross is not None and not cross.empty:
        cross = cross.copy()
        cross["BH_FDR"] = pd.to_numeric(cross.get("BH_FDR"), errors="coerce")
        cross_axes = set(cross.loc[cross["BH_FDR"] <= 0.05, "axis"].astype(str).str.upper())

    def motif_support(row: pd.Series) -> bool:
        if motif_df.empty:
            return False
        axis = str(row.get("output_axis", "")).upper()
        mod = str(row.get("module", ""))
        if not axis or axis == "NAN":
            return False
        motif_group_hint = {
            "RA_module": "RA",
            "BMP_module": "BMP",
            "NOTCH_module": "NOTCH",
            "FGF_SHH_module": "FGF|SHH|GLI|ETV",
            "WNT_stemness_module": "WNT|TCF",
            "p53_Rb_fate_lock_module": "P53|TP53|RB|E2F",
        }.get(mod, "")
        if not motif_group_hint:
            return False
        sub = motif_df[motif_df["pgcs_axis"] == axis]
        return sub["motif_group"].str.contains(motif_group_hint, case=False, regex=True, na=False).any()

    edges["chromvar_support"] = edges.apply(motif_support, axis=1)
    edges["peak_gene_support"] = edges["target"].astype(str).str.upper().isin(peak_genes) | edges["source"].astype(str).str.upper().isin(peak_genes)
    edges["crossmodal_support"] = edges["output_axis"].astype(str).str.upper().isin(cross_axes)
    edges["support_score"] = edges[["chromvar_support", "peak_gene_support", "crossmodal_support", "any_FDR_0_05"]].astype(bool).sum(axis=1)
    edges["empirical_edge_status"] = np.where(edges["sparse_selected"], "learned_sparse_edge", "measured_but_not_sparse_selected")
    return edges


def correlation(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 2:
        return math.nan
    x = x[mask]
    y = y[mask]
    sx, sy = x.std(), y.std()
    if sx == 0 or sy == 0:
        return math.nan
    return float(np.corrcoef(x, y)[0, 1])


def metrics(df: pd.DataFrame, observed_col="mean_difference", pred_col="predicted_delta") -> dict[str, float]:
    obs = pd.to_numeric(df[observed_col], errors="coerce").to_numpy(float)
    pred = pd.to_numeric(df[pred_col], errors="coerce").to_numpy(float)
    mask = np.isfinite(obs) & np.isfinite(pred)
    if mask.sum() == 0:
        return {"n": 0, "mae": math.nan, "rmse": math.nan, "pearson_r": math.nan, "sign_accuracy": math.nan}
    obs, pred = obs[mask], pred[mask]
    return {
        "n": int(mask.sum()),
        "mae": float(np.mean(np.abs(obs - pred))),
        "rmse": float(np.sqrt(np.mean((obs - pred) ** 2))),
        "pearson_r": correlation(obs, pred),
        "sign_accuracy": float(np.mean(np.sign(obs) == np.sign(pred))),
    }


def make_prediction_tables(pgcs_rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pgcs_rows.copy()
    df["module"] = df["target_gene"].map(module_for_gene)
    df["mean_difference"] = pd.to_numeric(df["mean_difference"], errors="coerce")
    df = df.dropna(subset=["mean_difference", "output_axis", "target_gene"])

    global_axis = df.groupby("output_axis")["mean_difference"].mean().to_dict()

    predictions = []
    # Leave-one-perturbation-out: hold target gene.
    for gene, held in df.groupby("target_gene"):
        train = df[df["target_gene"] != gene]
        module_axis = train.groupby(["module", "output_axis"])["mean_difference"].mean().to_dict()
        gene_module = module_for_gene(gene)
        for _, row in held.iterrows():
            axis = row["output_axis"]
            pred = module_axis.get((gene_module, axis), global_axis.get(axis, train["mean_difference"].mean()))
            predictions.append(
                {
                    "validation_type": "leave_one_perturbation_out",
                    "heldout_unit": gene,
                    "dataset_id": row.get("dataset_id", ""),
                    "sample": row.get("sample", ""),
                    "target_gene": gene,
                    "module": gene_module,
                    "output_axis": axis,
                    "observed_delta": row["mean_difference"],
                    "predicted_delta": pred,
                    "prediction_source": "training module-axis mean; fallback global axis mean",
                }
            )

    # Dataset holdout.
    if "dataset_id" in df.columns:
        for ds, held in df.groupby("dataset_id"):
            train = df[df["dataset_id"] != ds]
            if train.empty:
                continue
            module_axis = train.groupby(["module", "output_axis"])["mean_difference"].mean().to_dict()
            train_global_axis = train.groupby("output_axis")["mean_difference"].mean().to_dict()
            for _, row in held.iterrows():
                axis = row["output_axis"]
                mod = row["module"]
                pred = module_axis.get((mod, axis), train_global_axis.get(axis, train["mean_difference"].mean()))
                predictions.append(
                    {
                        "validation_type": "dataset_holdout",
                        "heldout_unit": ds,
                        "dataset_id": row.get("dataset_id", ""),
                        "sample": row.get("sample", ""),
                        "target_gene": row["target_gene"],
                        "module": mod,
                        "output_axis": axis,
                        "observed_delta": row["mean_difference"],
                        "predicted_delta": pred,
                        "prediction_source": "training module-axis mean; fallback training global axis mean",
                    }
                )

    pred_df = pd.DataFrame(predictions)
    report_rows = []
    if not pred_df.empty:
        for val_type, sub in pred_df.groupby("validation_type"):
            m = metrics(sub, "observed_delta", "predicted_delta")
            report_rows.append({"validation_type": val_type, "heldout_unit": "all", **m})
        for (val_type, unit), sub in pred_df.groupby(["validation_type", "heldout_unit"]):
            m = metrics(sub, "observed_delta", "predicted_delta")
            report_rows.append({"validation_type": val_type, "heldout_unit": unit, **m})

    # Pathway ablation: compare full module-axis predictor with module-ablated global-axis predictor.
    full = df.groupby(["module", "output_axis"])["mean_difference"].transform("mean")
    axis_only = df.groupby("output_axis")["mean_difference"].transform("mean")
    ab = df[["dataset_id", "sample", "target_gene", "module", "output_axis", "mean_difference"]].copy()
    ab["predicted_delta"] = full
    full_m = metrics(ab, "mean_difference", "predicted_delta")
    ab["predicted_delta"] = axis_only
    ablated_m = metrics(ab, "mean_difference", "predicted_delta")
    report_rows.append({"validation_type": "pathway_ablation_test", "heldout_unit": "module_axis_predictor", **full_m})
    report_rows.append({"validation_type": "pathway_ablation_test", "heldout_unit": "axis_only_after_module_ablation", **ablated_m})
    return pred_df, pd.DataFrame(report_rows)


def write_svg_scatter(pred_df: pd.DataFrame, path: Path) -> None:
    df = pred_df[pred_df["validation_type"] == "leave_one_perturbation_out"].copy()
    if df.empty:
        path.write_text("<svg xmlns='http://www.w3.org/2000/svg' width='600' height='400'></svg>\n")
        return
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["observed_delta", "predicted_delta"])
    obs = pd.to_numeric(df["observed_delta"], errors="coerce")
    pred = pd.to_numeric(df["predicted_delta"], errors="coerce")
    lim = max(float(np.nanmax(np.abs(obs))), float(np.nanmax(np.abs(pred))), 0.01)
    w, h, pad = 720, 560, 70
    def sx(x): return pad + (float(x) + lim) / (2 * lim) * (w - 2 * pad)
    def sy(y): return h - pad - (float(y) + lim) / (2 * lim) * (h - 2 * pad)
    colors = {"P": "#2c7fb8", "G": "#41ab5d", "S": "#b8322c", "C": "#756bb1"}
    elems = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>",
        "<rect width='100%' height='100%' fill='#f8fafc'/>",
        f"<text x='{w/2}' y='32' text-anchor='middle' font-family='Arial' font-size='20' fill='#111827'>Predicted vs observed ΔS</text>",
        f"<line x1='{pad}' y1='{h-pad}' x2='{w-pad}' y2='{pad}' stroke='#64748b' stroke-width='1.5' stroke-dasharray='5 5'/>",
        f"<line x1='{pad}' y1='{sy(0)}' x2='{w-pad}' y2='{sy(0)}' stroke='#cbd5e1'/>",
        f"<line x1='{sx(0)}' y1='{pad}' x2='{sx(0)}' y2='{h-pad}' stroke='#cbd5e1'/>",
    ]
    sample = df.sample(min(len(df), 1200), random_state=7) if len(df) > 1200 else df
    for _, row in sample.iterrows():
        axis = str(row["output_axis"])
        elems.append(f"<circle cx='{sx(row['observed_delta'])}' cy='{sy(row['predicted_delta'])}' r='3' fill='{colors.get(axis, '#334155')}' opacity='0.55'/>")
    elems.extend([
        f"<text x='{w/2}' y='{h-22}' text-anchor='middle' font-family='Arial' font-size='13' fill='#334155'>observed perturbation ΔS</text>",
        f"<text transform='translate(20,{h/2}) rotate(-90)' text-anchor='middle' font-family='Arial' font-size='13' fill='#334155'>predicted ΔS</text>",
        "</svg>",
    ])
    path.write_text("\n".join(elems) + "\n", encoding="utf-8")


def write_svg_heatmap(edges: pd.DataFrame, path: Path) -> None:
    st = edges[(edges["target_type"] == "state_axis") & (edges["sparse_selected"])].copy()
    if st.empty:
        path.write_text("<svg xmlns='http://www.w3.org/2000/svg' width='600' height='400'></svg>\n")
        return
    top_genes = (
        st.assign(absw=st["inferred_native_weight"].abs())
        .groupby("source")["absw"].max()
        .sort_values(ascending=False)
        .head(40)
        .index.tolist()
    )
    axes = ["P", "G", "S", "C"]
    mat = st[st["source"].isin(top_genes)].pivot_table(index="source", columns="output_axis", values="inferred_native_weight", aggfunc="mean").reindex(top_genes).reindex(columns=axes)
    cell, left, top = 28, 160, 70
    w, h = left + cell * len(axes) + 80, top + cell * len(top_genes) + 80
    maxv = max(float(np.nanmax(np.abs(mat.to_numpy()))), 0.001)
    def color(v):
        if pd.isna(v):
            return "#e5e7eb"
        a = min(abs(float(v)) / maxv, 1.0)
        if v >= 0:
            return f"rgb({int(255 - 80*a)},{int(245 - 120*a)},{int(235 - 180*a)})"
        return f"rgb({int(235 - 170*a)},{int(245 - 120*a)},{int(255 - 80*a)})"
    elems = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>",
        "<rect width='100%' height='100%' fill='#f8fafc'/>",
        f"<text x='{w/2}' y='32' text-anchor='middle' font-family='Arial' font-size='20'>Learned sparse gene→state W_GRN</text>",
    ]
    for j, axis in enumerate(axes):
        elems.append(f"<text x='{left + j*cell + cell/2}' y='{top-12}' text-anchor='middle' font-family='Arial' font-size='12'>{axis}</text>")
    for i, gene in enumerate(top_genes):
        y = top + i * cell
        elems.append(f"<text x='{left-8}' y='{y+18}' text-anchor='end' font-family='Arial' font-size='11'>{gene}</text>")
        for j, axis in enumerate(axes):
            v = mat.loc[gene, axis] if axis in mat.columns else np.nan
            elems.append(f"<rect x='{left+j*cell}' y='{y}' width='{cell-1}' height='{cell-1}' fill='{color(v)}' stroke='#ffffff'/>")
    elems.append("</svg>")
    path.write_text("\n".join(elems) + "\n", encoding="utf-8")


def write_svg_graph(edges: pd.DataFrame, path: Path) -> None:
    graph = edges[edges["sparse_selected"]].copy()
    graph["target_bucket"] = np.where(
        graph["target_type"] == "state_axis",
        graph["target"].astype(str),
        "GENE_MODULE:" + graph["target"].astype(str).map(module_for_gene),
    )
    module_graph = (
        graph.groupby(["module", "target_bucket"], dropna=False)
        .agg(
            inferred_native_weight=("inferred_native_weight", "mean"),
            n_edges=("edge_id", "count"),
            mean_abs_weight=("inferred_native_weight", lambda x: float(np.mean(np.abs(x)))),
        )
        .reset_index()
    )
    module_graph["sign"] = module_graph["inferred_native_weight"].map(sign_label)
    module_graph = module_graph.sort_values("mean_abs_weight", ascending=False)
    module_graph.to_csv(OUT / "W_GRN_learned_module_graph.tsv", sep="\t", index=False)

    modules = list(dict.fromkeys(module_graph["module"].tolist()))
    targets = list(dict.fromkeys(module_graph["target_bucket"].tolist()))
    w, h = 1120, max(660, 120 + 46 * max(len(modules), len(targets)))
    module_y = {m: 95 + i * ((h - 180) / max(len(modules)-1, 1)) for i, m in enumerate(modules)}
    target_y = {t: 95 + i * ((h - 180) / max(len(targets)-1, 1)) for i, t in enumerate(targets)}
    colors = {"activation_positive": "#b8322c", "repression_negative": "#2c7fb8", "zero": "#64748b"}
    elems = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>",
        "<rect width='100%' height='100%' fill='#f8fafc'/>",
        f"<text x='{w/2}' y='34' text-anchor='middle' font-family='Arial' font-size='20'>Empirically learned signed sparse W_GRN module graph</text>",
        "<defs><marker id='arrow' markerWidth='8' markerHeight='8' refX='7' refY='3' orient='auto'><path d='M0,0 L8,3 L0,6 Z' fill='#475569'/></marker></defs>",
    ]
    for m, y in module_y.items():
        elems.append(f"<rect x='45' y='{y-20}' width='245' height='40' rx='6' fill='#e2e8f0' stroke='#334155'/>")
        elems.append(f"<text x='167' y='{y+5}' text-anchor='middle' font-family='Arial' font-size='11'>{m}</text>")
    for t, y in target_y.items():
        fill = "#dbeafe" if t.startswith("STATE_AXIS") else "#dcfce7"
        elems.append(f"<rect x='{w-330}' y='{y-20}' width='285' height='40' rx='6' fill='{fill}' stroke='#334155'/>")
        label = t.replace("GENE_MODULE:", "GENE:")
        elems.append(f"<text x='{w-188}' y='{y+5}' text-anchor='middle' font-family='Arial' font-size='11'>{label}</text>")
    maxw = max(float(module_graph["mean_abs_weight"].max()), 0.001) if not module_graph.empty else 0.001
    counts = defaultdict(int)
    for _, row in module_graph.iterrows():
        sy = module_y.get(row["module"], 300)
        ty = target_y.get(row["target_bucket"], 300)
        offset = (counts[(row["module"], row["target_bucket"])] % 9 - 4) * 3
        counts[(row["module"], row["target_bucket"])] += 1
        width = 0.8 + 4.2 * float(row["mean_abs_weight"]) / maxw
        color = colors.get(row["sign"], "#475569")
        elems.append(f"<path d='M290 {sy+offset} C470 {sy+offset}, 650 {ty-offset}, {w-330} {ty-offset}' fill='none' stroke='{color}' stroke-width='{width:.2f}' opacity='0.55' marker-end='url(#arrow)'/>")
    elems.append(f"<text x='{w/2}' y='{h-24}' text-anchor='middle' font-family='Arial' font-size='12' fill='#475569'>blue = inferred repression; red = inferred activation; edge width = mean |native weight|; node targets aggregate sparse empirical edges</text>")
    elems.append("</svg>")
    path.write_text("\n".join(elems) + "\n", encoding="utf-8")


def df_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "No validation metrics available."
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            val = row[c]
            if isinstance(val, float):
                vals.append("" if math.isnan(val) else f"{val:.4g}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> int:
    missing = [str(p) for p in INPUTS.values() if not p.exists()]
    if missing:
        raise SystemExit("Missing input files:\n" + "\n".join(missing))

    tables = {k: read_table(v) for k, v in INPUTS.items() if v.suffix.lower() in {".tsv", ".csv"} or v.name.endswith(".tsv")}
    pgcs = tables["perturbation_pgcs_validation"]
    top = tables["gse221321_top_effects"]

    state_edges, pgcs_rows = aggregate_gene_state_edges(pgcs)
    gene_edges = aggregate_gene_gene_edges(top)
    all_edges = pd.concat([state_edges, gene_edges], ignore_index=True, sort=False)
    all_edges = add_chromatin_support(all_edges, tables)
    all_edges["edge_id"] = [f"WGRN_{i:06d}" for i in range(1, len(all_edges) + 1)]
    first_cols = ["edge_id", "source", "target", "target_type", "module", "output_axis", "state_interpretation", "inferred_native_weight", "sign", "observed_perturbation_delta", "sparse_selected", "support_score", "chromvar_support", "peak_gene_support", "crossmodal_support", "min_q_value_bh", "n_observations", "supporting_datasets", "evidence_source", "evidence_type", "sign_inference_rule"]
    rest = [c for c in all_edges.columns if c not in first_cols]
    all_edges[first_cols + rest].to_csv(OUT / "W_GRN_learned.tsv", sep="\t", index=False)
    all_edges[all_edges["sparse_selected"]][first_cols + rest].to_csv(OUT / "W_GRN_learned_sparse_edges.tsv", sep="\t", index=False)

    state_matrix = state_edges.pivot_table(index="source", columns="output_axis", values="inferred_native_weight", aggfunc="mean").reset_index()
    state_matrix.to_csv(OUT / "W_GRN_learned_state_axis_matrix.tsv", sep="\t", index=False)

    pred_df, acc_df = make_prediction_tables(pgcs_rows)
    pred_df.to_csv(OUT / "predicted_vs_observed_deltaS.tsv", sep="\t", index=False)
    acc_df.to_csv(OUT / "prediction_accuracy_report.tsv", sep="\t", index=False)

    manifest_rows = []
    for name, path in INPUTS.items():
        manifest_rows.append({"input_name": name, "path": str(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else ""})
    pd.DataFrame(manifest_rows).to_csv(OUT / "W_GRN_learning_input_manifest.tsv", sep="\t", index=False)

    write_svg_scatter(pred_df, OUT / "predicted_vs_observed_deltaS.svg")
    write_svg_heatmap(all_edges, OUT / "perturbation_reconstruction_plot.svg")
    write_svg_graph(all_edges, OUT / "W_GRN_learned_graph.svg")

    sparse = all_edges[all_edges["sparse_selected"]]
    summary = pd.DataFrame([
        {"metric": "total_empirical_edges_measured", "value": len(all_edges)},
        {"metric": "sparse_selected_edges", "value": len(sparse)},
        {"metric": "sparse_state_axis_edges", "value": int(((sparse["target_type"] == "state_axis")).sum())},
        {"metric": "sparse_gene_gene_edges", "value": int(((sparse["target_type"] == "gene")).sum())},
        {"metric": "modules_observed", "value": ";".join(sorted(sparse["module"].dropna().unique()))},
        {"metric": "input_perturbation_rows", "value": len(pgcs_rows)},
        {"metric": "input_gse221321_gene_gene_rows", "value": len(top)},
    ])
    summary.to_csv(OUT / "W_GRN_learning_summary.tsv", sep="\t", index=False)

    acc_text = df_to_markdown(acc_df)
    md = f"""# Data-Driven W_GRN Learning Report

## Empirical Status

`W_GRN` has been replaced by an empirical signed edge table learned from perturbation-derived response data on T9. No manually specified regulatory weights were used for edge weights.

## Inputs

- Perturbation-to-state responses: `{INPUTS['perturbation_pgcs_validation']}`
- Gene-to-gene perturbation responses: `{INPUTS['gse221321_top_effects']}`
- chromVAR motif-state support: GSE239276 and GSE140203 chromVAR association tables
- Peak-gene support: GSE239276 same-cell peak-gene association tables
- Transition consistency context: GSE153596 CellRank terminal probabilities and velocity transition matrix

## Sign Rule

For KO/KD/sgRNA/loss-of-function perturbations, native regulatory weight is inferred as `- observed perturbation delta`. For unknown perturbation direction, the row is retained as perturbation-response direction and marked in `sign_inference_rule`.

## Outputs

- `W_GRN_learned.tsv`
- `W_GRN_learned_sparse_edges.tsv`
- `W_GRN_learned_state_axis_matrix.tsv`
- `W_GRN_learned_graph.svg`
- `predicted_vs_observed_deltaS.tsv`
- `predicted_vs_observed_deltaS.svg`
- `perturbation_reconstruction_plot.svg`
- `prediction_accuracy_report.tsv`

## Cross-Validation Summary

{acc_text}

## Guardrail

The learned matrix is empirical for the available T9 perturbation artifacts. It does not imply that unavailable GSE90546 or GSE195467 data were processed in this run.
"""
    (OUT / "prediction_accuracy_report.md").write_text(md, encoding="utf-8")

    system_md = """# Updated Dynamical System With Learned W_GRN

The governing system is now:

```text
dS/dt = W_GRN_data · S + B(U) + biological_feedback(S) + xi(S)
```

where `W_GRN_data` is the sparse signed empirical edge table in `W_GRN_learned_sparse_edges.tsv`.

Biological interpretation:

- `source` is the perturbed regulator or inferred upstream gene.
- `target` is either a downstream gene or a measured PGCS state axis.
- `inferred_native_weight` is the signed learned coupling.
- `module` assigns each learned edge to RA, BMP, NOTCH, FGF/SHH, WNT/stemness, p53/Rb fate-lock, chromatin regulator, or unassigned modules.
- `support_score` records independent support from perturbation significance, chromVAR motif association, peak-gene linkage, and crossmodal RNA/ATAC consistency.

This system treats `W_GRN_data` as a measured object rather than a symbolic matrix. Bifurcation and stochastic transition analyses must use this learned matrix or a declared subset of it.
"""
    (OUT / "updated_full_dynamical_system_definition.md").write_text(system_md, encoding="utf-8")

    print("W_GRN learning complete")
    print(f"total_edges={len(all_edges)}")
    print(f"sparse_edges={len(sparse)}")
    print(OUT / "W_GRN_learned.tsv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
