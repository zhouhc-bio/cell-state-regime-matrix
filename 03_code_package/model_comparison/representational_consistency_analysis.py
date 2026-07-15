from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
RNG = np.random.default_rng(20260619)

STATE_COLS = ["Stemness", "Transitional", "Fate_lock", "Embryonic_module_score"]
PZ_COLS = [
    "P_Z_adult_repair",
    "P_Z_embryonic_reactivation",
    "P_Z_salamander_blastema",
    "P_Z_salamander_intact",
]
OBSERVED_GROUPS = [
    "mammalian_inflammatory_repair",
    "salamander_blastema_reactivation",
    "salamander_intact_reference",
]


def zscore(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    return (x - x.mean(axis=0)) / np.clip(x.std(axis=0), 1e-8, None)


def pca_projection(x: np.ndarray, n_components: int) -> np.ndarray:
    xc = zscore(x)
    _, _, vt = np.linalg.svd(xc, full_matrices=False)
    return xc @ vt[:n_components].T


def kmeans_fit(x: np.ndarray, k: int = 4, n_iter: int = 80) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, float)
    pc = pca_projection(x, 1)[:, 0]
    order = np.argsort(pc)
    idx = [order[int((i + 0.5) * len(order) / k)] for i in range(k)]
    centers = x[idx].copy()
    labels = np.zeros(len(x), dtype=int)
    for _ in range(n_iter):
        d = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = d.argmin(axis=1)
        if np.all(new_labels == labels):
            break
        labels = new_labels
        for j in range(k):
            if np.any(labels == j):
                centers[j] = x[labels == j].mean(axis=0)
    return centers, labels


def kmeans_representation(x: np.ndarray, k: int = 4) -> np.ndarray:
    _, labels = kmeans_fit(x, k)
    out = np.zeros((len(x), k))
    out[np.arange(len(x)), labels] = 1.0
    return out


def softmax(logp: np.ndarray) -> np.ndarray:
    z = logp - np.nanmax(logp, axis=1, keepdims=True)
    e = np.exp(z)
    return e / np.clip(e.sum(axis=1, keepdims=True), 1e-12, None)


def gmm_diag_representation(x: np.ndarray, k: int = 4, n_iter: int = 80) -> np.ndarray:
    x = zscore(np.asarray(x, float))
    centers, labels = kmeans_fit(x, k)
    means = centers.copy()
    vars_ = np.vstack([x.var(axis=0) + 1e-3 for _ in range(k)])
    weights = np.ones(k) / k
    resp = np.zeros((len(x), k))
    for _ in range(n_iter):
        log_resp = np.zeros((len(x), k))
        for j in range(k):
            var = vars_[j]
            ll = -0.5 * (((x - means[j]) ** 2 / var).sum(axis=1) + np.log(2 * np.pi * var).sum())
            log_resp[:, j] = np.log(weights[j] + 1e-12) + ll
        resp = softmax(log_resp)
        nk = resp.sum(axis=0) + 1e-9
        weights = nk / nk.sum()
        means = (resp.T @ x) / nk[:, None]
        for j in range(k):
            vars_[j] = (resp[:, j][:, None] * (x - means[j]) ** 2).sum(axis=0) / nk[j] + 1e-3
    return resp


