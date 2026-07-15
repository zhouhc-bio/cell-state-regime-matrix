from __future__ import annotations

import csv
import math
from dataclasses import dataclass
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
REGIME_ORDER = ["adult_repair", "embryonic_reactivation", "salamander_blastema", "salamander_intact"]
OBSERVED_ORDER = [
    "mammalian_inflammatory_repair",
    "salamander_blastema_reactivation",
    "salamander_intact_reference",
]


def softmax(logp: np.ndarray) -> np.ndarray:
    z = logp - np.nanmax(logp, axis=1, keepdims=True)
    e = np.exp(z)
    return e / np.clip(e.sum(axis=1, keepdims=True), 1e-12, None)


def gaussian_prob(train_x, train_y, test_x, classes):
    train_x = np.asarray(train_x, float)
    test_x = np.asarray(test_x, float)
    logp = np.zeros((test_x.shape[0], len(classes)), float)
    for j, c in enumerate(classes):
        x = train_x[train_y == c]
        prior = max(len(x), 1) / max(len(train_x), 1)
        if len(x) == 0:
            logp[:, j] = math.log(1e-12)
            continue
        mu = x.mean(axis=0)
        var = x.var(axis=0) + 1e-4
        ll = -0.5 * (((test_x - mu) ** 2 / var).sum(axis=1) + np.log(2 * np.pi * var).sum())
        logp[:, j] = math.log(prior + 1e-12) + ll
    return softmax(logp)


def pca_fit_transform(train_x, test_x, n_components):
    train_x = np.asarray(train_x, float)
    test_x = np.asarray(test_x, float)
    mu = train_x.mean(axis=0)
    xc = train_x - mu
    _, _, vt = np.linalg.svd(xc, full_matrices=False)
    comp = vt[:n_components].T
    return xc @ comp, (test_x - mu) @ comp


def kmeans_fit(train_x, k, n_iter=80):
    x = np.asarray(train_x, float)
    # deterministic spread: choose quantiles along first PC.
    pc, _ = pca_fit_transform(x, x, 1)
    order = np.argsort(pc[:, 0])
    idx = [order[int((i + 0.5) * len(order) / k)] for i in range(k)]
    centers = x[idx].copy()
    labels = np.zeros(len(x), int)
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


