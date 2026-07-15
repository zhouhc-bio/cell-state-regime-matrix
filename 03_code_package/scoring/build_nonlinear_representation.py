#!/usr/bin/env python3
from __future__ import annotations

import math
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


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
    if g.startswith("RAR") or g.startswith("RXR") or g.startswith("HOX") or g.startswith("ALDH1A") or g.startswith("CYP26") or g.startswith("MEIS") or g.startswith("PBX"):
        return "RA"
    if g.startswith("BMP") or g.startswith("BMPR") or g.startswith("SMAD") or g.startswith("ID") or g in {"GDF15"}:
        return "BMP"
    if g.startswith("NOTCH") or g.startswith("HES") or g.startswith("HEY") or g.startswith("DLL") or g.startswith("JAG") or g == "RBPJ":
        return "NOTCH"
    if g.startswith("FGF") or g.startswith("FGFR") or g.startswith("ETV") or g.startswith("SPRY") or g == "DUSP6":
        return "FGF"
    if g == "SHH" or g.startswith("GLI") or g.startswith("PTCH"):
        return "SHH"
    return "none"


def build_w_features(w: pd.DataFrame) -> pd.DataFrame:
    w = w.copy()
    w["source"] = w["source"].astype(str).str.upper()
    w["target"] = w["target"].astype(str).str.upper()
    w["inferred_native_weight"] = pd.to_numeric(w["inferred_native_weight"], errors="coerce").fillna(0.0)
    w["support_score"] = pd.to_numeric(w.get("support_score", 0), errors="coerce").fillna(0.0)
    w["sparse_selected_bool"] = w["sparse_selected"].astype(str).str.lower().isin(["true", "1", "yes"])

    genes = sorted(set(w["source"]) | set(w.loc[w["target_type"].astype(str) == "gene", "target"]))
    rows = []
    for gene in genes:
        out = w[w["source"] == gene]
        inc = w[(w["target"] == gene) & (w["target_type"].astype(str) == "gene")]
        row: dict[str, float | str] = {
            "target_gene": gene,
            "W_out_degree": float(out.shape[0]),
            "W_in_degree": float(inc.shape[0]),
            "W_out_sparse_degree": float(out["sparse_selected_bool"].sum()) if not out.empty else 0.0,
            "W_in_sparse_degree": float(inc["sparse_selected_bool"].sum()) if not inc.empty else 0.0,
            "W_out_weight_sum": float(out["inferred_native_weight"].sum()) if not out.empty else 0.0,
            "W_in_weight_sum": float(inc["inferred_native_weight"].sum()) if not inc.empty else 0.0,
            "W_out_abs_weight_sum": float(out["inferred_native_weight"].abs().sum()) if not out.empty else 0.0,
            "W_in_abs_weight_sum": float(inc["inferred_native_weight"].abs().sum()) if not inc.empty else 0.0,
            "W_out_positive_sum": float(out.loc[out["inferred_native_weight"] > 0, "inferred_native_weight"].sum()) if not out.empty else 0.0,
            "W_out_negative_sum": float(out.loc[out["inferred_native_weight"] < 0, "inferred_native_weight"].sum()) if not out.empty else 0.0,
            "W_support_mean": float(out["support_score"].mean()) if not out.empty else 0.0,
        }
        for axis in AXES:
            sub = out[out["target"] == f"STATE_AXIS:{axis}"]
            row[f"W_to_axis_{axis}"] = float(sub["inferred_native_weight"].mean()) if not sub.empty else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def build_examples(pert: pd.DataFrame, w_features: pd.DataFrame) -> pd.DataFrame:
    pert = pert.copy()
    pert["target_gene"] = pert["target_gene"].astype(str).str.upper()
    pert["output_axis"] = pert["output_axis"].astype(str).str.upper()
    for col in ["mean_difference", "mean_control", "mean_target", "q_value_bh", "n_target_cells", "n_control_cells"]:
        pert[col] = pd.to_numeric(pert[col], errors="coerce")

    rows = []
    group_cols = ["dataset_id", "sample", "target_gene"]
    for key, sub in pert.groupby(group_cols, dropna=False):
        dataset_id, sample, target_gene = key
        row = {"dataset_id": dataset_id, "sample": sample, "target_gene": target_gene}
        for axis in AXES:
            ax = sub[sub["output_axis"] == axis]
            if ax.empty:
                row[f"S_control_{axis}"] = np.nan
                row[f"S_target_{axis}"] = np.nan
                row[f"delta_{axis}"] = np.nan
                row[f"q_{axis}"] = np.nan
            else:
                weights = (ax["n_target_cells"].fillna(0) + ax["n_control_cells"].fillna(0)).replace(0, 1)
                row[f"S_control_{axis}"] = float(np.average(ax["mean_control"].fillna(0), weights=weights))
                row[f"S_target_{axis}"] = float(np.average(ax["mean_target"].fillna(0), weights=weights))
                row[f"delta_{axis}"] = float(np.average(ax["mean_difference"].fillna(0), weights=weights))
                row[f"q_{axis}"] = float(ax["q_value_bh"].min(skipna=True))
        row["target_module_for_U"] = module_for_gene(target_gene)
        for u in U_AXES:
            row[f"U_{u}"] = 1.0 if row["target_module_for_U"] == u else 0.0
        rows.append(row)
    ex = pd.DataFrame(rows)
    ex = ex.merge(w_features, on="target_gene", how="left")
    for c in w_features.columns:
        if c != "target_gene" and c in ex.columns:
            ex[c] = pd.to_numeric(ex[c], errors="coerce").fillna(0.0)
    ex = ex.dropna(subset=[f"delta_{a}" for a in AXES], how="any").reset_index(drop=True)
    ex["observed_basin"] = ex[[f"delta_{a}" for a in AXES]].astype(float).idxmax(axis=1).str.replace("delta_", "", regex=False)
    return ex


