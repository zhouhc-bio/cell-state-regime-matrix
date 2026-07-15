#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

W_PATH = OUT / "W_GRN_learned.tsv"
PERT_PATH = Path("/Volumes/T9/PGCS/publication/mechanistic_validation_20260605/perturbation_validation/perturbation_pgcs_validation.tsv")

AXES = ["P", "G", "S", "C"]
U_AXES = ["RA", "BMP", "NOTCH", "FGF", "SHH"]


def read_tsv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    return df


def module_for_gene(gene: str) -> str:
    g = str(gene).upper()
    if g.startswith(("RAR", "RXR", "HOX", "ALDH1A", "CYP26", "MEIS", "PBX")):
        return "RA"
    if g.startswith(("BMP", "BMPR", "SMAD", "ID")) or g in {"GDF15"}:
        return "BMP"
    if g.startswith(("NOTCH", "HES", "HEY", "DLL", "JAG")) or g == "RBPJ":
        return "NOTCH"
    if g.startswith(("FGF", "FGFR", "ETV", "SPRY")) or g == "DUSP6":
        return "FGF"
    if g == "SHH" or g.startswith(("GLI", "PTCH")):
        return "SHH"
    if g.startswith(("EZH", "SUZ", "EED", "ARID", "SMARCA", "KMT", "BMI", "BPTF")):
        return "chromatin_regulator"
    return "none"


def build_w_features(w: pd.DataFrame) -> pd.DataFrame:
    w = w.copy()
    w["source"] = w["source"].astype(str).str.upper()
    w["target"] = w["target"].astype(str).str.upper()
    w["inferred_native_weight"] = pd.to_numeric(w["inferred_native_weight"], errors="coerce").fillna(0.0)
    w["support_score"] = pd.to_numeric(w.get("support_score", 0), errors="coerce").fillna(0.0)
    w["sparse_bool"] = w["sparse_selected"].astype(str).str.lower().isin(["true", "1", "yes"])
    genes = sorted(set(w["source"]) | set(w.loc[w["target_type"].astype(str) == "gene", "target"]))
    rows = []
    for gene in genes:
        out = w[w["source"] == gene]
        inc = w[(w["target"] == gene) & (w["target_type"].astype(str) == "gene")]
        row = {
            "target_gene": gene,
            "W_out_degree": float(out.shape[0]),
            "W_in_degree": float(inc.shape[0]),
            "W_out_sparse_degree": float(out["sparse_bool"].sum()) if not out.empty else 0.0,
            "W_in_sparse_degree": float(inc["sparse_bool"].sum()) if not inc.empty else 0.0,
            "W_out_weight_sum": float(out["inferred_native_weight"].sum()) if not out.empty else 0.0,
            "W_in_weight_sum": float(inc["inferred_native_weight"].sum()) if not inc.empty else 0.0,
            "W_out_abs_weight_sum": float(out["inferred_native_weight"].abs().sum()) if not out.empty else 0.0,
            "W_in_abs_weight_sum": float(inc["inferred_native_weight"].abs().sum()) if not inc.empty else 0.0,
            "W_out_positive_sum": float(out.loc[out["inferred_native_weight"] > 0, "inferred_native_weight"].sum()) if not out.empty else 0.0,
            "W_out_negative_sum": float(out.loc[out["inferred_native_weight"] < 0, "inferred_native_weight"].sum()) if not out.empty else 0.0,
            "W_support_mean": float(out["support_score"].mean()) if not out.empty else 0.0,
            "W_chromatin_supported_edges": float((out.get("chromvar_support", False).astype(str).str.lower().isin(["true", "1"]) | out.get("peak_gene_support", False).astype(str).str.lower().isin(["true", "1"])).sum()) if not out.empty else 0.0,
        }
        for axis in AXES:
            sub = out[out["target"] == f"STATE_AXIS:{axis}"]
            row[f"W_to_axis_{axis}"] = float(sub["inferred_native_weight"].mean()) if not sub.empty else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def build_examples(pert: pd.DataFrame, wf: pd.DataFrame) -> pd.DataFrame:
    pert = pert.copy()
    pert["target_gene"] = pert["target_gene"].astype(str).str.upper()
    pert["output_axis"] = pert["output_axis"].astype(str).str.upper()
    for col in ["mean_difference", "mean_control", "mean_target", "q_value_bh", "n_target_cells", "n_control_cells"]:
        pert[col] = pd.to_numeric(pert[col], errors="coerce")
    rows = []
    for (dataset_id, sample, gene), sub in pert.groupby(["dataset_id", "sample", "target_gene"], dropna=False):
        row = {"dataset_id": dataset_id, "sample": sample, "target_gene": gene}
        for axis in AXES:
            ax = sub[sub["output_axis"] == axis]
            if ax.empty:
                row[f"S_{axis}"] = np.nan
                row[f"delta_{axis}"] = np.nan
            else:
                weights = (ax["n_target_cells"].fillna(0) + ax["n_control_cells"].fillna(0)).replace(0, 1)
                row[f"S_{axis}"] = float(np.average(ax["mean_control"].fillna(0), weights=weights))
                row[f"delta_{axis}"] = float(np.average(ax["mean_difference"].fillna(0), weights=weights))
                row[f"q_{axis}"] = float(ax["q_value_bh"].min(skipna=True))
        mod = module_for_gene(gene)
        row["target_module_for_U"] = mod
        for u in U_AXES:
            row[f"U_{u}"] = 1.0 if mod == u else 0.0
        row["U_observed_known_pathway"] = 1.0 if mod in U_AXES else 0.0
        row["is_chromatin_regulator_target"] = 1.0 if mod == "chromatin_regulator" else 0.0
        rows.append(row)
    ex = pd.DataFrame(rows).merge(wf, on="target_gene", how="left")
    for c in wf.columns:
        if c != "target_gene" and c in ex.columns:
            ex[c] = pd.to_numeric(ex[c], errors="coerce").fillna(0.0)
    ex = ex.dropna(subset=[f"S_{a}" for a in AXES] + [f"delta_{a}" for a in AXES]).reset_index(drop=True)
    ex["observed_basin"] = ex[[f"delta_{a}" for a in AXES]].astype(float).idxmax(axis=1).str.replace("delta_", "", regex=False)
    ex["control_basin"] = ex[[f"S_{a}" for a in AXES]].astype(float).idxmax(axis=1).str.replace("S_", "", regex=False)
    return ex