def cluster_probs(train_x, train_y, test_x, classes):
    k = len(classes)
    centers, labels = kmeans_fit(train_x, k)
    comp_to_class = np.zeros((k, len(classes)), float)
    for j in range(k):
        mask = labels == j
        if not mask.any():
            comp_to_class[j] = 1 / len(classes)
        else:
            for ci, c in enumerate(classes):
                comp_to_class[j, ci] = np.mean(train_y[mask] == c)
            comp_to_class[j] = (comp_to_class[j] + 1e-3) / (comp_to_class[j].sum() + 1e-3 * len(classes))
    d = ((np.asarray(test_x)[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    test_clusters = d.argmin(axis=1)
    return comp_to_class[test_clusters]


def gmm_diag_probs(train_x, train_y, test_x, classes, n_iter=80):
    x = np.asarray(train_x, float)
    k = len(classes)
    centers, labels = kmeans_fit(x, k)
    means = centers.copy()
    vars_ = np.vstack([x.var(axis=0) + 1e-3 for _ in range(k)])
    weights = np.ones(k) / k
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
    comp_to_class = np.zeros((k, len(classes)), float)
    resp_train = resp
    for j in range(k):
        for ci, c in enumerate(classes):
            comp_to_class[j, ci] = resp_train[train_y == c, j].sum()
        comp_to_class[j] = (comp_to_class[j] + 1e-3) / (comp_to_class[j].sum() + 1e-3 * len(classes))
    xt = np.asarray(test_x, float)
    log_resp = np.zeros((len(xt), k))
    for j in range(k):
        var = vars_[j]
        ll = -0.5 * (((xt - means[j]) ** 2 / var).sum(axis=1) + np.log(2 * np.pi * var).sum())
        log_resp[:, j] = np.log(weights[j] + 1e-12) + ll
    resp_test = softmax(log_resp)
    return resp_test @ comp_to_class


def diffusion_landmark(train_x, test_x, n_components=3, n_landmarks=512):
    x = np.asarray(train_x, float)
    xt = np.asarray(test_x, float)
    n_landmarks = min(n_landmarks, len(x))
    idx = RNG.choice(len(x), size=n_landmarks, replace=False)
    lm = x[idx]
    # Median distance on landmarks as kernel scale.
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
    keep = slice(1, n_components + 1)
    vals_k = np.clip(vals[keep], 1e-8, None)
    vecs_k = vecs[:, keep]

    def project(y):
        ky = np.exp(-(((np.asarray(y)[:, None, :] - lm[None, :, :]) ** 2).sum(axis=2)) / (sigma2 + 1e-12))
        return ky @ (vecs_k / vals_k)

    return project(x), project(xt)


def stratified_folds(y, k=5):
    y = np.asarray(y)
    folds = [[] for _ in range(k)]
    for c in np.unique(y):
        idx = np.where(y == c)[0]
        RNG.shuffle(idx)
        for i, part in enumerate(np.array_split(idx, k)):
            folds[i].extend(part.tolist())
    return [np.array(sorted(f), int) for f in folds]


def metrics(y_true, probs, classes):
    y_true = np.asarray(y_true)
    probs = np.asarray(probs, float)
    idx = np.array([classes.index(y) for y in y_true])
    p_true = np.clip(probs[np.arange(len(idx)), idx], 1e-12, 1.0)
    ce_loss = -np.log(p_true)
    pred_idx = probs.argmax(axis=1)
    acc = float(np.mean(pred_idx == idx))
    brier = float(np.mean(((np.eye(len(classes))[idx] - probs) ** 2).sum(axis=1)))
    # Macro precision / recall.
    precs, recs = [], []
    for j in range(len(classes)):
        tp = np.sum((pred_idx == j) & (idx == j))
        fp = np.sum((pred_idx == j) & (idx != j))
        fn = np.sum((pred_idx != j) & (idx == j))
        precs.append(tp / max(tp + fp, 1))
        recs.append(tp / max(tp + fn, 1))
    # One-vs-rest macro AUC via ranking.
    aucs = []
    for j in range(len(classes)):
        pos = idx == j
        neg = ~pos
        if pos.sum() == 0 or neg.sum() == 0:
            continue
        scores = probs[:, j]
        order = np.argsort(scores)
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(1, len(scores) + 1)
        auc = (ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * neg.sum())
        aucs.append(float(auc))
    # ECE with confidence bins.
    conf = probs.max(axis=1)
    correct = pred_idx == idx
    ece = 0.0
    for lo, hi in zip(np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:]):
        mask = (conf >= lo) & (conf < hi if hi < 1 else conf <= hi)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return {
        "n": len(idx),
        "cross_entropy": float(np.mean(ce_loss)),
        "mse_probability": brier,
        "accuracy": acc,
        "macro_precision": float(np.mean(precs)),
        "macro_recall": float(np.mean(recs)),
        "macro_auc": float(np.mean(aucs)) if aucs else np.nan,
        "ece_calibration": float(ece),
        "per_sample_loss": ce_loss,
    }


def cv_predict(df, target_col, classes):
    x = df[STATE_COLS].to_numpy(float)
    pz = df[PZ_COLS].to_numpy(float)
    phi = df[["Phi"]].to_numpy(float)
    y = df[target_col].astype(str).to_numpy()
    folds = stratified_folds(y, 5)
    pred_store = {}
    for model in [
        "latent_regime_mixture_PZ",
        "single_phi_scalar",
        "pca_1d",
        "pca_2d",
        "pca_3d",
        "diffusion_map_3d_landmark",
        "gmm_diag",
        "kmeans",
        "null_prior",
        "uniform_null",
        "shuffled_label_null",
    ]:
        pred_store[model] = np.zeros((len(df), len(classes)))
    for fold in folds:
        test = fold
        train = np.setdiff1d(np.arange(len(df)), test)
        ytr = y[train]
        pred_store["latent_regime_mixture_PZ"][test] = gaussian_prob(pz[train], ytr, pz[test], classes)
        pred_store["single_phi_scalar"][test] = gaussian_prob(phi[train], ytr, phi[test], classes)
        for k, name in [(1, "pca_1d"), (2, "pca_2d"), (3, "pca_3d")]:
            tr, te = pca_fit_transform(x[train], x[test], k)
            pred_store[name][test] = gaussian_prob(tr, ytr, te, classes)
        tr, te = diffusion_landmark(x[train], x[test], 3)
        pred_store["diffusion_map_3d_landmark"][test] = gaussian_prob(tr, ytr, te, classes)
        pred_store["kmeans"][test] = cluster_probs(x[train], ytr, x[test], classes)
        pred_store["gmm_diag"][test] = gmm_diag_probs(x[train], ytr, x[test], classes)
        pri = np.array([np.mean(ytr == c) for c in classes])
        pri = (pri + 1e-6) / (pri.sum() + len(classes) * 1e-6)
        pred_store["null_prior"][test] = pri[None, :]
        pred_store["uniform_null"][test] = np.ones((len(test), len(classes))) / len(classes)
        yshuf = ytr.copy()
        RNG.shuffle(yshuf)
        pred_store["shuffled_label_null"][test] = gaussian_prob(pz[train], yshuf, pz[test], classes)
    rows = []
    losses = {}
    for model, pred in pred_store.items():
        m = metrics(y, pred, classes)
        losses[model] = m.pop("per_sample_loss")
        rows.append({"task": target_col, "model": model, "status": "computed", **m})
    rows.append({
        "task": target_col,
        "model": "umap_embedding",
        "status": "not_computable_from_locked_outputs",
        "n": len(df),
        "cross_entropy": np.nan,
        "mse_probability": np.nan,
        "accuracy": np.nan,
        "macro_precision": np.nan,
        "macro_recall": np.nan,
        "macro_auc": np.nan,
        "ece_calibration": np.nan,
    })
    return rows, losses, y


def paired_tests(loss_latent, loss_base, n_boot=2000):
    diff = np.asarray(loss_base) - np.asarray(loss_latent)
    mean = float(diff.mean())
    sd = float(diff.std(ddof=1))
    boot = []
    for _ in range(n_boot):
        idx = RNG.integers(0, len(diff), size=len(diff))
        boot.append(diff[idx].mean())
    boot = np.array(boot)
    ci = np.quantile(boot, [0.025, 0.975])
    p_boot = float(np.mean(boot <= 0))
    # Sign-flip permutation: H0 no paired direction.
    perm = []
    for _ in range(n_boot):
        signs = RNG.choice([-1, 1], size=len(diff))
        perm.append((diff * signs).mean())
    perm = np.array(perm)
    p_perm = float(np.mean(perm >= mean)) if mean >= 0 else float(np.mean(perm <= mean))
    d = float(mean / sd) if sd > 0 else np.nan
    return mean, float(ci[0]), float(ci[1]), p_boot, p_perm, d


def cross_species(df):
    rows = []
    x = df[STATE_COLS].to_numpy(float)
    pz = df[PZ_COLS].to_numpy(float)
    phi = df[["Phi"]].to_numpy(float)
    y = df["latent_regime_map"].astype(str).to_numpy()
    species = df["species_group"].astype(str).to_numpy()
    classes = REGIME_ORDER
    models = ["latent_regime_mixture_PZ", "single_phi_scalar", "pca_3d", "diffusion_map_3d_landmark", "kmeans", "gmm_diag", "null_prior", "uniform_null"]
    for train_species, test_species in [("mammal", "salamander"), ("salamander", "mammal")]:
        train = np.where(species == train_species)[0]
        test = np.where(species == test_species)[0]
        preds = {}
        preds["latent_regime_mixture_PZ"] = pz[test] / np.clip(pz[test].sum(axis=1, keepdims=True), 1e-12, None)
        preds["single_phi_scalar"] = gaussian_prob(phi[train], y[train], phi[test], classes)
        tr, te = pca_fit_transform(x[train], x[test], 3)
        preds["pca_3d"] = gaussian_prob(tr, y[train], te, classes)
        trd, ted = diffusion_landmark(x[train], x[test], 3)
        preds["diffusion_map_3d_landmark"] = gaussian_prob(trd, y[train], ted, classes)
        preds["kmeans"] = cluster_probs(x[train], y[train], x[test], classes)
        preds["gmm_diag"] = gmm_diag_probs(x[train], y[train], x[test], classes)
        pri = np.array([np.mean(y[train] == c) for c in classes])
        pri = (pri + 1e-6) / (pri.sum() + len(classes) * 1e-6)
        preds["null_prior"] = np.repeat(pri[None, :], len(test), axis=0)
        preds["uniform_null"] = np.ones((len(test), len(classes))) / len(classes)
        for model in models:
            m = metrics(y[test], preds[model], classes)
            m.pop("per_sample_loss")
            rows.append({
                "train_species": train_species,
                "test_species": test_species,
                "target": "latent_regime_map_internal_consistency",
                "model": model,
                "status": "computed_internal_target_not_independent_truth",
                **m,
            })
        rows.append({
            "train_species": train_species,
            "test_species": test_species,
            "target": "observed_regime_group",
            "model": "all_supervised_models",
            "status": "not_estimable_label_support_absent_train_species_has_single_observed_group",
            "n": len(test),
            "cross_entropy": np.nan,
            "mse_probability": np.nan,
            "accuracy": np.nan,
            "macro_precision": np.nan,
            "macro_recall": np.nan,
            "macro_auc": np.nan,
            "ece_calibration": np.nan,
        })
    return rows


def perturbation_metrics():
    path = OUT / "DeltaS_predicted_vs_observed.tsv"
    df = pd.read_csv(path, sep="\t")
    axes = ["P", "G", "S", "C"]
    rows = []
    for model, prefix in [("linear_decoder_existing", "linear_predicted_delta"), ("nonlinear_decoder_existing", "nonlinear_predicted_delta")]:
        obs_all, pred_all = [], []
        for a in axes:
            obs_all.append(df[f"observed_delta_{a}"].to_numpy(float))
            pred_all.append(df[f"{prefix}_{a}"].to_numpy(float))
        obs = np.concatenate(obs_all)
        pred = np.concatenate(pred_all)
        sign_acc = float(np.mean(np.sign(obs) == np.sign(pred)))
        rows.append({
            "model": model,
            "status": "computed_existing_deltaS_table",
            "n_axis_observations": len(obs),
            "mse_deltaS": float(np.mean((obs - pred) ** 2)),
            "rmse_deltaS": float(np.sqrt(np.mean((obs - pred) ** 2))),
            "mae_deltaS": float(np.mean(np.abs(obs - pred))),
            "sign_accuracy": sign_acc,
            "cosine_alignment_mean": cosine_by_row(df, prefix),
            "note": "Existing DeltaS table; not a direct latent-state-regime mixture benchmark unless P(Z|S,W_GRN) and U are aligned per perturbation row.",
        })
    obs = np.concatenate([df[f"observed_delta_{a}"].to_numpy(float) for a in axes])
    zero = np.zeros_like(obs)
    rows.append({
        "model": "zero_delta_null",
        "status": "computed_null",
        "n_axis_observations": len(obs),
        "mse_deltaS": float(np.mean((obs - zero) ** 2)),
        "rmse_deltaS": float(np.sqrt(np.mean((obs - zero) ** 2))),
        "mae_deltaS": float(np.mean(np.abs(obs - zero))),
        "sign_accuracy": np.nan,
        "cosine_alignment_mean": np.nan,
        "note": "Zero-effect null baseline.",
    })
    for model in ["latent_regime_mixture_PZ", "single_phi_scalar", "pca_3d", "diffusion_map_3d_landmark", "gmm_diag", "kmeans", "umap_embedding"]:
        rows.append({
            "model": model,
            "status": "not_computable_from_locked_outputs",
            "n_axis_observations": len(obs),
            "mse_deltaS": np.nan,
            "rmse_deltaS": np.nan,
            "mae_deltaS": np.nan,
            "sign_accuracy": np.nan,
            "cosine_alignment_mean": np.nan,
            "note": "Perturbation table lacks per-row S_t, U and P(Z|S,W_GRN) alignment required for fair P(S_t+1|S_t,U) comparison.",
        })
    return rows


def cosine_by_row(df, prefix):
    axes = ["P", "G", "S", "C"]
    vals = []
    for _, r in df.iterrows():
        obs = np.array([r[f"observed_delta_{a}"] for a in axes], float)
        pred = np.array([r[f"{prefix}_{a}"] for a in axes], float)
        denom = np.linalg.norm(obs) * np.linalg.norm(pred)
        if denom > 0:
            vals.append(float(obs.dot(pred) / denom))
    return float(np.mean(vals)) if vals else np.nan


def write_figure(metrics_df, cross_df, perturb_df, sig_df):
    W, H = 3600, 2600
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    bold_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    ftitle = ImageFont.truetype(bold_path, 48)
    fsub = ImageFont.truetype(font_path, 28)
    fsmall = ImageFont.truetype(font_path, 22)
    fbold = ImageFont.truetype(bold_path, 26)
    draw.text((80, 45), "FIGURE_SUPERIORITY_FINAL | predictive benchmark on locked processed outputs", font=ftitle, fill=(20, 31, 50))
    draw.text((80, 105), "Key result: predictive superiority is not fully established because transition/perturbation-aligned P(Z|S,W_GRN) targets are absent.", font=fsub, fill=(150, 40, 35))

    def panel(x, y, w, h, title):
        draw.rounded_rectangle((x, y, x + w, y + h), radius=22, outline=(210, 218, 230), width=3, fill=(248, 250, 253))
        draw.text((x + 25, y + 20), title, font=fbold, fill=(32, 102, 165))
        return x + 25, y + 70, w - 50, h - 95

    def bars(x, y, w, h, labels, values, color=(43, 140, 136), higher_better=True):
        vals = np.array(values, float)
        finite = np.isfinite(vals)
        if not finite.any():
            return
        vmax = vals[finite].max()
        vmin = vals[finite].min()
        rng = max(vmax - min(0, vmin), 1e-9)
        bar_h = min(34, (h - 20) // max(len(labels), 1) - 6)
        for i, (lab, val) in enumerate(zip(labels, vals)):
            yy = y + i * (bar_h + 8)
            draw.text((x, yy), lab[:28], font=fsmall, fill=(20, 31, 50))
            if np.isfinite(val):
                bw = int((val - min(0, vmin)) / rng * (w - 300))
                draw.rectangle((x + 250, yy, x + 250 + bw, yy + bar_h), fill=color)
                draw.text((x + 260 + bw, yy), f"{val:.3f}", font=fsmall, fill=(20, 31, 50))
            else:
                draw.text((x + 250, yy), "NA", font=fsmall, fill=(150, 40, 35))

    # A observed-regime accuracy
    px, py, pw, ph = panel(80, 170, 1080, 620, "A  Observed-regime prediction accuracy")
    obs = metrics_df[metrics_df["task"] == "regime_group"].sort_values("accuracy", ascending=False)
    obs = obs[obs["status"] == "computed"].head(8)
    bars(px, py, pw, ph, obs["model"].tolist(), obs["accuracy"].tolist(), color=(43, 140, 136))

    # B cross species internal
    px, py, pw, ph = panel(1260, 170, 1080, 620, "B  Cross-species internal consistency")
    cs = cross_df[(cross_df["target"] == "latent_regime_map_internal_consistency") & (cross_df["model"].isin(["latent_regime_mixture_PZ", "single_phi_scalar", "pca_3d", "kmeans", "null_prior"]))]
    lab, val = [], []
    for _, r in cs.iterrows():
        lab.append(f"{r['model']} {r['train_species']}→{r['test_species']}")
        val.append(r["accuracy"])
    bars(px, py, pw, ph, lab[:9], val[:9], color=(106, 90, 168))

    # C perturbation
    px, py, pw, ph = panel(2440, 170, 1080, 620, "C  Perturbation ΔS alignment")
    pp = perturb_df[perturb_df["status"].str.contains("computed", na=False)]
    bars(px, py, pw, ph, pp["model"].tolist(), pp["sign_accuracy"].fillna(0).tolist(), color=(184, 121, 26))
    draw.text((px, py + 260), "Direct latent/Phi/PCA perturbation comparison: not computable from locked outputs.", font=fsmall, fill=(150, 40, 35))

    # D residual superiority
    px, py, pw, ph = panel(80, 880, 1660, 720, "D  Paired CE improvement vs Phi")
    row = sig_df[sig_df["baseline_model"] == "single_phi_scalar"].iloc[0]
    draw.text((px, py), f"Mean CE improvement (Phi - latent): {row['mean_ce_improvement_baseline_minus_latent']:.4f}", font=fsub, fill=(20, 31, 50))
    draw.text((px, py + 60), f"95% bootstrap CI: [{row['ci95_low']:.4f}, {row['ci95_high']:.4f}]", font=fsub, fill=(20, 31, 50))
    draw.text((px, py + 120), f"bootstrap p(one-sided): {row['paired_bootstrap_p_one_sided']:.4g}", font=fsub, fill=(20, 31, 50))
    draw.text((px, py + 180), f"Cohen d paired: {row['cohen_d_paired']:.3f}", font=fsub, fill=(20, 31, 50))
    draw.text((px, py + 300), "Interpretation: computed only for observed-regime proxy prediction,\nnot for true P(S_t+1|S_t,U).", font=fsub, fill=(150, 40, 35))

    # E null failure
    px, py, pw, ph = panel(1860, 880, 1660, 720, "E  Null model comparison")
    nulls = metrics_df[(metrics_df["task"] == "regime_group") & (metrics_df["model"].isin(["latent_regime_mixture_PZ", "null_prior", "uniform_null", "shuffled_label_null"]))]
    nulls = nulls.sort_values("cross_entropy")
    bars(px, py, pw, ph, nulls["model"].tolist(), nulls["cross_entropy"].tolist(), color=(190, 58, 52), higher_better=False)
    draw.text((px, py + 300), "Lower cross-entropy is better. Nulls fail, but this does not prove full\ntransition-level superiority.", font=fsub, fill=(20, 31, 50))

    # Decision band.
    draw.rounded_rectangle((80, 1720, 3520, 2440), radius=26, outline=(190, 58, 52), width=4, fill=(251, 234, 234))
    draw.text((130, 1770), "Decision criterion", font=ImageFont.truetype(bold_path, 40), fill=(190, 58, 52))
    decision = (
        "Latent-state-regime mixture improves processed observed-regime prediction over Phi/null baselines, "
        "but predictive superiority over all alternatives is NOT fully established because true transition matrices, "
        "UMAP embeddings, and perturbation-aligned P(Z|S,W_GRN) targets are absent from locked outputs. "
        "Manuscript claim should remain representational/descriptive unless new transition/perturbation validation is computed."
    )
    wrapped = []
    for line in decision.split(". "):
        wrapped.extend([line + "."])
    yy = 1840
    for text in wrapped:
        for seg in textwrap_wrap(text, 128):
            draw.text((130, yy), seg, font=fsub, fill=(20, 31, 50))
            yy += 42
        yy += 10
    png = OUT / "FIGURE_SUPERIORITY_FINAL.png"
    pdf = OUT / "FIGURE_SUPERIORITY_FINAL.pdf"
    img.save(png, dpi=(300, 300))
    img.save(pdf, "PDF", resolution=300)


def textwrap_wrap(s, width):
    words = s.split()
    out, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def main():
    df = pd.read_csv(OUT / "regime_posterior_probabilities.tsv", sep="\t")
    df = df.dropna(subset=STATE_COLS + ["Phi", "regime_group", "latent_regime_map"]).copy()
    # Keep only labels with explicit observed support.
    df = df[df["regime_group"].isin(OBSERVED_ORDER)]

    rows_obs, losses_obs, _ = cv_predict(df, "regime_group", OBSERVED_ORDER)
    rows_latent, losses_latent, _ = cv_predict(df, "latent_regime_map", REGIME_ORDER)
    metrics_df = pd.DataFrame(rows_obs + rows_latent)
    metrics_df.to_csv(OUT / "regime_superiority_metrics.tsv", sep="\t", index=False)

    # Pairwise tests for observed-regime prediction, the least circular computable target.
    sig_rows = []
    lat_loss = losses_obs["latent_regime_mixture_PZ"]
    lat_ce = float(lat_loss.mean())
    for model, loss in losses_obs.items():
        if model == "latent_regime_mixture_PZ":
            continue
        mean, lo, hi, pboot, pperm, d = paired_tests(lat_loss, loss)
        base_ce = float(loss.mean())
        sig_rows.append({
            "task": "observed_regime_group_prediction",
            "proposed_model": "latent_regime_mixture_PZ",
            "baseline_model": model,
            "latent_cross_entropy": lat_ce,
            "baseline_cross_entropy": base_ce,
            "mean_ce_improvement_baseline_minus_latent": mean,
            "relative_ce_improvement_percent": 100 * mean / base_ce if base_ce else np.nan,
            "ci95_low": lo,
            "ci95_high": hi,
            "paired_bootstrap_p_one_sided": pboot,
            "permutation_signflip_p_one_sided": pperm,
            "cohen_d_paired": d,
            "significant_alpha_0_05": bool((lo > 0) and (pboot < 0.05)),
        })
    sig_df = pd.DataFrame(sig_rows)

    cross_df = pd.DataFrame(cross_species(df))
    cross_df.to_csv(OUT / "cross_species_prediction_results.tsv", sep="\t", index=False)

    perturb_df = pd.DataFrame(perturbation_metrics())
    perturb_df.to_csv(OUT / "perturbation_prediction_accuracy.tsv", sep="\t", index=False)

    null_df = metrics_df[metrics_df["model"].str.contains("null", na=False)].copy()
    null_df.to_csv(OUT / "null_model_baseline_results.tsv", sep="\t", index=False)

    # Summary comparison table.
    comp = metrics_df[metrics_df["task"] == "regime_group"].copy()
    comp["primary_metric"] = "cross_entropy"
    comp["lower_is_better"] = True
    comp = comp.sort_values("cross_entropy", na_position="last")
    comp.to_csv(OUT / "model_comparison_table.tsv", sep="\t", index=False)

    sig_df.to_csv(OUT / "model_pairwise_significance.tsv", sep="\t", index=False)

    # Decision.
    computed = sig_df.dropna(subset=["paired_bootstrap_p_one_sided"])
    all_sig = bool((computed["significant_alpha_0_05"].all()) and len(computed) >= 7)
    unavailable = [
        "true P(S_t+1|S_t,U) transition matrices are not present; differential_state_transition_matrix_template.tsv is not_computed",
        "UMAP baseline has no locked embedding and no runnable dependency in the active environment",
        "perturbation rows lack per-row S_t, U and P(Z|S,W_GRN), so direct latent-state-regime ΔS prediction cannot be benchmarked",
    ]
    verdict = "predictive_superiority_not_fully_established_downgrade_to_descriptive_model_only"
    if all_sig and not unavailable:
        verdict = "predictive_superiority_established"

    lines = [
        "# Statistical Significance Report",
        "",
        "## Scope",
        "",
        "This benchmark used only locked processed outputs. No biological data, model structure, figures, or hypotheses were modified.",
        "",
        "## Computable Targets",
        "",
        "- Observed regime-group prediction from state features and posterior representations.",
        "- Internal latent-state-regime-map recovery and cross-species consistency. This target is not independent truth because latent_regime_map is derived from P(Z|S,W_GRN).",
        "- Existing DeltaS prediction table for prior linear/nonlinear decoders and null baseline.",
        "",
        "## Non-computable From Locked Outputs",
        "",
    ]
    lines += [f"- {x}" for x in unavailable]
    lines += [
        "",
        "## Pairwise Superiority Results",
        "",
        sig_df.to_markdown(index=False),
        "",
        "## Decision",
        "",
        f"DECISION: {verdict}",
        "",
        "The latent-state-regime posterior representation is better than the deprecated scalar Phi and null baselines on the computable observed-regime proxy task, but the strict task criterion asks for superiority over all alternatives on P(S_t+1|S_t,U). That cannot be established from the locked outputs because transition-level and perturbation-aligned targets are missing. Therefore the manuscript claim should remain representational/descriptive unless those missing predictive targets are computed in a future analysis.",
    ]
    (OUT / "statistical_significance_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_figure(metrics_df, cross_df, perturb_df, sig_df)
    print("predictive superiority benchmark complete")
    print(verdict)


if __name__ == "__main__":
    main()