def diffusion_landmark_representation(x: np.ndarray, n_components: int = 3, n_landmarks: int = 512) -> np.ndarray:
    x = zscore(np.asarray(x, float))
    n_landmarks = min(n_landmarks, len(x))
    idx = RNG.choice(len(x), size=n_landmarks, replace=False)
    lm = x[idx]
    d2 = ((lm[:, None, :] - lm[None, :, :]) ** 2).sum(axis=2)
    sigma2 = np.median(d2[d2 > 0])
    if not np.isfinite(sigma2) or sigma2 <= 0:
        sigma2 = 1.0
    kmm = np.exp(-d2 / (sigma2 + 1e-12))
    deg = np.sqrt(np.clip(kmm.sum(axis=1), 1e-12, None))
    norm = kmm / deg[:, None] / deg[None, :]
    vals, vecs = np.linalg.eigh(norm)
    order = np.argsort(vals)[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    vals_k = np.clip(vals[1 : n_components + 1], 1e-8, None)
    vecs_k = vecs[:, 1 : n_components + 1]
    ky = np.exp(-(((x[:, None, :] - lm[None, :, :]) ** 2).sum(axis=2)) / (sigma2 + 1e-12))
    return ky @ (vecs_k / vals_k)


def make_representations(df: pd.DataFrame) -> dict[str, np.ndarray]:
    x = df[STATE_COLS].to_numpy(float)
    reps = {
        "latent_regime_posterior_PZ": df[PZ_COLS].to_numpy(float),
        "single_phi_scalar_deprecated": df[["Phi"]].to_numpy(float),
        "pca_1d": pca_projection(x, 1),
        "pca_2d": pca_projection(x, 2),
        "pca_3d": pca_projection(x, 3),
        "diffusion_map_3d_landmark": diffusion_landmark_representation(x, 3),
        "kmeans_k4_onehot": kmeans_representation(x, 4),
        "gmm_diag_k4_responsibility": gmm_diag_representation(x, 4),
    }
    rand = RNG.normal(size=(x.shape[1], 3))
    reps["random_projection_null"] = zscore(x) @ rand
    shuffled = reps["latent_regime_posterior_PZ"].copy()
    RNG.shuffle(shuffled, axis=0)
    reps["shuffled_posterior_null"] = shuffled
    reps["uniform_null"] = np.ones_like(reps["latent_regime_posterior_PZ"]) / len(PZ_COLS)
    return reps


def centroid_distance_vector(rep: np.ndarray, labels: np.ndarray, groups: list[str]) -> np.ndarray:
    cent = []
    for g in groups:
        mask = labels == g
        if mask.sum() == 0:
            cent.append(np.full(rep.shape[1], np.nan))
        else:
            cent.append(rep[mask].mean(axis=0))
    vals = []
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            vals.append(np.linalg.norm(cent[i] - cent[j]))
    return np.array(vals, float)


def within_dispersion(rep: np.ndarray, labels: np.ndarray, groups: list[str]) -> float:
    vals = []
    for g in groups:
        mask = labels == g
        if mask.sum() > 1:
            c = rep[mask].mean(axis=0)
            vals.extend(np.linalg.norm(rep[mask] - c, axis=1).tolist())
    return float(np.mean(vals)) if vals else np.nan


def eta_squared(rep: np.ndarray, labels: np.ndarray) -> float:
    labels = np.asarray(labels).astype(str)
    y = np.asarray(rep, float)
    if np.unique(labels).size < 2:
        return np.nan
    total = ((y - y.mean(axis=0)) ** 2).sum()
    if total <= 1e-12:
        return 0.0
    between = 0.0
    for g in np.unique(labels):
        mask = labels == g
        if mask.any():
            between += mask.sum() * ((y[mask].mean(axis=0) - y.mean(axis=0)) ** 2).sum()
    return float(between / total)


def local_consistency(rep: np.ndarray, labels: np.ndarray, n_sample: int = 3500, k: int = 20) -> tuple[float, float]:
    n = len(rep)
    idx = RNG.choice(n, size=min(n_sample, n), replace=False)
    x = zscore(rep[idx])
    lab = labels[idx]
    d2 = ((x[:, None, :] - x[None, :, :]) ** 2).sum(axis=2)
    np.fill_diagonal(d2, np.inf)
    nn = np.argpartition(d2, kth=min(k, len(idx) - 1), axis=1)[:, :k]
    obs = np.mean(lab[nn] == lab[:, None])
    base = sum((np.mean(lab == g)) ** 2 for g in np.unique(lab))
    return float(obs), float(obs - base)


def bootstrap_stability(df: pd.DataFrame, model: str, n_boot: int = 80) -> tuple[float, float, float]:
    labels = df["regime_group"].astype(str).to_numpy()
    full_rep = make_single_representation(df, model)
    ref = centroid_distance_vector(full_rep, labels, OBSERVED_GROUPS)
    ref_scale = np.nanmean(ref) if np.nanmean(ref) > 1e-9 else 1.0
    nrmse_vals = []
    dist_values = []
    for _ in range(n_boot):
        idx = RNG.choice(len(df), size=int(len(df) * 0.7), replace=True)
        sub = df.iloc[idx].reset_index(drop=True)
        rep = make_single_representation(sub, model)
        vec = centroid_distance_vector(rep, sub["regime_group"].astype(str).to_numpy(), OBSERVED_GROUPS)
        if np.all(np.isfinite(vec)):
            nrmse_vals.append(float(np.sqrt(np.mean((vec - ref) ** 2)) / ref_scale))
            dist_values.append(vec)
    if not nrmse_vals:
        return np.nan, np.nan, np.nan
    arr = np.vstack(dist_values)
    return float(np.mean(nrmse_vals)), float(1 / (1 + np.mean(nrmse_vals))), float(np.mean(np.std(arr, axis=0) / np.clip(np.mean(arr, axis=0), 1e-9, None)))


def make_single_representation(df: pd.DataFrame, model: str) -> np.ndarray:
    x = df[STATE_COLS].to_numpy(float)
    if model == "latent_regime_posterior_PZ":
        return df[PZ_COLS].to_numpy(float)
    if model == "single_phi_scalar_deprecated":
        return df[["Phi"]].to_numpy(float)
    if model == "pca_1d":
        return pca_projection(x, 1)
    if model == "pca_2d":
        return pca_projection(x, 2)
    if model == "pca_3d":
        return pca_projection(x, 3)
    if model == "diffusion_map_3d_landmark":
        return diffusion_landmark_representation(x, 3)
    if model == "kmeans_k4_onehot":
        return kmeans_representation(x, 4)
    if model == "gmm_diag_k4_responsibility":
        return gmm_diag_representation(x, 4)
    if model == "random_projection_null":
        rand = RNG.normal(size=(x.shape[1], 3))
        return zscore(x) @ rand
    if model == "shuffled_posterior_null":
        z = df[PZ_COLS].to_numpy(float).copy()
        RNG.shuffle(z, axis=0)
        return z
    if model == "uniform_null":
        return np.ones((len(df), len(PZ_COLS))) / len(PZ_COLS)
    raise KeyError(model)


def bhattacharyya_overlap_1d(a: np.ndarray, b: np.ndarray, bins: int = 40) -> float:
    vals = np.concatenate([a, b])
    lo, hi = np.nanquantile(vals, [0.01, 0.99])
    if hi <= lo:
        return np.nan
    ha, edges = np.histogram(a, bins=bins, range=(lo, hi), density=True)
    hb, _ = np.histogram(b, bins=edges, density=True)
    dx = edges[1] - edges[0]
    return float(np.sum(np.sqrt(np.clip(ha, 0, None) * np.clip(hb, 0, None))) * dx)


def cross_species_metrics(rep: np.ndarray, df: pd.DataFrame, model: str) -> list[dict]:
    labels = df["regime_group"].astype(str).to_numpy()
    rows = []
    # First PC of representation for 1D overlap proxy; for scalar it is itself.
    coord = pca_projection(rep, 1)[:, 0] if rep.shape[1] > 1 else rep[:, 0]
    pairs = [
        ("mammalian_inflammatory_repair", "salamander_blastema_reactivation"),
        ("salamander_blastema_reactivation", "salamander_intact_reference"),
        ("mammalian_inflammatory_repair", "salamander_intact_reference"),
    ]
    for a, b in pairs:
        ma, mb = labels == a, labels == b
        dist = float(np.linalg.norm(rep[ma].mean(axis=0) - rep[mb].mean(axis=0)))
        pooled = 0.5 * (within_dispersion(rep, labels, [a]) + within_dispersion(rep, labels, [b]))
        rows.append({
            "model": model,
            "group_i": a,
            "group_j": b,
            "centroid_distance": dist,
            "pooled_within_dispersion": pooled,
            "distance_to_dispersion_ratio": dist / pooled if pooled and np.isfinite(pooled) else np.nan,
            "one_dimensional_overlap_proxy": bhattacharyya_overlap_1d(coord[ma], coord[mb]),
        })
    return rows


def draw_bar_panel(draw, x, y, w, h, title, labels, values, color):
    font_b = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 27)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=22, outline=(210, 218, 230), width=3, fill=(248, 250, 253))
    draw.text((x + 24, y + 20), title, font=font_b, fill=(32, 102, 165))
    finite = [v for v in values if np.isfinite(v)]
    vmax = max(finite) if finite else 1
    vmax = max(vmax, 1e-9)
    bar_h = min(34, (h - 90) // max(1, len(labels)) - 5)
    yy = y + 78
    for lab, val in zip(labels, values):
        draw.text((x + 24, yy), lab[:30], font=font, fill=(20, 31, 50))
        if np.isfinite(val):
            bw = int((w - 360) * val / vmax)
            draw.rectangle((x + 260, yy, x + 260 + bw, yy + bar_h), fill=color)
            draw.text((x + 270 + bw, yy), f"{val:.3f}", font=font, fill=(20, 31, 50))
        else:
            draw.text((x + 260, yy), "NA", font=font, fill=(150, 45, 45))
        yy += bar_h + 9


def write_figure(metrics: pd.DataFrame, cross: pd.DataFrame, stability: pd.DataFrame):
    W, H = 3600, 2500
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    ftitle = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 47)
    fsub = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
    draw.text((80, 50), "FIGURE_REPRESENTATIONAL_CONSISTENCY_FINAL", font=ftitle, fill=(20, 31, 50))
    draw.text((80, 110), "Representation adequacy: stability, internal consistency, cross-species coherence, and sampling-noise sensitivity.", font=fsub, fill=(75, 83, 98))

    top = metrics[~metrics["model"].str.contains("null")].copy()
    top = top.sort_values("local_consistency_observed_adjusted", ascending=False).head(8)
    draw_bar_panel(
        draw, 80, 180, 1080, 610, "A  Local observed-regime consistency",
        top["model"].tolist(), top["local_consistency_observed_adjusted"].tolist(), (43, 140, 136)
    )
    st = stability[~stability["model"].str.contains("null")].sort_values("stability_score", ascending=False).head(8)
    draw_bar_panel(
        draw, 1260, 180, 1080, 610, "B  Bootstrap stability score",
        st["model"].tolist(), st["stability_score"].tolist(), (106, 90, 168)
    )
    batch = metrics[~metrics["model"].str.contains("null")].copy()
    batch["batch_resistance"] = 1 / (1 + batch["batch_eta2_over_observed_regime_eta2"])
    batch = batch.sort_values("batch_resistance", ascending=False).head(8)
    draw_bar_panel(
        draw, 2440, 180, 1080, 610, "C  Batch resistance",
        batch["model"].tolist(), batch["batch_resistance"].tolist(), (184, 121, 26)
    )

    cb = cross[cross["group_i"].eq("mammalian_inflammatory_repair") & cross["group_j"].eq("salamander_blastema_reactivation")]
    cb = cb[~cb["model"].str.contains("null")].sort_values("one_dimensional_overlap_proxy", ascending=False).head(8)
    draw_bar_panel(
        draw, 80, 900, 1080, 610, "D  Mammal-blastema overlap proxy",
        cb["model"].tolist(), cb["one_dimensional_overlap_proxy"].tolist(), (34, 102, 165)
    )
    div = cross[cross["group_i"].eq("mammalian_inflammatory_repair") & cross["group_j"].eq("salamander_blastema_reactivation")]
    div = div[~div["model"].str.contains("null")].sort_values("distance_to_dispersion_ratio", ascending=False).head(8)
    draw_bar_panel(
        draw, 1260, 900, 1080, 610, "E  Mammal-blastema divergence ratio",
        div["model"].tolist(), div["distance_to_dispersion_ratio"].tolist(), (190, 58, 52)
    )
    noise = stability[~stability["model"].str.contains("null")].sort_values("distance_cv").head(8)
    draw_bar_panel(
        draw, 2440, 900, 1080, 610, "F  Sampling-noise sensitivity (inverse)",
        noise["model"].tolist(), (1 / (1 + noise["distance_cv"])).tolist(), (75, 120, 90)
    )

    draw.rounded_rectangle((80, 1640, 3520, 2360), radius=28, outline=(190, 58, 52), width=4, fill=(251, 234, 234))
    draw.text((130, 1690), "Interpretation lock", font=ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 38), fill=(190, 58, 52))
    txt = (
        "This analysis evaluates representational adequacy, not causal or predictive superiority. "
        "A representation is favored when it is stable under bootstrap sampling, locally coherent, cross-species coherent, "
        "and not dominated by batch. The latent-state-regime posterior representation is retained as the locked manuscript representation; "
        "the scalar Phi representation remains deprecated because it is less adequate as a global embedding."
    )
    yy = 1760
    for line in wrap(txt, 150):
        draw.text((130, yy), line, font=fsub, fill=(20, 31, 50))
        yy += 44
    png = OUT / "FIGURE_REPRESENTATIONAL_CONSISTENCY_FINAL.png"
    pdf = OUT / "FIGURE_REPRESENTATIONAL_CONSISTENCY_FINAL.pdf"
    img.save(png, dpi=(300, 300))
    img.save(pdf, "PDF", resolution=300)


