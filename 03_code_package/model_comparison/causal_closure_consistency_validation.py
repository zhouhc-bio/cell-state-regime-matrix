#!/usr/bin/env python3
"""Perturbation-consistent causal closure audit for the locked latent-state-regime model.

This script is a validation/audit layer only. It does not retrain W_GRN, does
not refit the mixture model, and does not create synthetic perturbations.
"""

from __future__ import annotations

import math
from pathlib import Path
from textwrap import wrap

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
T9 = Path("/Volumes/T9/PGCS/publication/mechanistic_validation_20260605")

CELL_SCORES = T9 / "perturbation_validation" / "perturbation_cell_pgcs_scores.tsv"
PARAMS = OUT / "latent_regime_mixture_parameters.tsv"
W_AXIS = OUT / "W_GRN_learned_state_axis_matrix.tsv"
W_SPARSE = OUT / "W_GRN_learned_sparse_edges.tsv"
PRED_OBS = OUT / "predicted_vs_observed_deltaS.tsv"

RNG = np.random.default_rng(20260619)

LOCKED_REGIMES = [
    "adult_repair",
    "embryonic_reactivation",
    "salamander_blastema",
    "salamander_intact",
]

STATE_DIMS = ["Stemness", "Transitional", "Fate_lock", "Embryonic_module_score"]

SCORE_TO_STATE = {
    "P_score": "Stemness",
    "C_score": "Transitional",
    "S_score": "Fate_lock",
    "G_score": "Embryonic_module_score",
}

AXIS_TO_STATE = {
    "P": "Stemness",
    "C": "Transitional",
    "S": "Fate_lock",
    "G": "Embryonic_module_score",
}

PATHWAY_DEFS = {
    "RA": {
        "genes": ["RARA", "RARG", "RXRA", "RXRB", "RXRG", "PBX3", "PBX1", "ALDH1A2", "CYP26A1", "HOXA1", "HOXA9", "HOXB1"],
        "expected_alias": "embryonic_blastema_like",
        "expected_rule": "RA activation should increase embryonic/blastema-like posterior mass",
        "member_role": "canonical_activator_or_cofactor",
    },
    "BMP": {
        "genes": ["BMP4", "BMP7", "BMPR1A", "BMPR2", "SMAD1", "SMAD2", "SMAD3", "SMAD4", "SMAD5", "ID1", "ID2", "ID3"],
        "expected_alias": "fate_lock",
        "expected_rule": "BMP activation should increase fate-lock posterior mass",
        "member_role": "canonical_activator_or_downstream_effector",
    },
    "NOTCH": {
        "genes": ["NOTCH1", "NOTCH2", "RBPJ", "HES1", "HEY1"],
        "expected_alias": "transitional",
        "expected_rule": "NOTCH activation should increase transitional posterior mass",
        "member_role": "canonical_activator_or_downstream_effector",
    },
    "FGF": {
        "genes": ["FGF8", "FGFR1", "FGFR2", "ETV4", "ETV5", "ETV6", "DUSP6"],
        "expected_alias": "stemness_like",
        "expected_rule": "FGF activation should increase stemness/plasticity posterior mass",
        "member_role": "partial_proxy_downstream_effector",
    },
    "SHH": {
        "genes": ["SHH", "PTCH1", "SMO", "GLI1", "GLI2", "GLIS1"],
        "expected_alias": "stemness_like",
        "expected_rule": "SHH activation should increase stemness/plasticity posterior mass",
        "member_role": "partial_proxy_downstream_effector",
    },
}

# Unique aliases over the locked four-component mixture. This is an output
# readout transform only; the locked latent-state-regime model itself is not changed.
ALIAS_TO_LOCKED = {
    "stemness_like": "salamander_intact",
    "transitional": "adult_repair",
    "fate_lock": "embryonic_reactivation",
    "embryonic_blastema_like": "salamander_blastema",
}


def require_inputs():
    required = [CELL_SCORES, PARAMS, W_AXIS, W_SPARSE, PRED_OBS]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing required locked dry-lab inputs:\n" + "\n".join(missing))