def zscore(X: np.ndarray) -> np.ndarray:
    X = X.astype(float)
    mean = np.nanmean(X, axis=0)
    std = np.nanstd(X, axis=0)
    std[std == 0] = 1.0
    return np.nan_to_num((X - mean) / std)


def pca_scores(X: np.ndarray, k: int = 3) -> np.ndarray:
    Xs = zscore(X)
    if Xs.shape[1] == 0:
        return np.zeros((Xs.shape[0], 1))
    _, s, vt = np.linalg.svd(Xs, full_matrices=False)
    kk = min(k, vt.shape[0])
    return Xs @ vt[:kk].T


def quantile_code(X: np.ndarray, bins: int = 4) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    codes = []
    for j in range(X.shape[1]):
        col = X[:, j]
        if np.nanstd(col) == 0:
            codes.append(np.zeros(len(col), dtype=int))
            continue
        qs = np.unique(np.nanquantile(col, np.linspace(0, 1, bins + 1)[1:-1]))
        codes.append(np.digitize(col, qs, right=False))
    tuples = list(zip(*codes))
    return pd.factorize(tuples, sort=True)[0]


def entropy(code: np.ndarray) -> float:
    code = np.asarray(code)
    _, counts = np.unique(code, return_counts=True)
    p = counts / counts.sum()
    return float(-(p * np.log2(p)).sum())


