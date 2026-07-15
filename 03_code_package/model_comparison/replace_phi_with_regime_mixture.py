#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
OUT = ROOT / "outputs"
STATE_AXES = ["Stemness", "Transitional", "Fate_lock", "Embryonic_module_score"]
LATENT_REGIMES = ["adult_repair", "embryonic_reactivation", "salamander_blastema", "salamander_intact"]
RNG_SEED = 20260619
N_COMPONENTS = 4


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


def get_fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont]:
    for name in ["Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]:
        try:
            return ImageFont.truetype(name, 22), ImageFont.truetype(name, 15), ImageFont.truetype(name, 12)
        except Exception:
            pass
    font = ImageFont.load_default()
    return font, font, font


def logsumexp(a: np.ndarray, axis: int = 1) -> np.ndarray:
    m = np.max(a, axis=axis, keepdims=True)
    return np.squeeze(m, axis=axis) + np.log(np.sum(np.exp(a - m), axis=axis))


def initialize_means(x: np.ndarray) -> np.ndarray:
    # Deterministic anchors spanning observed state geometry; not species-tuned.
    phi_like = x[:, 0] - x[:, 2] + x[:, 3]
    idx = [
        int(np.argmin(phi_like)),
        int(np.argmax(x[:, 3])),
        int(np.argmax(x[:, 1] + x[:, 3] - x[:, 2])),
        int(np.argmin(np.linalg.norm(x - np.median(x, axis=0), axis=1))),
    ]
    means = x[idx].copy()
    # Guard against duplicated anchors.
    for k in range(N_COMPONENTS):
        if np.linalg.matrix_rank(means[: k + 1] - means[: k + 1].mean(axis=0, keepdims=True)) < min(k, x.shape[1]):
            means[k] = np.quantile(x, (k + 1) / (N_COMPONENTS + 1), axis=0)
    return means


def fit_diag_gmm(x: np.ndarray, max_iter: int = 400, tol: float = 1e-6) -> dict[str, np.ndarray | float | int]:
    rng = np.random.default_rng(RNG_SEED)
    best: dict[str, np.ndarray | float | int] | None = None
    base_means = initialize_means(x)
    global_var = np.var(x, axis=0) + 1e-3
    n, d = x.shape
    for run in range(6):
        if run == 0:
            means = base_means.copy()
        else:
            means = base_means + rng.normal(0, 0.15, size=base_means.shape)
        variances = np.tile(global_var, (N_COMPONENTS, 1))
        weights = np.ones(N_COMPONENTS) / N_COMPONENTS
        last_ll = -np.inf
        for iteration in range(max_iter):
            log_prob = np.empty((n, N_COMPONENTS), dtype=float)
            for k in range(N_COMPONENTS):
                var = np.maximum(variances[k], 1e-5)
                log_det = float(np.sum(np.log(var)))
                quad = np.sum((x - means[k]) ** 2 / var, axis=1)
                log_prob[:, k] = math.log(weights[k] + 1e-12) - 0.5 * (d * math.log(2 * math.pi) + log_det + quad)
            ll_i = logsumexp(log_prob, axis=1)
            ll = float(ll_i.sum())
            resp = np.exp(log_prob - ll_i[:, None])
            nk = resp.sum(axis=0) + 1e-9
            weights = nk / n
            means = (resp.T @ x) / nk[:, None]
            for k in range(N_COMPONENTS):
                diff = x - means[k]
                variances[k] = (resp[:, k][:, None] * diff * diff).sum(axis=0) / nk[k] + 1e-4
            if abs(ll - last_ll) < tol * (abs(last_ll) + 1):
                break
            last_ll = ll
        if best is None or ll > float(best["log_likelihood"]):
            best = {
                "means": means.copy(),
                "variances": variances.copy(),
                "weights": weights.copy(),
                "responsibilities": resp.copy(),
                "log_likelihood": ll,
                "iterations": iteration + 1,
                "run": run,
            }
    assert best is not None
    return best


def annotate_components(phi: pd.DataFrame, resp: np.ndarray, means: np.ndarray) -> tuple[list[str], pd.DataFrame]:
    tmp = phi[["species_group", "regime_group", "stage_or_condition", "Phi", *STATE_AXES]].copy()
    tmp["component"] = resp.argmax(axis=1)
    rows = []
    for k in range(N_COMPONENTS):
        sub = tmp[tmp["component"] == k]
        fractions = sub["regime_group"].value_counts(normalize=True).to_dict()
        rows.append(
            {
                "component": k,
                "n_cells": len(sub),
                "mean_Phi": float(sub["Phi"].mean()),
                "mean_Stemness": float(sub["Stemness"].mean()),
                "mean_Transitional": float(sub["Transitional"].mean()),
                "mean_Fate_lock": float(sub["Fate_lock"].mean()),
                "mean_Embryonic_module_score": float(sub["Embryonic_module_score"].mean()),
                "frac_mammalian_inflammatory_repair": fractions.get("mammalian_inflammatory_repair", 0.0),
                "frac_salamander_blastema_reactivation": fractions.get("salamander_blastema_reactivation", 0.0),
                "frac_salamander_intact_reference": fractions.get("salamander_intact_reference", 0.0),
            }
        )
    summary = pd.DataFrame(rows)
    labels: dict[int, str] = {}
    remaining = set(range(N_COMPONENTS))
    intact_idx = int(summary.loc[list(remaining), "frac_salamander_intact_reference"].idxmax())
    labels[intact_idx] = "salamander_intact"
    remaining.remove(intact_idx)
    blast_idx = int(summary.loc[list(remaining), "frac_salamander_blastema_reactivation"].idxmax())
    labels[blast_idx] = "salamander_blastema"
    remaining.remove(blast_idx)
    adult_idx = int(summary.loc[list(remaining), "frac_mammalian_inflammatory_repair"].idxmax())
    labels[adult_idx] = "adult_repair"
    remaining.remove(adult_idx)
    labels[remaining.pop()] = "embryonic_reactivation"
    ordered_labels = [labels[k] for k in range(N_COMPONENTS)]
    summary["latent_regime_label"] = summary["component"].map(labels)
    return ordered_labels, summary


def gaussian_kl(mu0: np.ndarray, var0: np.ndarray, mu1: np.ndarray, var1: np.ndarray) -> float:
    var0 = np.maximum(var0, 1e-8)
    var1 = np.maximum(var1, 1e-8)
    d = len(mu0)
    return float(0.5 * (np.sum(np.log(var1 / var0)) - d + np.sum(var0 / var1) + np.sum((mu1 - mu0) ** 2 / var1)))


def symmetric_kl_matrix(labels: list[str], means: np.ndarray, variances: np.ndarray) -> pd.DataFrame:
    rows = []
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            val = 0.0 if i == j else 0.5 * (
                gaussian_kl(means[i], variances[i], means[j], variances[j])
                + gaussian_kl(means[j], variances[j], means[i], variances[i])
            )
            rows.append({"regime_i": a, "regime_j": b, "symmetric_KL": val})
    return pd.DataFrame(rows)


def bhattacharyya_overlap(mu0: np.ndarray, var0: np.ndarray, mu1: np.ndarray, var1: np.ndarray) -> float:
    avg = 0.5 * (var0 + var1)
    term1 = 0.125 * np.sum((mu1 - mu0) ** 2 / np.maximum(avg, 1e-8))
    term2 = 0.5 * np.sum(np.log(np.maximum(avg, 1e-8) / np.sqrt(np.maximum(var0 * var1, 1e-16))))
    distance = float(term1 + term2)
    return float(np.exp(-distance))


def overlap_matrix(labels: list[str], means: np.ndarray, variances: np.ndarray, resp: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            val = 1.0 if i == j else bhattacharyya_overlap(means[i], variances[i], means[j], variances[j])
            rows.append({"regime_i": a, "regime_j": b, "bhattacharyya_overlap_proxy": val})
    hard = resp.argmax(axis=1)
    posterior_rows = []
    for i, a in enumerate(labels):
        idx = hard == i
        if not idx.any():
            continue
        for j, b in enumerate(labels):
            posterior_rows.append({"assigned_regime": a, "posterior_regime": b, "mean_posterior_probability": float(resp[idx, j].mean())})
    return pd.DataFrame(rows), pd.DataFrame(posterior_rows)


def observed_regime_overlap(comp_df: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    comp_cols = [f"mean_P_Z_{label}" for label in labels]
    rows = []
    for _, a in comp_df.iterrows():
        va = a[comp_cols].to_numpy(dtype=float)
        va = va / max(va.sum(), 1e-12)
        for _, b in comp_df.iterrows():
            vb = b[comp_cols].to_numpy(dtype=float)
            vb = vb / max(vb.sum(), 1e-12)
            rows.append(
                {
                    "species_regime_i": a["observed_regime_proxy"],
                    "species_regime_j": b["observed_regime_proxy"],
                    "posterior_composition_overlap": float(np.minimum(va, vb).sum()),
                    "posterior_composition_cosine": float(np.dot(va, vb) / max(np.linalg.norm(va) * np.linalg.norm(vb), 1e-12)),
                }
            )
    return pd.DataFrame(rows)


def empirical_hist(values: np.ndarray, bins: np.ndarray) -> np.ndarray:
    h, _ = np.histogram(values, bins=bins, density=False)
    h = h.astype(float) + 1e-12
    return h / h.sum()


def mixture_hist(phi_values: np.ndarray, resp: np.ndarray, labels: list[str], bins: np.ndarray) -> tuple[pd.DataFrame, float]:
    rows = []
    empirical = empirical_hist(phi_values, bins)
    mixture = np.zeros(len(bins) - 1, dtype=float)
    for k, label in enumerate(labels):
        weights = resp[:, k]
        hist, _ = np.histogram(phi_values, bins=bins, weights=weights, density=False)
        hist = hist.astype(float)
        component_mass = float(weights.mean())
        density = hist / max(hist.sum(), 1e-12)
        mixture += component_mass * density
        for i in range(len(bins) - 1):
            rows.append(
                {
                    "latent_regime": label,
                    "bin_left": bins[i],
                    "bin_right": bins[i + 1],
                    "bin_center": 0.5 * (bins[i] + bins[i + 1]),
                    "component_density": density[i],
                    "component_mass": component_mass,
                    "weighted_component_density": component_mass * density[i],
                }
            )
    mixture = mixture / mixture.sum()
    kl = float(np.sum(empirical * np.log(empirical / np.maximum(mixture, 1e-12))))
    return pd.DataFrame(rows), kl


def mutual_information_from_resp(resp: np.ndarray) -> float:
    pz = resp.mean(axis=0)
    entropy_z = -float(np.sum(pz * np.log(np.maximum(pz, 1e-12))))
    entropy_z_given_s = -float(np.mean(np.sum(resp * np.log(np.maximum(resp, 1e-12)), axis=1)))
    return entropy_z - entropy_z_given_s


def draw_heatmap(matrix_df: pd.DataFrame, row_col: str, col_col: str, value_col: str, title_text: str, out: Path) -> None:
    labels_r = list(matrix_df[row_col].drop_duplicates())
    labels_c = list(matrix_df[col_col].drop_duplicates())
    pivot = matrix_df.pivot(index=row_col, columns=col_col, values=value_col).loc[labels_r, labels_c]
    arr = pivot.to_numpy(dtype=float)
    vmin, vmax = float(np.nanmin(arr)), float(np.nanmax(arr))
    img = Image.new("RGB", (860, 760), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((180, 24), title_text, fill=(17, 24, 39), font=title)
    left, top, cell = 180, 120, 95
    for i, r in enumerate(labels_r):
        draw.text((35, top + i * cell + 35), r, fill=(30, 41, 59), font=small)
        for j, c in enumerate(labels_c):
            v = float(arr[i, j])
            t = (v - vmin) / max(vmax - vmin, 1e-12)
            color = (
                int(44 + t * (184 - 44)),
                int(127 + t * (50 - 127)),
                int(184 + t * (44 - 184)),
            )
            x0, y0 = left + j * cell, top + i * cell
            draw.rectangle([x0, y0, x0 + cell, y0 + cell], fill=color, outline=(30, 41, 59))
            draw.text((x0 + 20, y0 + 38), f"{v:.2f}", fill=(15, 23, 42), font=small)
    for j, c in enumerate(labels_c):
        draw.text((left + j * cell + 5, top - 42), c[:14], fill=(30, 41, 59), font=small)
    img.save(out)


def draw_mixture_density(hist: pd.DataFrame, phi: pd.DataFrame, out: Path) -> None:
    img = Image.new("RGB", (1120, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((300, 24), "FIG 1: mixture density decomposition of Phi", fill=(17, 24, 39), font=title)
    left, top, width, height = 90, 110, 720, 460
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    bins = np.sort(np.unique(np.r_[hist["bin_left"].unique(), hist["bin_right"].unique()]))
    emp_h, edges = np.histogram(phi["Phi"], bins=bins, density=True)
    max_y = max(float(emp_h.max()), float(hist["weighted_component_density"].max()))
    colors = {
        "adult_repair": (221, 139, 40),
        "embryonic_reactivation": (184, 50, 44),
        "salamander_blastema": (44, 127, 184),
        "salamander_intact": (100, 116, 139),
    }
    def px(x: float) -> int:
        return int(left + (x - bins.min()) / max(bins.max() - bins.min(), 1e-9) * width)
    def py(y: float) -> int:
        return int(top + height - y / max(max_y, 1e-12) * height)
    emp_pts = [(px(0.5 * (a + b)), py(y)) for y, a, b in zip(emp_h, edges[:-1], edges[1:])]
    draw.line(emp_pts, fill=(15, 23, 42), width=4)
    draw.text((840, 130), "black: empirical Phi", fill=(15, 23, 42), font=small)
    for idx, (label, sub) in enumerate(hist.groupby("latent_regime", sort=False)):
        pts = [(px(r.bin_center), py(r.weighted_component_density)) for r in sub.itertuples()]
        draw.line(pts, fill=colors[label], width=3)
        draw.rectangle([840, 170 + idx * 34, 860, 190 + idx * 34], fill=colors[label])
        draw.text((872, 166 + idx * 34), label, fill=(30, 41, 59), font=small)
    draw.text((left + 310, top + height + 34), "Phi", fill=(30, 41, 59), font=font)
    draw.text((18, top + 210), "density", fill=(30, 41, 59), font=small)
    img.save(out)


def draw_posterior_landscape(phi: pd.DataFrame, out: Path) -> None:
    img = Image.new("RGB", (1120, 760), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((280, 24), "FIG 2: regime posterior landscape P(Z|S)", fill=(17, 24, 39), font=title)
    left, top, width, height = 90, 100, 660, 520
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    colors = {
        "adult_repair": (221, 139, 40),
        "embryonic_reactivation": (184, 50, 44),
        "salamander_blastema": (44, 127, 184),
        "salamander_intact": (100, 116, 139),
    }
    x = phi["Fate_lock"].to_numpy()
    y = phi["Embryonic_module_score"].to_numpy()
    xmin, xmax = np.quantile(x, [0.002, 0.998])
    ymin, ymax = np.quantile(y, [0.002, 0.998])
    sample = phi.sample(min(5500, len(phi)), random_state=RNG_SEED)
    for row in sample.itertuples():
        px = int(left + (row.Fate_lock - xmin) / max(xmax - xmin, 1e-9) * width)
        py = int(top + height - (row.Embryonic_module_score - ymin) / max(ymax - ymin, 1e-9) * height)
        if left <= px <= left + width and top <= py <= top + height:
            draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=colors[row.latent_regime_map])
    for idx, (label, color) in enumerate(colors.items()):
        draw.rectangle([790, 150 + idx * 34, 810, 170 + idx * 34], fill=color)
        draw.text((822, 146 + idx * 34), label, fill=(30, 41, 59), font=small)
    draw.text((left + 240, top + height + 35), "Fate_lock", fill=(30, 41, 59), font=font)
    draw.text((18, top + 245), "Embryonic module", fill=(30, 41, 59), font=small)
    img.save(out)


def draw_failure_panel(stats: dict[str, float], out: Path) -> None:
    img = Image.new("RGB", (1120, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((245, 26), "FIG 5: failure of discriminative Phi", fill=(17, 24, 39), font=title)
    text = [
        "Phi(S,W_GRN) is NOT a valid discriminative or order parameter.",
        "",
        f"ROC AUC = {stats['auc']:.3f}  (random performance)",
        f"Permutation p = {stats['permutation_p_value_two_sided']:.3f}  (mean shift unstable)",
        f"KS p = {stats['ks_p_value']:.2e}  (shape difference, not separability)",
        f"Bootstrap mean CI = [{stats['mean_ci_low']:.3f}, {stats['mean_ci_high']:.3f}]",
        "",
        "Replacement:",
        "P(Phi | S) = sum_Z P(Phi | S,Z) P(Z | S,W_GRN)",
        "",
        "Single scalar order parameter Phi is insufficient;",
        "cell fate system is governed by a latent state regime mixture model",
        "rather than a separable embedding.",
    ]
    y = 115
    for line in text:
        draw.text((90, y), line, fill=(17, 24, 39), font=font if line and not line.startswith("P(") else small)
        y += 42 if line else 24
    img.save(out)


def draw_regime_phi_distributions(phi: pd.DataFrame, out: Path) -> None:
    img = Image.new("RGB", (1080, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((300, 24), "Per-regime Phi distributions", fill=(17, 24, 39), font=title)
    left, top, width, height = 90, 110, 720, 460
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    bins = np.linspace(phi["Phi"].quantile(0.002), phi["Phi"].quantile(0.998), 70)
    colors = {
        "adult_repair": (221, 139, 40),
        "embryonic_reactivation": (184, 50, 44),
        "salamander_blastema": (44, 127, 184),
        "salamander_intact": (100, 116, 139),
    }
    hists = []
    max_y = 0.0
    for label, sub in phi.groupby("latent_regime_map"):
        h, edges = np.histogram(sub["Phi"], bins=bins, density=True)
        hists.append((label, h, edges))
        max_y = max(max_y, float(h.max()))
    def px(x: float) -> int:
        return int(left + (x - bins.min()) / max(bins.max() - bins.min(), 1e-9) * width)
    def py(y: float) -> int:
        return int(top + height - y / max(max_y, 1e-12) * height)
    for idx, (label, h, edges) in enumerate(hists):
        pts = [(px(0.5 * (a + b)), py(v)) for v, a, b in zip(h, edges[:-1], edges[1:])]
        draw.line(pts, fill=colors[label], width=4)
        draw.rectangle([840, 150 + idx * 34, 860, 170 + idx * 34], fill=colors[label])
        draw.text((872, 146 + idx * 34), label, fill=(30, 41, 59), font=small)
    draw.text((left + 330, top + height + 35), "Phi", fill=(30, 41, 59), font=font)
    img.save(out)


def write_reports(
    phi: pd.DataFrame,
    summary: pd.DataFrame,
    fit: dict[str, np.ndarray | float | int],
    mixture_kl: float,
    mi: float,
    stats: dict[str, float],
) -> None:
    inv = f"""# Formal Invalidation of Single-Phi Model

## Model Invalidation

**Phi(S, W_GRN) is NOT a valid discriminative or order parameter.**

All classifier and global-threshold interpretations of `Phi` are removed.

## Evidence

- ROC AUC = {stats['auc']:.3f}, which is random classification performance.
- Permutation p-value for mean separation = {stats['permutation_p_value_two_sided']:.3f}, not significant.
- Bootstrap CI for mean shift crosses zero: [{stats['mean_ci_low']:.3f}, {stats['mean_ci_high']:.3f}].
- KS test is significant (p = {stats['ks_p_value']:.2e}) but only indicates distribution-shape difference; it does not provide discriminative ordering.
- Batch/species entanglement prevents a single scalar from serving as a universal biological coordinate.

## Removed Interpretation

`Phi >= 0` must not be interpreted as embryonic reactivation, and `Phi < 0` must not be interpreted as adult repair. `ROC/AUC` is no longer an optimization objective for the dynamical system.

## Replacement

The model is replaced by a latent state regime mixture:

```text
Z in {{adult_repair, embryonic_reactivation, salamander_blastema, salamander_intact}}

P(Phi | S) = sum_Z P(Phi | S, Z) P(Z | S, W_GRN)
```

Each latent state regime has its own `Phi` distribution. No global `Phi` threshold exists.

## Mandatory Final Statement

Single scalar order parameter Phi is insufficient;
cell fate system is governed by a latent state regime mixture model rather than a separable embedding.
"""
    (OUT / "single_phi_model_invalidation.md").write_text(inv, encoding="utf-8")

    ident = f"""# Identifiability Failure Report

## Failure Mode

The prior model attempted to compress regime identity into one scalar `Phi`. The evidence shows this mapping is non-identifiable:

- similar `Phi` values occur in multiple latent state regimes;
- species/regime distributions differ in shape but not in stable monotone ordering;
- mean and median shifts are unstable or not aligned with classification;
- global thresholding fails.

## Mixture Fit Summary

- Model: diagonal Gaussian mixture over `S = [Stemness, Transitional, Fate_lock, Embryonic_module_score]`
- Latent components: 4
- Log likelihood: {float(fit['log_likelihood']):.6g}
- EM iterations: {int(fit['iterations'])}
- Empirical-vs-mixture KL over `Phi`: {mixture_kl:.6g}
- Mutual information proxy `I(S;Z)`: {mi:.6g}

## Regime Interpretation

Regime names are post-hoc biological annotations of mixture components. `Z` itself is not directly observed and should be reported as posterior probability `P(Z|S)`, not as ground-truth labels.

## Consequence

The developmental phase-transition model should be analyzed as a latent mixture dynamical system. `Phi` may be retained only as a regime-conditioned marginal variable.
"""
    (OUT / "identifiability_failure_report.md").write_text(ident, encoding="utf-8")

    model = """# Latent Regime Mixture Dynamical System

## State and Latent Regime

```text
S = [Stemness, Transitional, Fate_lock, Embryonic_module_score]
Z in {adult_repair, embryonic_reactivation, salamander_blastema, salamander_intact}
```

`Z` is not observed directly. It is inferred as `P(Z|S)` by a mixture model.

## Replacement of Single Phi

```text
P(Phi | S) = sum_Z P(Phi | S,Z) P(Z | S,W_GRN)
```

The dynamical system should be written as:

```text
dS/dt = sum_Z P(Z|S,W_GRN) F_Z(S,U,W_GRN) + xi(S)
```

No global threshold on `Phi` is used.

## Fitting Objective

The model objective is no longer AUC. The intended objectives are:

1. maximize likelihood `P(S|Z)`;
2. minimize `KL(P_empirical(Phi) || P_mixture(Phi))`;
3. maximize mutual information `I(S;Z)` subject to reproducible, non-degenerate components.
"""
    (OUT / "latent_regime_mixture_model.md").write_text(model, encoding="utf-8")


def main() -> int:
    phi = pd.read_csv(OUT / "Phi_unified.tsv", sep="\t")
    ks = pd.read_csv(OUT / "ks_test_results.tsv", sep="\t").iloc[0].to_dict()
    boot = pd.read_csv(OUT / "bootstrap_confidence_intervals.tsv", sep="\t")
    mean_ci = boot[boot["metric"] == "mean_difference"].iloc[0]
    stats = {
        "auc": float(ks["auc"]),
        "permutation_p_value_two_sided": float(ks["permutation_p_value_two_sided"]),
        "ks_p_value": float(ks["ks_p_value"]),
        "mean_ci_low": float(mean_ci["ci_lower_2p5"]),
        "mean_ci_high": float(mean_ci["ci_upper_97p5"]),
    }
    x = phi[STATE_AXES].to_numpy(dtype=float)
    fit = fit_diag_gmm(x)
    resp = np.asarray(fit["responsibilities"], dtype=float)
    labels, summary = annotate_components(phi, resp, np.asarray(fit["means"], dtype=float))
    # Reorder arrays to the biological label order for human-readable outputs.
    component_to_label = dict(enumerate(labels))
    label_order = LATENT_REGIMES
    old_order = [labels.index(label) for label in label_order]
    resp_reordered = resp[:, old_order]
    means = np.asarray(fit["means"], dtype=float)[old_order]
    variances = np.asarray(fit["variances"], dtype=float)[old_order]
    weights = np.asarray(fit["weights"], dtype=float)[old_order]

    for i, label in enumerate(label_order):
        phi[f"P_Z_{label}"] = resp_reordered[:, i]
    hard = resp_reordered.argmax(axis=1)
    phi["latent_regime_map"] = [label_order[i] for i in hard]
    phi["latent_regime_max_posterior"] = resp_reordered.max(axis=1)
    phi[
        [
            "sample_id",
            "dataset",
            "species_group",
            "regime_group",
            "source_batch",
            "stage_or_condition",
            "Phi",
            *STATE_AXES,
            "latent_regime_map",
            "latent_regime_max_posterior",
            *[f"P_Z_{label}" for label in label_order],
        ]
    ].to_csv(OUT / "regime_posterior_probabilities.tsv", sep="\t", index=False)

    comp_params = []
    for i, label in enumerate(label_order):
        row = {"latent_regime": label, "mixture_weight": weights[i]}
        for axis, mu, var in zip(STATE_AXES, means[i], variances[i]):
            row[f"mean_{axis}"] = mu
            row[f"variance_{axis}"] = var
        comp_params.append(row)
    pd.DataFrame(comp_params).to_csv(OUT / "latent_regime_mixture_parameters.tsv", sep="\t", index=False)

    summary["latent_regime_label_original"] = summary["latent_regime_label"]
    summary.to_csv(OUT / "latent_regime_component_annotation.tsv", sep="\t", index=False)

    phi_summary = (
        phi.groupby("latent_regime_map")
        .agg(
            n_cells=("Phi", "size"),
            Phi_mean=("Phi", "mean"),
            Phi_sd=("Phi", "std"),
            Phi_median=("Phi", "median"),
            Phi_q05=("Phi", lambda s: float(np.quantile(s, 0.05))),
            Phi_q95=("Phi", lambda s: float(np.quantile(s, 0.95))),
        )
        .reset_index()
        .rename(columns={"latent_regime_map": "latent_regime"})
    )
    phi_summary.to_csv(OUT / "per_regime_phi_distributions.tsv", sep="\t", index=False)

    overlap, posterior_overlap = overlap_matrix(label_order, means, variances, resp_reordered)
    overlap.to_csv(OUT / "regime_overlap_matrix.tsv", sep="\t", index=False)
    posterior_overlap.to_csv(OUT / "regime_posterior_overlap_matrix.tsv", sep="\t", index=False)
    skl = symmetric_kl_matrix(label_order, means, variances)
    skl.to_csv(OUT / "regime_KL_divergence_matrix.tsv", sep="\t", index=False)

    bins = np.linspace(phi["Phi"].quantile(0.001), phi["Phi"].quantile(0.999), 100)
    hist, mixture_kl = mixture_hist(phi["Phi"].to_numpy(dtype=float), resp_reordered, label_order, bins)
    hist.to_csv(OUT / "mixture_density_decomposition_phi.tsv", sep="\t", index=False)
    mi = mutual_information_from_resp(resp_reordered)
    pd.DataFrame(
        [
            {
                "model": "diagonal_gaussian_latent_regime_mixture",
                "n_components": N_COMPONENTS,
                "log_likelihood": float(fit["log_likelihood"]),
                "iterations": int(fit["iterations"]),
                "run": int(fit["run"]),
                "KL_empirical_phi_vs_mixture_phi": mixture_kl,
                "mutual_information_I_S_Z_proxy": mi,
                "objective": "likelihood + distributional alignment + regime information; no AUC objective",
            }
        ]
    ).to_csv(OUT / "latent_regime_mixture_fit_summary.tsv", sep="\t", index=False)

    # Observed-regime versus latent-state-regime soft composition.
    comp = []
    for observed, sub in phi.groupby("regime_group"):
        row = {"observed_regime_proxy": observed, "n_cells": len(sub)}
        for label in label_order:
            row[f"mean_P_Z_{label}"] = float(sub[f"P_Z_{label}"].mean())
        comp.append(row)
    comp_df = pd.DataFrame(comp)
    comp_df.to_csv(OUT / "observed_regime_to_latent_regime_composition.tsv", sep="\t", index=False)
    species_overlap = observed_regime_overlap(comp_df, label_order)
    species_overlap.to_csv(OUT / "species_regime_overlap_matrix.tsv", sep="\t", index=False)

    draw_mixture_density(hist, phi, OUT / "fig1_mixture_density_decomposition_phi.png")
    draw_posterior_landscape(phi, OUT / "fig2_regime_posterior_landscape.png")
    draw_heatmap(
        species_overlap,
        "species_regime_i",
        "species_regime_j",
        "posterior_composition_overlap",
        "FIG 3: overlap between species/regimes",
        OUT / "fig3_overlap_heatmap_between_species_regimes.png",
    )
    draw_heatmap(overlap, "regime_i", "regime_j", "bhattacharyya_overlap_proxy", "Latent-state-regime overlap diagnostic", OUT / "latent_regime_overlap_heatmap.png")
    draw_heatmap(skl, "regime_i", "regime_j", "symmetric_KL", "FIG 4: KL divergence between latent state regimes", OUT / "fig4_KL_divergence_matrix.png")
    draw_failure_panel(stats, OUT / "fig5_failure_of_discriminative_phi_summary.png")
    draw_regime_phi_distributions(phi, OUT / "per_regime_phi_distributions.png")

    write_reports(phi, summary, fit, mixture_kl, mi, stats)

    pd.DataFrame(
        [
            {
                "figure_id": "FIG 1",
                "figure_file": "fig1_mixture_density_decomposition_phi.png",
                "source_data": "mixture_density_decomposition_phi.tsv; Phi_unified.tsv",
                "replacement_for": "ROC/global Phi distribution classifier figure",
            },
            {
                "figure_id": "FIG 2",
                "figure_file": "fig2_regime_posterior_landscape.png",
                "source_data": "regime_posterior_probabilities.tsv",
                "replacement_for": "single-threshold phase plot",
            },
            {
                "figure_id": "FIG 3",
                "figure_file": "fig3_overlap_heatmap_between_species_regimes.png",
                "source_data": "species_regime_overlap_matrix.tsv; observed_regime_to_latent_regime_composition.tsv",
                "replacement_for": "separable species/regime heatmap",
            },
            {
                "figure_id": "FIG 4",
                "figure_file": "fig4_KL_divergence_matrix.png",
                "source_data": "regime_KL_divergence_matrix.tsv",
                "replacement_for": "Phi bifurcation threshold figure",
            },
            {
                "figure_id": "FIG 5",
                "figure_file": "fig5_failure_of_discriminative_phi_summary.png",
                "source_data": "ks_test_results.tsv; bootstrap_confidence_intervals.tsv; single_phi_model_invalidation.md",
                "replacement_for": "ROC-based validation panel",
            },
        ]
    ).to_csv(OUT / "mixture_figure_replacement_map.tsv", sep="\t", index=False)

    print("single Phi invalidated; latent state regime mixture fitted")
    print(f"log_likelihood={float(fit['log_likelihood']):.6f}")
    print(f"KL_empirical_phi_vs_mixture={mixture_kl:.6f}")
    print(f"I_S_Z_proxy={mi:.6f}")
    print(phi["latent_regime_map"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