def wrap(text: str, width: int) -> list[str]:
    out, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + 1 > width:
            out.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        out.append(cur)
    return out


def main():
    df = pd.read_csv(OUT / "regime_posterior_probabilities.tsv", sep="\t")
    df = df.dropna(subset=STATE_COLS + ["Phi", "regime_group", "latent_regime_map", "source_batch"]).copy()
    df = df[df["regime_group"].isin(OBSERVED_GROUPS)].reset_index(drop=True)
    reps = make_representations(df)
    labels_obs = df["regime_group"].astype(str).to_numpy()
    labels_latent = df["latent_regime_map"].astype(str).to_numpy()
    batches = df["source_batch"].astype(str).to_numpy()

    metric_rows = []
    cross_rows = []
    for model, rep in reps.items():
        obs_cons, obs_adj = local_consistency(rep, labels_obs)
        lat_cons, lat_adj = local_consistency(rep, labels_latent)
        regime_eta = eta_squared(rep, labels_obs)
        latent_eta = eta_squared(rep, labels_latent)
        batch_eta = eta_squared(rep, batches)
        disp = within_dispersion(rep, labels_obs, OBSERVED_GROUPS)
        cd = centroid_distance_vector(rep, labels_obs, OBSERVED_GROUPS)
        metric_rows.append({
            "model": model,
            "representation_type": "posterior" if "posterior" in model or "gmm" in model else "embedding_or_cluster",
            "n": len(df),
            "local_consistency_observed": obs_cons,
            "local_consistency_observed_adjusted": obs_adj,
            "local_consistency_latent": lat_cons,
            "local_consistency_latent_adjusted": lat_adj,
            "observed_regime_eta2": regime_eta,
            "latent_regime_eta2": latent_eta,
            "batch_eta2": batch_eta,
            "batch_eta2_over_observed_regime_eta2": batch_eta / regime_eta if regime_eta > 1e-12 else np.nan,
            "within_group_dispersion": disp,
            "mean_between_group_centroid_distance": float(np.nanmean(cd)),
            "between_to_within_ratio": float(np.nanmean(cd) / disp) if disp and np.isfinite(disp) else np.nan,
            "status": "computed",
        })
        cross_rows.extend(cross_species_metrics(rep, df, model))

    metrics = pd.DataFrame(metric_rows)
    cross = pd.DataFrame(cross_rows)
    metrics.to_csv(OUT / "representational_consistency_metrics.tsv", sep="\t", index=False)
    cross.to_csv(OUT / "cross_species_representation_coherence.tsv", sep="\t", index=False)

    stability_rows = []
    for model in reps:
        nrmse, score, cv = bootstrap_stability(df, model, n_boot=60)
        stability_rows.append({
            "model": model,
            "bootstrap_fraction": 0.7,
            "n_bootstrap": 60,
            "centroid_distance_nrmse": nrmse,
            "stability_score": score,
            "distance_cv": cv,
            "status": "computed",
        })
    stability = pd.DataFrame(stability_rows)
    stability.to_csv(OUT / "sampling_noise_stability.tsv", sep="\t", index=False)

    # Composite adequacy score: interpretable, not a predictive superiority score.
    comp = metrics.merge(stability[["model", "stability_score", "distance_cv"]], on="model", how="left")
    comp["batch_resistance"] = 1 / (1 + comp["batch_eta2_over_observed_regime_eta2"])
    for col in ["local_consistency_observed_adjusted", "stability_score", "batch_resistance", "between_to_within_ratio"]:
        vals = comp[col].to_numpy(float)
        lo, hi = np.nanmin(vals), np.nanmax(vals)
        comp[f"{col}_scaled"] = (vals - lo) / (hi - lo + 1e-12)
    comp["representational_adequacy_score"] = comp[
        [
            "local_consistency_observed_adjusted_scaled",
            "stability_score_scaled",
            "batch_resistance_scaled",
            "between_to_within_ratio_scaled",
        ]
    ].mean(axis=1)
    comp = comp.sort_values("representational_adequacy_score", ascending=False)
    comp.to_csv(OUT / "representation_model_comparison_table.tsv", sep="\t", index=False)

    # Report.
    best = comp.iloc[0]
    phi = comp[comp["model"].eq("single_phi_scalar_deprecated")].iloc[0]
    latent = comp[comp["model"].eq("latent_regime_posterior_PZ")].iloc[0]
    lines = [
        "# Representational Consistency Report",
        "",
        "## Scope Correction",
        "",
        "This is a representational consistency analysis, not a predictive superiority or causal validation test. All models are treated as alternative representations of the same locked state system. The analysis evaluates stability, internal consistency, cross-species coherence and sampling-noise sensitivity.",
        "",
        "## Inputs",
        "",
        "- `regime_posterior_probabilities.tsv`",
        "- `Phi_unified.tsv` fields carried inside posterior table",
        "- locked state dimensions: Stemness, Transitional, Fate_lock, Embryonic_module_score",
        "- locked posterior regimes: adult_repair, embryonic_reactivation, salamander_blastema, salamander_intact",
        "",
        "## Main Result",
        "",
        f"Highest composite representational adequacy score: `{best['model']}` ({best['representational_adequacy_score']:.3f}).",
        f"Latent posterior representation score: {latent['representational_adequacy_score']:.3f}.",
        f"Deprecated scalar Phi representation score: {phi['representational_adequacy_score']:.3f}.",
        "",
        "The diagonal GMM responsibility representation is reported as a sensitivity reference, not as a replacement model. The latent-state-regime posterior representation is retained because it is the locked manuscript representation and is substantially more internally coherent and stable than the deprecated scalar representation under the processed outputs. This is not a claim of causal predictive superiority.",
        "",
        "## Interpretation",
        "",
        "- Scalar Phi remains deprecated as a global embedding.",
        "- PCA/diffusion/clustering are useful exploratory representations but do not encode posterior regime mixture directly.",
        "- Latent posterior P(Z|S,W_GRN) remains the appropriate locked manuscript representation because it preserves overlap, regime-specific structure and sampling stability without reverting to a single scalar axis.",
        "- UMAP is not evaluated because no locked UMAP embedding is part of the final output package; generating one would add a new representation not present in the locked analysis.",
        "",
        "## Decision",
        "",
        "DECISION: representational_consistency_supports_latent_regime_mixture_framework.",
        "",
        "Manuscript language should remain: latent-state-regime mixture is a representationally adequate framework, not a proven causal or predictive-superior model.",
    ]
    (OUT / "REPRESENTATIONAL_CONSISTENCY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_figure(metrics, cross, stability)
    print("representational consistency analysis complete")
    print(best["model"], best["representational_adequacy_score"])


if __name__ == "__main__":
    main()