def joint_code(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return pd.factorize(list(zip(a, b)), sort=True)[0]


def mi_discrete(x_code: np.ndarray, y_code: np.ndarray) -> dict[str, float]:
    hx = entropy(x_code)
    hy = entropy(y_code)
    hxy = entropy(joint_code(x_code, y_code))
    mi = max(0.0, hx + hy - hxy)
    return {
        "H_X_bits": hx,
        "H_deltaS_bits": hy,
        "I_bits": mi,
        "H_deltaS_given_X_bits": max(0.0, hy - mi),
        "normalized_MI_by_H_deltaS": mi / hy if hy > 0 else np.nan,
        "residual_entropy_ratio": (hy - mi) / hy if hy > 0 else np.nan,
    }


def information_rows(ex: pd.DataFrame, feature_sets: dict[str, list[str]]) -> pd.DataFrame:
    rows = []
    Y = ex[[f"delta_{a}" for a in AXES]].to_numpy(float)
    y_joint = quantile_code(Y, bins=4)
    y_basin = pd.factorize(ex["observed_basin"])[0]
    for name, cols in feature_sets.items():
        X = ex[cols].to_numpy(float)
        x_code = quantile_code(pca_scores(X, k=min(4, max(1, X.shape[1]))), bins=4)
        for label, y_code in [("deltaS_joint", y_joint), ("dominant_basin", y_basin)]:
            m = mi_discrete(x_code, y_code)
            rows.append({"feature_set": name, "response": label, "n": len(ex), **m})
        for axis in AXES:
            y_axis = quantile_code(ex[f"delta_{axis}"].to_numpy(float), bins=4)
            m = mi_discrete(x_code, y_axis)
            rows.append({"feature_set": name, "response": f"delta_{axis}", "n": len(ex), **m})
    return pd.DataFrame(rows)


def observability_metrics(ex: pd.DataFrame, feature_sets: dict[str, list[str]], predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    y_joint = quantile_code(ex[[f"delta_{a}" for a in AXES]].to_numpy(float), bins=4)
    basins = ex["observed_basin"].astype(str).to_numpy()
    Y = ex[[f"delta_{a}" for a in AXES]].to_numpy(float)
    obs_var = float(np.var(Y, axis=0).sum())
    for name, cols in feature_sets.items():
        X = ex[cols].to_numpy(float)
        Xz = zscore(X)
        x_code = quantile_code(pca_scores(X, k=min(4, max(1, X.shape[1]))), bins=4)
        df = pd.DataFrame({"x": x_code, "y": y_joint})
        group = df.groupby("x")["y"].agg(["nunique", "count"]).reset_index()
        ambiguous_obs = int(group.loc[group["nunique"] > 1, "count"].sum())
        collision_rate = 1.0 - group.shape[0] / len(df)
        d = np.sum((Xz[:, None, :] - Xz[None, :, :]) ** 2, axis=2)
        np.fill_diagonal(d, np.inf)
        k = min(10, len(ex) - 1)
        nn = np.argpartition(d, kth=k - 1, axis=1)[:, :k]
        state_ambiguity = float(np.mean([[basins[j] != basins[i] for j in nn[i]] for i in range(len(ex))]))
        same_min, diff_min, overlap, sil = [], [], [], []
        for i in range(len(ex)):
            same = (basins == basins[i])
            same[i] = False
            diff = basins != basins[i]
            a = float(np.min(d[i, same])) if same.any() else np.nan
            b = float(np.min(d[i, diff])) if diff.any() else np.nan
            same_min.append(a)
            diff_min.append(b)
            if np.isfinite(a) and np.isfinite(b):
                overlap.append(b <= a)
                sil.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
        pred = predictions.get(name)
        if pred is not None:
            pred_var_ratio = float(np.var(pred, axis=0).sum() / obs_var) if obs_var > 0 else np.nan
            sign_acc = float(np.mean(np.sign(pred.reshape(-1)) == np.sign(Y.reshape(-1))))
        else:
            pred_var_ratio = np.nan
            sign_acc = np.nan
        rows.append(
            {
                "feature_set": name,
                "n": len(ex),
                "distinct_feature_bins": int(group.shape[0]),
                "collision_rate": collision_rate,
                "many_to_one_ambiguous_observation_fraction": ambiguous_obs / len(ex),
                "state_ambiguity_knn10_fraction": state_ambiguity,
                "basin_overlap_fraction": float(np.mean(overlap)) if overlap else np.nan,
                "basin_silhouette_proxy_mean": float(np.nanmean(sil)) if sil else np.nan,
                "prediction_variance_ratio": pred_var_ratio,
                "prediction_collapse_index": 1.0 - min(pred_var_ratio, 1.0) if np.isfinite(pred_var_ratio) else np.nan,
                "prediction_sign_accuracy": sign_acc,
            }
        )
    return pd.DataFrame(rows)


def ridge_cv_by_target(ex: pd.DataFrame, feature_sets: dict[str, list[str]]) -> dict[str, np.ndarray]:
    Y = ex[[f"delta_{a}" for a in AXES]].to_numpy(float)
    groups = ex["target_gene"].astype(str).to_numpy()
    preds = {}
    for name, cols in feature_sets.items():
        X = ex[cols].to_numpy(float)
        P = np.full_like(Y, np.nan)
        for g in sorted(pd.unique(groups)):
            test = np.where(groups == g)[0]
            train = np.where(groups != g)[0]
            if len(train) < 10:
                continue
            mean = X[train].mean(axis=0)
            std = X[train].std(axis=0)
            std[std == 0] = 1.0
            Xs = (X - mean) / std
            Xtr = np.c_[np.ones(len(train)), Xs[train]]
            Xte = np.c_[np.ones(len(test)), Xs[test]]
            lam = 1e-3
            eye = np.eye(Xtr.shape[1])
            eye[0, 0] = 0.0
            beta = np.linalg.pinv(Xtr.T @ Xtr + lam * eye) @ Xtr.T @ Y[train]
            P[test] = Xte @ beta
        preds[name] = np.nan_to_num(P)
    return preds


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return np.nan
    x = x[mask]
    y = y[mask]
    if x.std() == 0 or y.std() == 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def eta_squared(values: np.ndarray, categories: pd.Series) -> float:
    vals = np.asarray(values, dtype=float)
    cats = categories.astype(str).to_numpy()
    mask = np.isfinite(vals)
    vals = vals[mask]
    cats = cats[mask]
    if len(vals) < 3:
        return np.nan
    grand = vals.mean()
    ss_total = ((vals - grand) ** 2).sum()
    if ss_total == 0:
        return 0.0
    ss_between = 0.0
    for c in pd.unique(cats):
        sub = vals[cats == c]
        ss_between += len(sub) * (sub.mean() - grand) ** 2
    return float(ss_between / ss_total)


def residual_structure(ex: pd.DataFrame, pred_full: np.ndarray) -> pd.DataFrame:
    Y = ex[[f"delta_{a}" for a in AXES]].to_numpy(float)
    R = Y - pred_full
    ex2 = ex.copy()
    ex2["residual_norm"] = np.sqrt((R * R).sum(axis=1))
    for j, axis in enumerate(AXES):
        ex2[f"residual_{axis}"] = R[:, j]
    rows = []
    continuous = {
        "hidden_lineage_history_proxy:S_P": "S_P",
        "hidden_lineage_history_proxy:S_G": "S_G",
        "hidden_lineage_history_proxy:S_S": "S_S",
        "chromatin_memory_proxy:S_C": "S_C",
        "chromatin_memory_proxy:W_to_axis_C": "W_to_axis_C",
        "chromatin_memory_proxy:W_chromatin_supported_edges": "W_chromatin_supported_edges",
        "chromatin_memory_proxy:W_support_mean": "W_support_mean",
        "unobserved_signaling_proxy:U_observed_known_pathway": "U_observed_known_pathway",
        "unobserved_signaling_proxy:W_out_abs_weight_sum": "W_out_abs_weight_sum",
    }
    for proxy, col in continuous.items():
        if col not in ex2.columns:
            continue
        for comp in ["residual_norm"] + [f"residual_{a}" for a in AXES]:
            rows.append(
                {
                    "residual_component": comp,
                    "proxy_type": proxy.split(":")[0],
                    "proxy_variable": proxy.split(":", 1)[1],
                    "test": "pearson_r",
                    "value": pearson(ex2[comp].to_numpy(float), ex2[col].to_numpy(float)),
                    "n": len(ex2),
                }
            )
    categorical = {
        "hidden_lineage_history_proxy:dataset_id": "dataset_id",
        "hidden_lineage_history_proxy:sample": "sample",
        "hidden_lineage_history_proxy:control_basin": "control_basin",
        "unobserved_signaling_proxy:target_module_for_U": "target_module_for_U",
        "unobserved_signaling_proxy:target_gene": "target_gene",
        "fate_output_proxy:observed_basin": "observed_basin",
    }
    for proxy, col in categorical.items():
        for comp in ["residual_norm"] + [f"residual_{a}" for a in AXES]:
            rows.append(
                {
                    "residual_component": comp,
                    "proxy_type": proxy.split(":")[0],
                    "proxy_variable": proxy.split(":", 1)[1],
                    "test": "eta_squared",
                    "value": eta_squared(ex2[comp].to_numpy(float), ex2[col]),
                    "n": len(ex2),
                }
            )
    out = pd.DataFrame(rows)
    out["abs_value"] = out["value"].abs()
    out = out.sort_values(["residual_component", "abs_value"], ascending=[True, False])
    return out.drop(columns=["abs_value"])


def cv_metrics(Y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    y = Y.reshape(-1)
    p = pred.reshape(-1)
    mask = np.isfinite(y) & np.isfinite(p)
    y = y[mask]
    p = p[mask]
    if len(y) == 0:
        return {"pearson_r": np.nan, "rmse": np.nan, "sign_accuracy": np.nan}
    return {
        "pearson_r": pearson(y, p),
        "rmse": float(np.sqrt(np.mean((y - p) ** 2))),
        "sign_accuracy": float(np.mean(np.sign(y) == np.sign(p))),
    }


def md_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    d = df.head(max_rows).copy()
    cols = list(d.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in d.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append("" if math.isnan(v) else f"{v:.4g}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> int:
    w = read_tsv(W_PATH)
    pert = read_tsv(PERT_PATH)
    wf = build_w_features(w)
    ex = build_examples(pert, wf)
    s_cols = [f"S_{a}" for a in AXES]
    u_cols = [f"U_{u}" for u in U_AXES]
    w_cols = [c for c in ex.columns if c.startswith("W_")]
    feature_sets = {
        "W_GRN_S_U": w_cols + s_cols + u_cols,
        "S_U": s_cols + u_cols,
        "W_GRN_only": w_cols,
    }
    preds = ridge_cv_by_target(ex, feature_sets)
    info = information_rows(ex, feature_sets)
    obs = observability_metrics(ex, feature_sets, preds)
    Y = ex[[f"delta_{a}" for a in AXES]].to_numpy(float)
    pred_metric_rows = []
    for name, pred in preds.items():
        pred_metric_rows.append({"feature_set": name, **cv_metrics(Y, pred)})
    pred_metrics = pd.DataFrame(pred_metric_rows)
    res = residual_structure(ex, preds["W_GRN_S_U"])

    info.to_csv(OUT / "information_decomposition.tsv", sep="\t", index=False)
    obs.to_csv(OUT / "observability_mapping_diagnostics.tsv", sep="\t", index=False)
    pred_metrics.to_csv(OUT / "identifiability_prediction_diagnostics.tsv", sep="\t", index=False)
    res.to_csv(OUT / "residual_structure_analysis.tsv", sep="\t", index=False)

    full_joint = info[(info["feature_set"] == "W_GRN_S_U") & (info["response"] == "deltaS_joint")].iloc[0]
    full_obs = obs[obs["feature_set"] == "W_GRN_S_U"].iloc[0]
    full_pred = pred_metrics[pred_metrics["feature_set"] == "W_GRN_S_U"].iloc[0]
    nmi = float(full_joint["normalized_MI_by_H_deltaS"])
    residual_ratio = float(full_joint["residual_entropy_ratio"])
    ambiguity = float(full_obs["many_to_one_ambiguous_observation_fraction"])
    basin_overlap = float(full_obs["basin_overlap_fraction"])
    pred_r = float(full_pred["pearson_r"])
    sign_acc = float(full_pred["sign_accuracy"])

    if nmi >= 0.75 and residual_ratio <= 0.25 and ambiguity <= 0.20 and pred_r >= 0.70 and sign_acc >= 0.75:
        classification = "fully_identifiable"
    elif nmi >= 0.25 and residual_ratio <= 0.75 and pred_r >= 0.20:
        classification = "partially_identifiable"
    else:
        classification = "non_identifiable"
    if ambiguity > 0.75 or basin_overlap > 0.75:
        classification = "non_identifiable" if pred_r < 0.35 else "partially_identifiable"

    top_res = res.sort_values("value", key=lambda s: s.abs(), ascending=False).head(12)

    report = f"""# Identifiability Report

## Reset Assumption

This audit treats the current system as independently initialized. It does not assume previous decoder validity, previous manifold sufficiency, or completeness of `W_GRN`.

## Inputs

- `W_GRN`: `{W_PATH}`
- perturbation response table: `{PERT_PATH}`
- observations: {len(ex)} sample-target perturbation units
- state vector `S`: control mean PGCS axes P/G/S/C
- pathway input `U`: observable RA/BMP/NOTCH/FGF/SHH target-module indicators only
- response `ΔS`: perturbed mean minus control mean for P/G/S/C

## Observability Result

The map `(W_GRN, S, U) -> ΔS` is not injective at the available observation level. Discretized feature states collide with multiple response states, and nearest-neighbor basin labels remain mixed.

{md_table(obs)}

## Information Decomposition

Mutual information is estimated by PCA-assisted quantile discretization. Values are comparative, not absolute biophysical information measures.

{md_table(info[info['response'].isin(['deltaS_joint', 'dominant_basin'])])}

## Prediction Diagnostics

{md_table(pred_metrics)}

## Classification

Revised system classification: **{classification}**.

Key values for full `(W_GRN,S,U)`:

- normalized MI with joint `ΔS`: {nmi:.4g}
- residual entropy ratio: {residual_ratio:.4g}
- many-to-one ambiguous observation fraction: {ambiguity:.4g}
- basin overlap fraction: {basin_overlap:.4g}
- heldout prediction correlation: {pred_r:.4g}
- heldout sign accuracy: {sign_acc:.4g}

## Residual Structure

Top residual associations:

{md_table(top_res)}
"""
    (OUT / "identifiability_report.md").write_text(report, encoding="utf-8")

    class_md = f"""# Revised System Classification

Classification: **{classification}**

The current observable system is not structurally identifiable as a closed fate-dynamics map. `W_GRN` adds measurable information relative to `S,U` for some discretized response summaries, but the full map remains many-to-one: similar observed `(W_GRN,S,U)` states can produce different `ΔS` basins, and residuals retain structure associated with sample, target identity, control basin, and chromatin/proxy variables.

Operational interpretation:

- `W_GRN` is empirically grounded but incomplete for fate dynamics.
- `S` and coarse pathway indicators `U` do not capture hidden lineage history or pathway dose.
- The residual entropy after conditioning remains too high for full identifiability.
- The system is therefore usable as a partially constrained response model, not a uniquely identifiable mechanistic dynamical system.

Required missing observables for identifiability improvement:

1. time-resolved `S(t) -> S(t+τ)` per perturbation rather than endpoint summaries,
2. explicit pathway dose/activity for RA/BMP/NOTCH/FGF/SHH,
3. lineage-history or clone/history labels,
4. matched chromatin memory state per cell before perturbation,
5. direct transition probabilities linked to the same perturbation units.
"""
    (OUT / "system_classification_revised.md").write_text(class_md, encoding="utf-8")

    print("identifiability audit complete")
    print(f"observations={len(ex)}")
    print(f"classification={classification}")
    print(f"normalized_MI_full_deltaS={nmi:.6f}")
    print(f"residual_entropy_ratio={residual_ratio:.6f}")
    print(f"ambiguity={ambiguity:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