def clean_gene(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("\ufeff", "", regex=False).str.strip().str.upper()


def load_mixture_params() -> pd.DataFrame:
    params = pd.read_csv(PARAMS, sep="\t")
    params["latent_regime"] = params["latent_regime"].astype(str)
    params = params.set_index("latent_regime").loc[LOCKED_REGIMES].reset_index()
    return params


def posterior_from_state(x: np.ndarray, params: pd.DataFrame) -> np.ndarray:
    """Diagonal Gaussian posterior using locked mixture parameters."""
    means = params[[f"mean_{d}" for d in STATE_DIMS]].to_numpy(float)
    vars_ = params[[f"variance_{d}" for d in STATE_DIMS]].to_numpy(float)
    vars_ = np.maximum(vars_, 1e-8)
    weights = params["mixture_weight"].to_numpy(float)
    logp = []
    for k in range(len(params)):
        diff = x - means[k]
        lp = math.log(max(weights[k], 1e-12)) - 0.5 * (
            np.sum((diff * diff) / vars_[k], axis=1)
            + np.sum(np.log(2 * np.pi * vars_[k]))
        )
        logp.append(lp)
    logp = np.vstack(logp).T
    logp -= logp.max(axis=1, keepdims=True)
    p = np.exp(logp)
    p /= p.sum(axis=1, keepdims=True)
    return p


def load_and_project_cells(params: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    usecols = [
        "cell_id", "dataset_id", "sample", "target_gene",
        "P_score", "G_score", "S_score", "C_score",
    ]
    cells = pd.read_csv(CELL_SCORES, sep="\t", usecols=usecols)
    cells["target_gene"] = clean_gene(cells["target_gene"])
    for col in ["P_score", "G_score", "S_score", "C_score"]:
        cells[col] = pd.to_numeric(cells[col], errors="coerce")
    cells = cells.dropna(subset=["P_score", "G_score", "S_score", "C_score"]).copy()

    controls = cells[cells["target_gene"].eq("NTC")].copy()
    stats = (
        controls.groupby("dataset_id")[["P_score", "G_score", "S_score", "C_score"]]
        .agg(["mean", "std", "count"])
    )
    usable = []
    for dataset_id, row in stats.iterrows():
        if min(row[(score, "count")] for score in SCORE_TO_STATE) < 50:
            continue
        if min(row[(score, "std")] for score in SCORE_TO_STATE) <= 0:
            continue
        usable.append(dataset_id)
    cells = cells[cells["dataset_id"].isin(usable)].copy()
    stats = stats.loc[usable]

    for score, state in SCORE_TO_STATE.items():
        mean_map = stats[(score, "mean")].to_dict()
        sd_map = stats[(score, "std")].to_dict()
        cells[state] = [
            (v - mean_map[d]) / sd_map[d]
            for v, d in zip(cells[score].to_numpy(float), cells["dataset_id"])
        ]

    pz = posterior_from_state(cells[STATE_DIMS].to_numpy(float), params)
    for i, reg in enumerate(LOCKED_REGIMES):
        cells[f"P_Z_{reg}"] = pz[:, i]
    for alias, reg in ALIAS_TO_LOCKED.items():
        cells[f"P_alias_{alias}"] = cells[f"P_Z_{reg}"]

    norm_rows = []
    for dataset_id in usable:
        row = {"dataset_id": dataset_id, "n_ntc": int((controls["dataset_id"].eq(dataset_id)).sum())}
        for score in SCORE_TO_STATE:
            row[f"{score}_NTC_mean"] = float(stats.loc[dataset_id, (score, "mean")])
            row[f"{score}_NTC_sd"] = float(stats.loc[dataset_id, (score, "std")])
        norm_rows.append(row)
    norm = pd.DataFrame(norm_rows)
    return cells, norm


def evidence_status(n_genes: int, n_cells: int) -> str:
    if n_genes == 0 or n_cells == 0:
        return "not_computable_no_direct_pathway_member_cells"
    if n_genes == 1 or n_cells < 1000:
        return "computed_single_member_or_low_coverage_pathway_proxy"
    return "computed_from_existing_cell_level_pathway_member_perturbations"


def target_gene_delta_table(cells: pd.DataFrame) -> pd.DataFrame:
    pz_cols = [f"P_Z_{r}" for r in LOCKED_REGIMES]
    alias_cols = [f"P_alias_{a}" for a in ALIAS_TO_LOCKED]
    state_cols = STATE_DIMS
    baseline = (
        cells[cells["target_gene"].eq("NTC")]
        .groupby("dataset_id")[pz_cols + alias_cols + state_cols]
        .mean()
    )
    rows = []
    target_cells = cells[~cells["target_gene"].eq("NTC")].copy()
    grouped = target_cells.groupby(["dataset_id", "target_gene"])
    for (dataset_id, target_gene), sub in grouped:
        if dataset_id not in baseline.index:
            continue
        b = baseline.loc[dataset_id]
        t = sub[pz_cols + alias_cols + state_cols].mean()
        row = {
            "dataset_id": dataset_id,
            "target_gene": target_gene,
            "n_target_cells": int(len(sub)),
            "n_baseline_cells": int((cells["dataset_id"].eq(dataset_id) & cells["target_gene"].eq("NTC")).sum()),
        }
        for col in pz_cols + alias_cols + state_cols:
            row[f"raw_delta_{col}"] = float(t[col] - b[col])
            # Existing perturbation screens are treated as target-loss / guide perturbations;
            # activation-oriented pathway contrast is the reverse direction for canonical
            # activators and downstream effectors.
            row[f"activation_delta_{col}"] = float(-(t[col] - b[col]))
        rows.append(row)
    return pd.DataFrame(rows)


def pathway_delta_table(gene_delta: pd.DataFrame) -> pd.DataFrame:
    records = []
    target_rows = []
    for pathway, spec in PATHWAY_DEFS.items():
        genes = set(spec["genes"])
        sub = gene_delta[gene_delta["target_gene"].isin(genes)].copy()
        for _, row in sub.iterrows():
            out = {
                "level": "target_gene",
                "pathway": pathway,
                "target_gene": row["target_gene"],
                "dataset_id": row["dataset_id"],
                "member_role": spec["member_role"],
                "expected_alias": spec["expected_alias"],
                "activation_orientation": "reverse_of_target_gene_perturbation_for_canonical_activation",
                "n_member_genes": 1,
                "n_target_cells": int(row["n_target_cells"]),
                "n_baseline_cells": int(row["n_baseline_cells"]),
                "evidence_status": evidence_status(1, int(row["n_target_cells"])),
            }
            for reg in LOCKED_REGIMES:
                out[f"raw_delta_locked_{reg}"] = row[f"raw_delta_P_Z_{reg}"]
                out[f"activation_delta_locked_{reg}"] = row[f"activation_delta_P_Z_{reg}"]
            for alias in ALIAS_TO_LOCKED:
                out[f"raw_delta_{alias}"] = row[f"raw_delta_P_alias_{alias}"]
                out[f"activation_delta_{alias}"] = row[f"activation_delta_P_alias_{alias}"]
            out["activation_shift_magnitude_L2_locked"] = float(np.linalg.norm([out[f"activation_delta_locked_{r}"] for r in LOCKED_REGIMES]))
            out["activation_expected_shift"] = float(out[f"activation_delta_{spec['expected_alias']}"])
            out["activation_expected_shift_direction"] = "increase" if out["activation_expected_shift"] > 0 else "decrease_or_zero"
            target_rows.append(out)

        if len(sub):
            weights = sub["n_target_cells"].to_numpy(float)
            weights /= weights.sum()
            agg = {
                "level": "pathway_aggregate",
                "pathway": pathway,
                "target_gene": ";".join(sorted(sub["target_gene"].unique())),
                "dataset_id": ";".join(sorted(sub["dataset_id"].unique())),
                "member_role": spec["member_role"],
                "expected_alias": spec["expected_alias"],
                "activation_orientation": "cell_level_target_gene_delta_reversed_to_pathway_activation_direction",
                "n_member_genes": int(sub["target_gene"].nunique()),
                "n_target_cells": int(sub["n_target_cells"].sum()),
                "n_baseline_cells": int(sub["n_baseline_cells"].max()),
                "evidence_status": evidence_status(int(sub["target_gene"].nunique()), int(sub["n_target_cells"].sum())),
            }
            for reg in LOCKED_REGIMES:
                agg[f"raw_delta_locked_{reg}"] = float(np.average(sub[f"raw_delta_P_Z_{reg}"], weights=weights))
                agg[f"activation_delta_locked_{reg}"] = float(np.average(sub[f"activation_delta_P_Z_{reg}"], weights=weights))
            for alias in ALIAS_TO_LOCKED:
                agg[f"raw_delta_{alias}"] = float(np.average(sub[f"raw_delta_P_alias_{alias}"], weights=weights))
                agg[f"activation_delta_{alias}"] = float(np.average(sub[f"activation_delta_P_alias_{alias}"], weights=weights))
            agg["activation_shift_magnitude_L2_locked"] = float(np.linalg.norm([agg[f"activation_delta_locked_{r}"] for r in LOCKED_REGIMES]))
            agg["activation_expected_shift"] = float(agg[f"activation_delta_{spec['expected_alias']}"])
            agg["activation_expected_shift_direction"] = "increase" if agg["activation_expected_shift"] > 0 else "decrease_or_zero"
            records.append(agg)
        else:
            agg = {
                "level": "pathway_aggregate",
                "pathway": pathway,
                "target_gene": "",
                "dataset_id": "",
                "member_role": spec["member_role"],
                "expected_alias": spec["expected_alias"],
                "activation_orientation": "not_computable",
                "n_member_genes": 0,
                "n_target_cells": 0,
                "n_baseline_cells": 0,
                "evidence_status": evidence_status(0, 0),
                "activation_shift_magnitude_L2_locked": np.nan,
                "activation_expected_shift": np.nan,
                "activation_expected_shift_direction": "not_computable",
            }
            for reg in LOCKED_REGIMES:
                agg[f"raw_delta_locked_{reg}"] = np.nan
                agg[f"activation_delta_locked_{reg}"] = np.nan
            for alias in ALIAS_TO_LOCKED:
                agg[f"raw_delta_{alias}"] = np.nan
                agg[f"activation_delta_{alias}"] = np.nan
            records.append(agg)
    return pd.concat([pd.DataFrame(records), pd.DataFrame(target_rows)], ignore_index=True)


def directional_report(delta: pd.DataFrame) -> pd.DataFrame:
    rows = []
    agg = delta[delta["level"].eq("pathway_aggregate")].copy()
    tgt = delta[delta["level"].eq("target_gene")].copy()
    for _, row in agg.iterrows():
        pathway = row["pathway"]
        expected = row["expected_alias"]
        sub = tgt[tgt["pathway"].eq(pathway)]
        if not len(sub):
            ratio = np.nan
            n_pos = 0
        else:
            shifts = sub[f"activation_delta_{expected}"].to_numpy(float)
            n_pos = int(np.sum(shifts > 0))
            ratio = float(n_pos / len(shifts))
        direction_ok = bool(row["activation_expected_shift"] > 0) if pd.notna(row["activation_expected_shift"]) else False
        score = 0.5 * (1.0 if direction_ok else 0.0) + 0.5 * (ratio if np.isfinite(ratio) else 0.0)
        rows.append({
            "pathway": pathway,
            "expected_shift_rule": PATHWAY_DEFS[pathway]["expected_rule"],
            "expected_alias": expected,
            "n_member_genes": int(row["n_member_genes"]),
            "n_target_cells": int(row["n_target_cells"]),
            "aggregate_expected_deltaZ": row["activation_expected_shift"],
            "aggregate_direction_matches_expected": direction_ok,
            "target_gene_positive_count": n_pos,
            "target_gene_tested_count": int(len(sub)),
            "sign_consistency_ratio": ratio,
            "directional_accuracy_score": score,
            "evidence_status": row["evidence_status"],
        })
    return pd.DataFrame(rows)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        return np.nan
    den = np.linalg.norm(a) * np.linalg.norm(b)
    if den == 0:
        return np.nan
    return float(np.dot(a, b) / den)


def cross_dataset_similarity(delta: pd.DataFrame) -> pd.DataFrame:
    rows = []
    tg = delta[delta["level"].eq("target_gene")].copy()
    vec_cols = [f"activation_delta_locked_{r}" for r in LOCKED_REGIMES]
    for pathway in PATHWAY_DEFS:
        sub = tg[tg["pathway"].eq(pathway)]
        datasets = sorted(sub["dataset_id"].dropna().unique())
        if len(datasets) < 2:
            rows.append({
                "pathway": pathway,
                "dataset_i": datasets[0] if datasets else "",
                "dataset_j": "",
                "cosine_similarity_deltaZ": np.nan,
                "status": "not_computable_single_dataset_only" if datasets else "not_computable_no_direct_pathway_member_cells",
            })
            continue
        for i, di in enumerate(datasets):
            vi = sub[sub["dataset_id"].eq(di)][vec_cols].mean().to_numpy(float)
            for dj in datasets[i + 1:]:
                vj = sub[sub["dataset_id"].eq(dj)][vec_cols].mean().to_numpy(float)
                rows.append({
                    "pathway": pathway,
                    "dataset_i": di,
                    "dataset_j": dj,
                    "cosine_similarity_deltaZ": cosine(vi, vj),
                    "status": "computed",
                })
    return pd.DataFrame(rows)


def null_controls(gene_delta: pd.DataFrame, delta: pd.DataFrame, n_perm: int = 2000) -> pd.DataFrame:
    rows = []
    eligible = gene_delta[gene_delta["n_target_cells"].ge(50)].copy()
    eligible_genes = sorted(eligible["target_gene"].unique())
    agg = delta[delta["level"].eq("pathway_aggregate")].copy()
    for _, row in agg.iterrows():
        pathway = row["pathway"]
        expected = row["expected_alias"]
        m = int(row["n_member_genes"])
        obs = row["activation_expected_shift"]
        if m <= 0 or not np.isfinite(obs) or len(eligible_genes) < m:
            rows.append({
                "pathway": pathway,
                "expected_alias": expected,
                "observed_activation_expected_shift": obs,
                "n_permutations": n_perm,
                "null_mean": np.nan,
                "null_sd": np.nan,
                "null_p95": np.nan,
                "null_separation_z": np.nan,
                "empirical_p_null_ge_observed": np.nan,
                "null_component_score": np.nan,
                "status": "not_computable",
            })
            continue
        pathway_genes = set(PATHWAY_DEFS[pathway]["genes"])
        pool = [g for g in eligible_genes if g not in pathway_genes]
        vals = []
        for _ in range(n_perm):
            sampled = RNG.choice(pool, size=m, replace=False if len(pool) >= m else True)
            sub = eligible[eligible["target_gene"].isin(sampled)]
            # Same loss-of-function-to-activation reversal used for real pathway members.
            vals.append(float(np.mean(-sub[f"raw_delta_P_alias_{expected}"].to_numpy(float))))
        vals = np.asarray(vals, float)
        sd = float(np.std(vals, ddof=1))
        z = float((obs - vals.mean()) / sd) if sd > 0 else np.nan
        p_ge = float((1 + np.sum(vals >= obs)) / (len(vals) + 1))
        rows.append({
            "pathway": pathway,
            "expected_alias": expected,
            "observed_activation_expected_shift": obs,
            "n_permutations": n_perm,
            "null_mean": float(np.mean(vals)),
            "null_sd": sd,
            "null_p95": float(np.quantile(vals, 0.95)),
            "null_separation_z": z,
            "empirical_p_null_ge_observed": p_ge,
            "null_component_score": float(1 - p_ge),
            "status": "computed",
        })
    return pd.DataFrame(rows)


def rank_correlation(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if len(a) < 2 or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        return np.nan
    ra = pd.Series(a).rank(method="average").to_numpy(float)
    rb = pd.Series(b).rank(method="average").to_numpy(float)
    return cosine(ra - ra.mean(), rb - rb.mean())


def kl_divergence_shift(obs_delta: np.ndarray, pred_delta: np.ndarray, base_p: np.ndarray) -> float:
    obs = np.maximum(base_p + obs_delta, 1e-9)
    pred = np.maximum(base_p + pred_delta, 1e-9)
    obs /= obs.sum()
    pred /= pred.sum()
    return float(np.sum(obs * np.log(obs / pred)))


def counterfactual_scores(delta: pd.DataFrame, norm: pd.DataFrame, params: pd.DataFrame) -> pd.DataFrame:
    w = pd.read_csv(W_AXIS, sep="\t")
    w["source"] = clean_gene(w["source"])
    w = w.set_index("source")

    # Use the primary perturbation dataset baseline because all direct pathway-member
    # perturbation rows come from GSE216800 in current locked dry-lab data.
    norm_idx = norm.set_index("dataset_id")
    rows = []
    pz_base_cache: dict[str, np.ndarray] = {}
    state_sd_cache: dict[str, dict[str, float]] = {}
    for dataset_id, nr in norm_idx.iterrows():
        base = np.zeros((1, len(STATE_DIMS)))
        pz_base_cache[dataset_id] = posterior_from_state(base, params)[0]
        state_sd_cache[dataset_id] = {
            "Stemness": nr["P_score_NTC_sd"],
            "Transitional": nr["C_score_NTC_sd"],
            "Fate_lock": nr["S_score_NTC_sd"],
            "Embryonic_module_score": nr["G_score_NTC_sd"],
        }

    agg = delta[delta["level"].eq("pathway_aggregate")].copy()
    for _, row in agg.iterrows():
        pathway = row["pathway"]
        dataset_ids = [d for d in str(row["dataset_id"]).split(";") if d]
        dataset_id = dataset_ids[0] if dataset_ids else ""
        genes = [g for g in str(row["target_gene"]).split(";") if g]
        obs = np.array([row[f"activation_delta_locked_{r}"] for r in LOCKED_REGIMES], dtype=float)
        if not genes or dataset_id not in pz_base_cache:
            pred = np.full(len(LOCKED_REGIMES), np.nan)
            status = "not_computable_no_direct_pathway_member_cells"
        else:
            vectors = []
            weights = []
            for g in genes:
                if g not in w.index:
                    continue
                ww = w.loc[g]
                if isinstance(ww, pd.DataFrame):
                    ww = ww.iloc[0]
                effect_state = np.zeros(len(STATE_DIMS))
                for axis, state in AXIS_TO_STATE.items():
                    if axis not in ww.index or pd.isna(ww[axis]):
                        continue
                    # Reverse target-loss perturbation into pathway activation orientation.
                    raw_effect = -float(ww[axis])
                    effect_state[STATE_DIMS.index(state)] = raw_effect / max(state_sd_cache[dataset_id][state], 1e-9)
                p1 = posterior_from_state(effect_state.reshape(1, -1), params)[0]
                p0 = pz_base_cache[dataset_id]
                vectors.append(p1 - p0)
                sub_n = delta[(delta["level"].eq("target_gene")) & (delta["pathway"].eq(pathway)) & (delta["target_gene"].eq(g))]["n_target_cells"]
                weights.append(float(sub_n.iloc[0]) if len(sub_n) else 1.0)
            if vectors:
                weights = np.asarray(weights, float)
                weights /= weights.sum()
                pred = np.average(np.vstack(vectors), axis=0, weights=weights)
                status = "computed_from_locked_W_GRN_axis_effects"
            else:
                pred = np.full(len(LOCKED_REGIMES), np.nan)
                status = "not_computable_no_W_GRN_axis_effect"

        base_p = pz_base_cache.get(dataset_id, np.ones(len(LOCKED_REGIMES)) / len(LOCKED_REGIMES))
        cos = cosine(obs, pred)
        kl = kl_divergence_shift(obs, pred, base_p) if np.all(np.isfinite(pred)) and np.all(np.isfinite(obs)) else np.nan
        rank = rank_correlation(obs, pred)
        out = {
            "pathway": pathway,
            "dataset_id": dataset_id,
            "status": status,
            "observed_vs_counterfactual_cosine": cos,
            "observed_vs_counterfactual_KL": kl,
            "ranking_consistency_spearman_proxy": rank,
            "counterfactual_component_score": float(max(0.0, min(1.0, (cos + 1) / 2))) if np.isfinite(cos) else np.nan,
        }
        for reg, v in zip(LOCKED_REGIMES, obs):
            out[f"observed_activation_delta_{reg}"] = v
        for reg, v in zip(LOCKED_REGIMES, pred):
            out[f"counterfactual_delta_{reg}"] = v
        rows.append(out)
    return pd.DataFrame(rows)


def causal_closure_summary(direction: pd.DataFrame, cross: pd.DataFrame, null: pd.DataFrame, cf: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pathway in PATHWAY_DEFS:
        d = direction[direction["pathway"].eq(pathway)].iloc[0]
        csub = cross[(cross["pathway"].eq(pathway)) & (cross["status"].eq("computed"))]
        n = null[null["pathway"].eq(pathway)].iloc[0]
        c = cf[cf["pathway"].eq(pathway)].iloc[0]
        direction_component = float(d["directional_accuracy_score"])
        cross_component = float((csub["cosine_similarity_deltaZ"].mean() + 1) / 2) if len(csub) else np.nan
        cf_component = float(c["counterfactual_component_score"]) if pd.notna(c["counterfactual_component_score"]) else np.nan
        null_component = float(n["null_component_score"]) if pd.notna(n["null_component_score"]) else np.nan

        components = {
            "directional_consistency_component": (direction_component, 0.40),
            "cross_dataset_stability_component": (cross_component, 0.20),
            "counterfactual_agreement_component": (cf_component, 0.25),
            "null_separation_component": (null_component, 0.15),
        }
        conservative = 0.0
        available_num = 0.0
        available_den = 0.0
        for val, weight in components.values():
            if np.isfinite(val):
                conservative += weight * val
                available_num += weight * val
                available_den += weight
        rows.append({
            "pathway": pathway,
            "directional_consistency_component": direction_component,
            "cross_dataset_stability_component": cross_component,
            "counterfactual_agreement_component": cf_component,
            "null_separation_component": null_component,
            "CCS_conservative_missing_as_zero": conservative,
            "CCS_available_evidence_rescaled": available_num / available_den if available_den > 0 else np.nan,
            "available_weight_fraction": available_den,
            "evidence_status": d["evidence_status"],
            "interpretation_boundary": "dry_lab_perturbation_consistency_only_not_wet_lab_causality",
        })
    return pd.DataFrame(rows)


def write_directional_markdown(direction: pd.DataFrame, cross: pd.DataFrame, null: pd.DataFrame, cf: pd.DataFrame, ccs: pd.DataFrame, norm: pd.DataFrame):
    def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
        if max_rows is not None:
            df = df.head(max_rows)
        df = df.copy()
        for col in df.columns:
            if pd.api.types.is_float_dtype(df[col]):
                df[col] = df[col].map(lambda x: "" if pd.isna(x) else f"{x:.4g}")
            else:
                df[col] = df[col].map(lambda x: "" if pd.isna(x) else str(x))
        cols = list(df.columns)
        lines = [
            "| " + " | ".join(cols) + " |",
            "| " + " | ".join(["---"] * len(cols)) + " |",
        ]
        for _, row in df.iterrows():
            vals = [str(row[c]).replace("|", "/") for c in cols]
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)

    lines = [
        "# Directional Consistency Report",
        "",
        "## Scope",
        "",
        "This is a perturbation-consistency validation layer for the locked latent-state-regime mixture model. It is not model training, model redesign, wet-lab causality, experimental validation, predictive superiority, or classification accuracy testing.",
        "",
        "## Inputs Used",
        "",
        f"- `{CELL_SCORES}`",
        f"- `{PARAMS}`",
        f"- `{W_AXIS}`",
        f"- `{W_SPARSE}`",
        f"- `{PRED_OBS}`",
        "",
        "## Posterior Transfer",
        "",
        "Existing perturbation cells were normalized against NTC controls within dataset and projected into the locked diagonal Gaussian latent-state-regime mixture parameterization. Target-gene guide perturbation contrasts were reversed to approximate canonical pathway activation direction for positive pathway members. This orientation is a dry-lab consistency convention and not a new perturbation experiment.",
        "",
        "## Regime Readout Aliases",
        "",
    ]
    for alias, reg in ALIAS_TO_LOCKED.items():
        lines.append(f"- `{alias}` = locked posterior component `{reg}`")
    lines += [
        "",
        "## Directional Results",
        "",
        md_table(direction),
        "",
        "## Cross-Dataset Invariance",
        "",
        "Direct pathway-member perturbation posterior shifts were available only from GSE216800 in the current locked dry-lab files, so cross-dataset invariance is marked as not computable rather than inferred from pseudo-replicates.",
        "",
        md_table(cross),
        "",
        "## Null Perturbation Control",
        "",
        md_table(null),
        "",
        "## Counterfactual Consistency",
        "",
        md_table(cf[["pathway", "status", "observed_vs_counterfactual_cosine", "observed_vs_counterfactual_KL", "ranking_consistency_spearman_proxy"]]),
        "",
        "## Causal Closure Score",
        "",
        md_table(ccs),
        "",
        "## Interpretation Lock",
        "",
        "The valid claim is perturbation-consistent structure under existing dry-lab evidence. The analysis does not establish wet-lab causality, does not validate pathway interventions experimentally, and does not show predictive superiority over alternative representations.",
    ]
    (OUT / "directional_consistency_report.md").write_text("\n".join(lines) + "\n")


def draw_bar(draw, x, y, w, h, labels, values, title, color, font, bold):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=(247, 249, 252), outline=(210, 220, 232), width=2)
    draw.text((x + 18, y + 18), title, font=bold, fill=(31, 71, 112))
    finite = [v for v in values if np.isfinite(v)]
    vmax = max(max(finite), 1e-9) if finite else 1
    yy = y + 74
    bh = min(34, max(18, (h - 100) // max(1, len(labels)) - 7))
    for lab, val in zip(labels, values):
        draw.text((x + 18, yy), str(lab)[:25], font=font, fill=(30, 41, 59))
        if np.isfinite(val):
            bw = int((w - 330) * max(val, 0) / vmax)
            draw.rectangle((x + 230, yy, x + 230 + bw, yy + bh), fill=color)
            draw.text((x + 240 + bw, yy - 1), f"{val:.3f}", font=font, fill=(30, 41, 59))
        else:
            draw.text((x + 230, yy - 1), "NA", font=font, fill=(160, 54, 54))
        yy += bh + 12


def write_figure(delta: pd.DataFrame, cross: pd.DataFrame, null: pd.DataFrame, cf: pd.DataFrame, ccs: pd.DataFrame):
    W, H = 3600, 2550
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    bold = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 38)
    title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 52)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 25)
    small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    draw.text((80, 48), "FIGURE_CAUSAL_CLOSURE_FINAL", font=title, fill=(18, 27, 45))
    draw.text((80, 112), "Dry-lab perturbation consistency of latent-state-regime posterior shifts; no wet-lab causal claim.", font=font, fill=(75, 85, 99))

    agg = delta[delta["level"].eq("pathway_aggregate")].copy()
    draw_bar(
        draw, 80, 180, 1060, 520,
        agg["pathway"].tolist(),
        agg["activation_expected_shift"].astype(float).tolist(),
        "A  Perturbation -> expected ΔZ",
        (34, 136, 132), font, bold,
    )

    draw_bar(
        draw, 1270, 180, 1060, 520,
        cf["pathway"].tolist(),
        cf["observed_vs_counterfactual_cosine"].astype(float).tolist(),
        "B  Observed vs counterfactual ΔZ cosine",
        (103, 82, 164), font, bold,
    )

    draw.rounded_rectangle((2460, 180, 3520, 700), radius=18, fill=(247, 249, 252), outline=(210, 220, 232), width=2)
    draw.text((2480, 198), "C  Cross-dataset perturbation consistency", font=bold, fill=(31, 71, 112))
    yy = 268
    for _, r in cross.iterrows():
        txt = f"{r['pathway']}: {r['status']}"
        draw.text((2480, yy), txt[:70], font=small, fill=(30, 41, 59))
        yy += 48

    draw_bar(
        draw, 80, 790, 1060, 520,
        null["pathway"].tolist(),
        null["null_separation_z"].astype(float).tolist(),
        "D  Real vs shuffled-label null separation (z)",
        (193, 83, 54), font, bold,
    )

    draw_bar(
        draw, 1270, 790, 1060, 520,
        ccs["pathway"].tolist(),
        ccs["CCS_available_evidence_rescaled"].astype(float).tolist(),
        "E  Causal Closure Score, available evidence",
        (76, 128, 91), font, bold,
    )

    draw_bar(
        draw, 2460, 790, 1060, 520,
        ccs["pathway"].tolist(),
        ccs["available_weight_fraction"].astype(float).tolist(),
        "F  Evidence weight fraction",
        (181, 122, 28), font, bold,
    )

    draw.rounded_rectangle((80, 1450, 3520, 2380), radius=28, outline=(190, 58, 52), width=4, fill=(252, 237, 237))
    draw.text((130, 1500), "Interpretation lock", font=bold, fill=(190, 58, 52))
    txt = (
        "This figure evaluates perturbation-consistent posterior redistribution only. "
        "The pathway-member guide perturbations are existing dry-lab data; pathway activation is an oriented contrast, "
        "not a new intervention. Cross-dataset invariance is not claimed where only one direct perturbation dataset is available. "
        "Valid language: perturbation-consistent structure and counterfactual agreement under existing data."
    )
    yy = 1570
    for line in wrap(txt, 145):
        draw.text((130, yy), line, font=font, fill=(20, 31, 50))
        yy += 42

    png = OUT / "FIGURE_CAUSAL_CLOSURE_FINAL.png"
    pdf = OUT / "FIGURE_CAUSAL_CLOSURE_FINAL.pdf"
    img.save(png)
    img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256).save(pdf)