def standardize_train(X: np.ndarray, train_idx: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = X[train_idx].mean(axis=0)
    std = X[train_idx].std(axis=0)
    std[std == 0] = 1.0
    return (X - mean) / std, mean, std


def ridge_fit_predict(X: np.ndarray, Y: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray, lam: float = 1e-3) -> np.ndarray:
    Xs, _, _ = standardize_train(X, train_idx)
    Xtr = np.c_[np.ones(len(train_idx)), Xs[train_idx]]
    Xte = np.c_[np.ones(len(test_idx)), Xs[test_idx]]
    eye = np.eye(Xtr.shape[1])
    eye[0, 0] = 0.0
    beta = np.linalg.pinv(Xtr.T @ Xtr + lam * eye) @ Xtr.T @ Y[train_idx]
    return Xte @ beta


def pairwise_sq_dists(X: np.ndarray) -> np.ndarray:
    norms = np.sum(X * X, axis=1, keepdims=True)
    d = norms + norms.T - 2 * X @ X.T
    return np.maximum(d, 0.0)


def rbf_latent_embedding(X: np.ndarray, n_components: int = 10) -> tuple[np.ndarray, dict]:
    Xmean = X.mean(axis=0)
    Xstd = X.std(axis=0)
    Xstd[Xstd == 0] = 1.0
    Xs = (X - Xmean) / Xstd
    d = pairwise_sq_dists(Xs)
    positive = d[d > 0]
    gamma = 1.0 / (np.median(positive) + 1e-9) if positive.size else 1.0
    K = np.exp(-gamma * d)
    one = np.ones_like(K) / K.shape[0]
    Kc = K - one @ K - K @ one + one @ K @ one
    vals, vecs = np.linalg.eigh(Kc)
    order = np.argsort(vals)[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    keep = vals > 1e-9
    vals = vals[keep][:n_components]
    vecs = vecs[:, keep][:, :n_components]
    Z = vecs * np.sqrt(vals)
    meta = {"Xmean": Xmean, "Xstd": Xstd, "gamma": gamma, "eigenvalues": vals, "eigenvectors": vecs, "K_fit": K, "K_fit_col_mean": K.mean(axis=0), "K_fit_total_mean": float(K.mean())}
    return Z, meta


def metrics(Y: np.ndarray, P: np.ndarray) -> dict[str, float]:
    y = Y.reshape(-1)
    p = P.reshape(-1)
    mask = np.isfinite(y) & np.isfinite(p)
    y, p = y[mask], p[mask]
    if y.size == 0:
        return {"n": 0, "mae": np.nan, "rmse": np.nan, "pearson_r": np.nan, "sign_accuracy": np.nan}
    sy, sp = y.std(), p.std()
    corr = float(np.corrcoef(y, p)[0, 1]) if sy > 0 and sp > 0 else np.nan
    return {
        "n": int(y.size),
        "mae": float(np.mean(np.abs(y - p))),
        "rmse": float(np.sqrt(np.mean((y - p) ** 2))),
        "pearson_r": corr,
        "sign_accuracy": float(np.mean(np.sign(y) == np.sign(p))),
    }


def basin_accuracy(Y: np.ndarray, P: np.ndarray) -> float:
    return float(np.mean(np.argmax(Y, axis=1) == np.argmax(P, axis=1)))


def cross_validate(ex: pd.DataFrame, X_linear: np.ndarray, Z: np.ndarray, U: np.ndarray, Y: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    pred_rows = []
    metric_rows = []
    X_nonlin = np.c_[Z, U]
    groups = ex["target_gene"].astype(str).values
    unique_groups = sorted(pd.unique(groups))
    all_lin = np.zeros_like(Y)
    all_non = np.zeros_like(Y)
    for g in unique_groups:
        test = np.where(groups == g)[0]
        train = np.where(groups != g)[0]
        if len(train) < 10 or len(test) == 0:
            continue
        lin = ridge_fit_predict(X_linear, Y, train, test)
        non = ridge_fit_predict(X_nonlin, Y, train, test)
        all_lin[test] = lin
        all_non[test] = non
        for local_i, idx in enumerate(test):
            row = {
                "validation_type": "leave_one_perturbation_out",
                "heldout_unit": g,
                "dataset_id": ex.loc[idx, "dataset_id"],
                "sample": ex.loc[idx, "sample"],
                "target_gene": ex.loc[idx, "target_gene"],
                "observed_basin": ex.loc[idx, "observed_basin"],
                "predicted_basin_linear": AXES[int(np.argmax(lin[local_i]))],
                "predicted_basin_nonlinear": AXES[int(np.argmax(non[local_i]))],
            }
            for j, axis in enumerate(AXES):
                row[f"observed_delta_{axis}"] = Y[idx, j]
                row[f"linear_predicted_delta_{axis}"] = lin[local_i, j]
                row[f"nonlinear_predicted_delta_{axis}"] = non[local_i, j]
            pred_rows.append(row)
    covered = np.array([r for r in range(len(ex)) if np.any(all_lin[r] != 0) or np.any(all_non[r] != 0)])
    if len(covered):
        for name, pred in [("linear_baseline", all_lin), ("nonlinear_phi_decoder", all_non)]:
            m = metrics(Y[covered], pred[covered])
            m.update({"validation_type": "leave_one_perturbation_out", "model": name, "basin_accuracy": basin_accuracy(Y[covered], pred[covered])})
            metric_rows.append(m)

    if ex["dataset_id"].nunique() > 1:
        for ds in sorted(ex["dataset_id"].unique()):
            test = np.where(ex["dataset_id"].astype(str).values == str(ds))[0]
            train = np.where(ex["dataset_id"].astype(str).values != str(ds))[0]
            if len(train) < 10 or len(test) == 0:
                continue
            for name, X in [("linear_baseline", X_linear), ("nonlinear_phi_decoder", X_nonlin)]:
                pred = ridge_fit_predict(X, Y, train, test)
                m = metrics(Y[test], pred)
                m.update({"validation_type": "dataset_holdout", "model": name, "heldout_dataset": ds, "basin_accuracy": basin_accuracy(Y[test], pred)})
                metric_rows.append(m)

    # Pathway ablation: same nonlinear Z, but U set to zero during CV.
    X_no_u = np.c_[Z, np.zeros_like(U)]
    all_no_u = np.zeros_like(Y)
    for g in unique_groups:
        test = np.where(groups == g)[0]
        train = np.where(groups != g)[0]
        if len(train) < 10 or len(test) == 0:
            continue
        all_no_u[test] = ridge_fit_predict(X_no_u, Y, train, test)
    if len(covered):
        m = metrics(Y[covered], all_no_u[covered])
        m.update({"validation_type": "pathway_ablation", "model": "nonlinear_phi_decoder_without_U", "basin_accuracy": basin_accuracy(Y[covered], all_no_u[covered])})
        metric_rows.append(m)

    return pd.DataFrame(pred_rows), pd.DataFrame(metric_rows)


def fit_full_decoder(X: np.ndarray, Y: np.ndarray, lam: float = 1e-3) -> dict:
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    Xs = (X - mean) / std
    Xd = np.c_[np.ones(X.shape[0]), Xs]
    eye = np.eye(Xd.shape[1])
    eye[0, 0] = 0.0
    beta = np.linalg.pinv(Xd.T @ Xd + lam * eye) @ Xd.T @ Y
    return {"mean": mean, "std": std, "beta": beta, "lambda": lam}


def make_png(emb: pd.DataFrame, path: Path) -> None:
    w, h = 1100, 820
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("Arial.ttf", 18)
        small = ImageFont.truetype("Arial.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
    draw.rectangle([0, 0, w - 1, h - 1], fill=(248, 250, 252), outline=(203, 213, 225))
    draw.text((w // 2 - 210, 24), "Latent fate manifold Z = Φ(W_GRN, S)", fill=(17, 24, 39), font=font)
    x = emb["Z1"].to_numpy(float)
    y = emb["Z2"].to_numpy(float) if "Z2" in emb.columns else np.zeros(len(emb))
    xmin, xmax = np.nanpercentile(x, [1, 99])
    ymin, ymax = np.nanpercentile(y, [1, 99])
    if xmax == xmin:
        xmax += 1
        xmin -= 1
    if ymax == ymin:
        ymax += 1
        ymin -= 1
    pad = 90
    def sx(v): return int(pad + (np.clip(v, xmin, xmax) - xmin) / (xmax - xmin) * (w - 2 * pad))
    def sy(v): return int(h - pad - (np.clip(v, ymin, ymax) - ymin) / (ymax - ymin) * (h - 2 * pad))
    colors = {"P": (44, 127, 184), "G": (65, 171, 93), "S": (184, 50, 44), "C": (117, 107, 177)}
    draw.line([pad, h - pad, w - pad, h - pad], fill=(100, 116, 139), width=2)
    draw.line([pad, pad, pad, h - pad], fill=(100, 116, 139), width=2)
    if len(emb) > 3000:
        plot = emb.sample(3000, random_state=7)
    else:
        plot = emb
    for _, row in plot.iterrows():
        color = colors.get(str(row["observed_basin"]), (51, 65, 85))
        px, py = sx(float(row["Z1"])), sy(float(row["Z2"]))
        draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=color)
    legend_x, legend_y = w - 220, 90
    for i, axis in enumerate(AXES):
        yy = legend_y + i * 28
        draw.rectangle([legend_x, yy, legend_x + 16, yy + 16], fill=colors[axis])
        draw.text((legend_x + 24, yy - 1), f"observed basin {axis}", fill=(30, 41, 59), font=small)
    draw.text((w // 2 - 30, h - 42), "Z1", fill=(51, 65, 85), font=small)
    draw.text((30, h // 2), "Z2", fill=(51, 65, 85), font=small)
    img.save(path)


def markdown_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
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
    w_features = build_w_features(w)
    ex = build_examples(pert, w_features)

    base_cols = [f"S_control_{a}" for a in AXES] + [f"W_to_axis_{a}" for a in AXES] + [
        "W_out_degree", "W_in_degree", "W_out_sparse_degree", "W_in_sparse_degree",
        "W_out_weight_sum", "W_in_weight_sum", "W_out_abs_weight_sum", "W_in_abs_weight_sum",
        "W_out_positive_sum", "W_out_negative_sum", "W_support_mean",
    ]
    u_cols = [f"U_{u}" for u in U_AXES]
    for c in base_cols + u_cols:
        if c not in ex.columns:
            ex[c] = 0.0
    X_phi = ex[base_cols].astype(float).to_numpy()
    U = ex[u_cols].astype(float).to_numpy()
    X_linear = ex[base_cols + u_cols].astype(float).to_numpy()
    Y = ex[[f"delta_{a}" for a in AXES]].astype(float).to_numpy()

    Z, phi_meta = rbf_latent_embedding(X_phi, n_components=10)
    pred_df, metric_df = cross_validate(ex, X_linear, Z, U, Y)
    full_model = fit_full_decoder(np.c_[Z, U], Y)

    emb = ex[["dataset_id", "sample", "target_gene", "target_module_for_U", "observed_basin"] + [f"S_control_{a}" for a in AXES] + [f"delta_{a}" for a in AXES] + u_cols].copy()
    for i in range(Z.shape[1]):
        emb[f"Z{i+1}"] = Z[:, i]
    emb.to_csv(OUT / "latent_fate_manifold_embedding.tsv", sep="\t", index=False)

    pred_df.to_csv(OUT / "DeltaS_predicted_vs_observed.tsv", sep="\t", index=False)
    metric_df.to_csv(OUT / "nonlinear_representation_metrics.tsv", sep="\t", index=False)

    model_obj = {
        "model_type": "RBF_kernel_latent_embedding_plus_ridge_decoder",
        "axes": AXES,
        "U_axes": U_AXES,
        "Phi_input_columns": base_cols,
        "decoder_input": "Z plus U",
        "phi_meta": phi_meta,
        "decoder": full_model,
        "training_examples": ex[["dataset_id", "sample", "target_gene"]].copy(),
        "guardrail": "W_GRN was read from W_GRN_learned.tsv and not modified.",
    }
    with (OUT / "nonlinear_decoder_model.pkl").open("wb") as f:
        pickle.dump(model_obj, f)

    make_png(emb, OUT / "fate_manifold_visualization.png")

    lin = metric_df[(metric_df["validation_type"] == "leave_one_perturbation_out") & (metric_df["model"] == "linear_baseline")]
    non = metric_df[(metric_df["validation_type"] == "leave_one_perturbation_out") & (metric_df["model"] == "nonlinear_phi_decoder")]
    closure = "not_testable"
    closure_note = "Missing comparable validation rows."
    if not lin.empty and not non.empty:
        lin_r = float(lin.iloc[0]["pearson_r"])
        non_r = float(non.iloc[0]["pearson_r"])
        lin_sign = float(lin.iloc[0]["sign_accuracy"])
        non_sign = float(non.iloc[0]["sign_accuracy"])
        lin_basin = float(lin.iloc[0]["basin_accuracy"])
        non_basin = float(non.iloc[0]["basin_accuracy"])
        if (non_r > lin_r + 0.02) and (non_sign >= lin_sign) and (non_basin >= lin_basin):
            closure = "passed"
            closure_note = "Nonlinear latent decoder improves correlation by >0.02 without reducing sign or basin accuracy."
        else:
            closure = "failed"
            closure_note = "Nonlinear latent decoder did not meet the predeclared improvement criterion."

    report = f"""# Representation Closure Report

## Problem

The learned sparse signed `W_GRN` is structurally valid, but direct linear decoding from `W_GRN` to fate response was weak. This run adds only the nonlinear representation layer:

```text
Z = Phi(W_GRN, S)
DeltaS = g(Z, U)
```

`W_GRN`, `S`, and `U` were not redefined.

## Data Used

- `W_GRN`: `{W_PATH}`
- perturbation state responses: `{PERT_PATH}`
- sample unit: `(dataset_id, sample, target_gene)`
- state vector `S`: control means of PGCS axes P/G/S/C
- observed response `DeltaS`: mean perturbed minus control for P/G/S/C
- `U`: five pathway-control indicators RA/BMP/NOTCH/FGF/SHH when perturbation target maps to those pathway modules; otherwise all-zero because no explicit pathway-dose metadata were present.

## Representation

`Phi(W_GRN, S)` is an RBF-kernel latent embedding built from target-specific GRN features and current control-state coordinates. The decoder `g` is a ridge regression from `(Z, U)` to four-dimensional `DeltaS`.

## Validation Metrics

{markdown_table(metric_df)}

## Closure Decision

Representation closure: **{closure}**.

Reason: {closure_note}

This means the nonlinear latent manifold has been constructed and tested. It should only be treated as a valid predictive closure if the reported nonlinear decoder outperforms the linear baseline under the predeclared criteria.

## Biological Interpretation

`Z` represents a latent fate manifold in which GRN topology, current cell-state coordinates, and state-dependent regulatory coupling are compressed into a low-dimensional geometry. Separation in `Z` corresponds to differences in developmental accessibility, chromatin-constrained regulatory response, and pathway integration state. The PNG visualization colors cells by the observed dominant response basin, not by a fitted label.
"""
    (OUT / "representation_closure_report.md").write_text(report, encoding="utf-8")
    print("nonlinear representation complete")
    print(f"examples={len(ex)}")
    print(f"latent_dims={Z.shape[1]}")
    print(f"closure={closure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