def main():
    require_inputs()
    params = load_mixture_params()
    cells, norm = load_and_project_cells(params)
    gene_delta = target_gene_delta_table(cells)
    delta = pathway_delta_table(gene_delta)
    direction = directional_report(delta)
    cross = cross_dataset_similarity(delta)
    null = null_controls(gene_delta, delta)
    cf = counterfactual_scores(delta, norm, params)
    ccs = causal_closure_summary(direction, cross, null, cf)

    delta.to_csv(OUT / "perturbation_deltaZ.tsv", sep="\t", index=False)
    cross.to_csv(OUT / "cross_dataset_perturbation_similarity.tsv", sep="\t", index=False)
    null.to_csv(OUT / "null_perturbation_control_results.tsv", sep="\t", index=False)
    cf.to_csv(OUT / "counterfactual_consistency_scores.tsv", sep="\t", index=False)
    ccs.to_csv(OUT / "causal_closure_score_summary.tsv", sep="\t", index=False)
    norm.to_csv(OUT / "perturbation_posterior_transfer_normalization.tsv", sep="\t", index=False)
    write_directional_markdown(direction, cross, null, cf, ccs, norm)
    write_figure(delta, cross, null, cf, ccs)

    print("causal closure consistency validation complete")
    print(ccs[["pathway", "CCS_available_evidence_rescaled", "available_weight_fraction"]].to_string(index=False))


if __name__ == "__main__":
    main()
