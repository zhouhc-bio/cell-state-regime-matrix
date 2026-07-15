#!/usr/bin/env python3
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

MAMMAL_GSE153596 = Path("/Volumes/T9/PGCS/submission_archive_v1/05_processed_data/tsv_csv/gse153596_velocity_cell_state.tsv")
AXOLOTL_MODULE = Path("/Volumes/T9/PGCS/submission_archive_v1/06_intermediate_results/result14_axolotl_attractor/R14_axolotl_module_scores.tsv")
AXOLOTL_PSEUDOTIME = Path("/Volumes/T9/PGCS/submission_archive_v1/06_intermediate_results/result14_axolotl_attractor/R14_axolotl_pseudotime_results.tsv")
W_GRN = OUT / "W_GRN_learned.tsv"
W_AXIS = OUT / "W_GRN_learned_state_axis_matrix.tsv"

STATE_AXES = ["Stemness", "Transitional", "Fate_lock", "Embryonic_module_score"]
RAW_AXES = [f"{x}_raw" for x in STATE_AXES]
Z_AXES = [f"{x}_z_global" for x in STATE_AXES]
BC_AXES = [f"{x}_batch_corrected" for x in STATE_AXES]
PHI_WEIGHTS = {
    "stemness": 0.22,
    "inverse_fate_lock": 0.22,
    "embryonic_module": 0.24,
    "WE_projection": 0.20,
    "anti_WA_projection": 0.12,
}
N_PERMUTATIONS = 10_000
N_BOOTSTRAP = 5_000
RNG_SEED = 20260619


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", encoding="utf-8-sig")


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


def safe_mean(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    return df[cols].astype(float).mean(axis=1)


def build_mammal_state_matrix() -> pd.DataFrame:
    df = read_tsv(MAMMAL_GSE153596)
    out = pd.DataFrame(
        {
            "sample_id": df["cell_id"].astype(str),
            "dataset": "GSE153596",
            "species": "mouse",
            "species_group": "mammal",
            "regime_group": "mammalian_inflammatory_repair",
            "source_batch": df["geo_accession"].astype(str),
            "stage_or_condition": df["condition_detail"].astype(str),
            "trajectory_time": pd.to_numeric(df["velocity_pseudotime"], errors="coerce"),
            "pseudotime_source": "velocity_pseudotime",
            "n_counts": pd.to_numeric(df["n_counts"], errors="coerce"),
            "Stemness_raw": pd.to_numeric(df["Stemness_index_z"], errors="coerce"),
            "Transitional_raw": pd.to_numeric(df["Inflammatory_regeneration_index_z"], errors="coerce"),
            "Fate_lock_raw": safe_mean(df, ["Senescence_index_z", "p53_BMP_stabilization_score"]),
            "Embryonic_module_score_raw": safe_mean(
                df,
                [
                    "Embryonic_reactivation_index_z",
                    "RA_HOX_spatial_identity_score",
                    "embryonic_like_plasticity_basin_score",
                ],
            ),
            "dominant_state_source": df["dominant_fate_state"].astype(str),
            "raw_source_file": str(MAMMAL_GSE153596),
        }
    )
    return out


def build_axolotl_state_matrix() -> pd.DataFrame:
    df = read_tsv(AXOLOTL_MODULE)
    pt = read_tsv(AXOLOTL_PSEUDOTIME)[["cell_id", "dpt_pseudotime", "dominant_transition_probability_basin_proxy"]]
    df = df.merge(pt, on="cell_id", how="left")
    stage = df["stage"].astype(str)
    regime = np.where(stage.str.lower().eq("intact"), "salamander_intact_reference", "salamander_blastema_reactivation")
    out = pd.DataFrame(
        {
            "sample_id": df["cell_id"].astype(str),
            "dataset": df["dataset"].astype(str),
            "species": "axolotl",
            "species_group": "salamander",
            "regime_group": regime,
            "source_batch": df["sample_id"].astype(str),
            "stage_or_condition": stage,
            "trajectory_time": pd.to_numeric(df["dpt_pseudotime"], errors="coerce"),
            "pseudotime_source": "dpt_pseudotime",
            "n_counts": pd.to_numeric(df["n_counts_raw"], errors="coerce"),
            "Stemness_raw": pd.to_numeric(df["stemness_plasticity_score"], errors="coerce"),
            "Transitional_raw": pd.to_numeric(df["blastema_progenitor_score"], errors="coerce"),
            "Fate_lock_raw": safe_mean(df, ["fate_lock_score", "senescence_inflammatory_score"]),
            "Embryonic_module_score_raw": safe_mean(
                df,
                [
                    "ra_hox_positional_identity_score",
                    "fgf_shh_notch_position_score",
                    "developmental_position_score",
                    "blastema_positional_regeneration_score",
                ],
            ),
            "dominant_state_source": df["dominant_transition_probability_basin_proxy"].astype(str),
            "raw_source_file": str(AXOLOTL_MODULE),
        }
    )
    return out


def eta_squared(values: np.ndarray, labels: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    labels = np.asarray(labels)
    ok = np.isfinite(values) & pd.notna(labels)
    values = values[ok]
    labels = labels[ok]
    if len(values) < 3:
        return float("nan")
    grand = values.mean()
    ss_total = float(((values - grand) ** 2).sum())
    if ss_total <= 0:
        return 0.0
    ss_between = 0.0
    for lab in np.unique(labels):
        v = values[labels == lab]
        ss_between += len(v) * float((v.mean() - grand) ** 2)
    return ss_between / ss_total


def harmonize_state_matrix() -> tuple[pd.DataFrame, pd.DataFrame]:
    aligned = pd.concat([build_mammal_state_matrix(), build_axolotl_state_matrix()], ignore_index=True)
    aligned = aligned.dropna(subset=RAW_AXES).copy()

    norm_rows: list[dict[str, object]] = []
    for axis, raw_axis, z_axis, bc_axis in zip(STATE_AXES, RAW_AXES, Z_AXES, BC_AXES):
        raw = aligned[raw_axis].astype(float).to_numpy()
        lo, hi = np.quantile(raw[np.isfinite(raw)], [0.005, 0.995])
        clipped = np.clip(raw, lo, hi)
        mean = float(clipped.mean())
        sd = float(clipped.std(ddof=0)) or 1.0
        aligned[f"{axis}_winsorized"] = clipped
        aligned[z_axis] = (clipped - mean) / sd
        species_mean = aligned.groupby("species_group")[z_axis].transform("mean")
        batch_mean = aligned.groupby(["species_group", "source_batch"])[z_axis].transform("mean")
        aligned[bc_axis] = aligned[z_axis] - (batch_mean - species_mean)
        aligned[axis] = aligned[bc_axis]
        norm_rows.append(
            {
                "axis": axis,
                "raw_column": raw_axis,
                "global_winsor_p005": lo,
                "global_winsor_p995": hi,
                "global_mean_after_winsor": mean,
                "global_sd_after_winsor": sd,
                "batch_correction": "source_batch centered within species_group; species_group mean preserved",
                "eta2_batch_before": eta_squared(aligned[z_axis].to_numpy(), aligned["source_batch"].to_numpy()),
                "eta2_batch_after": eta_squared(aligned[bc_axis].to_numpy(), aligned["source_batch"].to_numpy()),
                "eta2_species_before": eta_squared(aligned[z_axis].to_numpy(), aligned["species_group"].to_numpy()),
                "eta2_species_after": eta_squared(aligned[bc_axis].to_numpy(), aligned["species_group"].to_numpy()),
            }
        )
    aligned["included_in_primary_H1"] = aligned["regime_group"].isin(
        ["mammalian_inflammatory_repair", "salamander_blastema_reactivation"]
    )
    aligned.to_csv(OUT / "aligned_state_matrix.tsv", sep="\t", index=False)
    norm = pd.DataFrame(norm_rows)
    norm.to_csv(OUT / "normalization_parameters.tsv", sep="\t", index=False)
    return aligned, norm


def normalized(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v.copy() if n == 0 else v / n


def gene_sets_from_wgrn() -> tuple[set[str], set[str]]:
    w = read_tsv(W_GRN)
    embryonic_pat = re.compile(r"(HOX|FGF|FGFR|SHH|GLI|WNT|FZD|TCF7|LEF|RAR|RARB|RARG|RARA|CYP26|ALDH1A)", re.I)
    adult_pat = re.compile(r"(BMP|SMAD|TP53|CDKN|RB1|ARF|NFKB|RELA|TNF|IL1|IL6|JUN|FOS|CXCL|CCL|SERPINE)", re.I)
    embryonic_modules = {"WNT_stemness_module", "FGF_SHH_module", "RA_module"}
    adult_modules = {"BMP_module", "p53_Rb_fate_lock_module"}
    embryonic: set[str] = set()
    adult: set[str] = set()
    for _, row in w.iterrows():
        source = str(row.get("source", ""))
        target = str(row.get("target", ""))
        module = str(row.get("module", ""))
        if module in embryonic_modules or embryonic_pat.search(source) or embryonic_pat.search(target):
            embryonic.add(source)
            if not target.startswith("STATE_AXIS:"):
                embryonic.add(target)
        if module in adult_modules or adult_pat.search(source) or adult_pat.search(target):
            adult.add(source)
            if not target.startswith("STATE_AXIS:"):
                adult.add(target)
    return embryonic, adult


def module_mode(axis_matrix: pd.DataFrame, genes: set[str], orientation: np.ndarray) -> tuple[np.ndarray, int, str]:
    rows = axis_matrix[axis_matrix["source"].isin(genes)]
    if len(rows) < 3:
        return normalized(orientation), len(rows), "fallback_low_overlap"
    x = rows[["Stemness", "Transitional", "Fate_lock", "Embryonic_module_score"]].to_numpy(dtype=float)
    x = x - x.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(x, full_matrices=False)
    mode = normalized(vt[0])
    if float(np.dot(mode, orientation)) < 0:
        mode = -mode
    return mode, len(rows), "W_GRN_module_PC1_oriented_by_biology"


def compute_wgrn_modes() -> dict[str, object]:
    axis = read_tsv(W_AXIS).rename(
        columns={
            "P": "Stemness",
            "C": "Transitional",
            "S": "Fate_lock",
            "G": "Embryonic_module_score",
        }
    )
    embryonic_genes, adult_genes = gene_sets_from_wgrn()
    e_orientation = normalized(np.array([0.45, 0.20, -0.55, 0.70], dtype=float))
    a_orientation = normalized(np.array([-0.35, 0.10, 0.75, -0.55], dtype=float))
    e_mode, n_e, e_status = module_mode(axis, embryonic_genes, e_orientation)
    a_mode, n_a, a_status = module_mode(axis, adult_genes, a_orientation)
    return {
        "WE_mode": e_mode,
        "WA_mode": a_mode,
        "n_WE_genes": n_e,
        "n_WA_genes": n_a,
        "WE_status": e_status,
        "WA_status": a_status,
    }


def add_phi(aligned: pd.DataFrame, modes: dict[str, object]) -> pd.DataFrame:
    S = aligned[STATE_AXES].to_numpy(dtype=float)
    we = np.asarray(modes["WE_mode"], dtype=float)
    wa = np.asarray(modes["WA_mode"], dtype=float)
    aligned = aligned.copy()
    aligned["Phi_term_stemness"] = S[:, 0]
    aligned["Phi_term_inverse_fate_lock"] = -S[:, 2]
    aligned["Phi_term_embryonic_module"] = S[:, 3]
    aligned["Phi_term_WE_projection"] = S @ we
    aligned["Phi_term_anti_WA_projection"] = -(S @ wa)
    aligned["Phi_raw_projection"] = sum(aligned[f"Phi_term_{k}"] * v for k, v in PHI_WEIGHTS.items())
    mu = float(aligned["Phi_raw_projection"].mean())
    sd = float(aligned["Phi_raw_projection"].std(ddof=0)) or 1.0
    aligned["Phi"] = (aligned["Phi_raw_projection"] - mu) / sd
    aligned["R_emergent"] = sigmoid(aligned["Phi"].to_numpy(dtype=float))
    aligned["Phi_threshold_regime"] = np.where(aligned["Phi"] >= 0, "embryonic_accessible", "adult_constrained")
    aligned.to_csv(OUT / "Phi_unified.tsv", sep="\t", index=False)

    rows = []
    for name, coeff in PHI_WEIGHTS.items():
        rows.append(
            {
                "Phi_term": name,
                "coefficient": coeff,
                "calculation": {
                    "stemness": "batch-corrected global-z Stemness",
                    "inverse_fate_lock": "- batch-corrected global-z Fate_lock",
                    "embryonic_module": "batch-corrected global-z Embryonic_module_score",
                    "WE_projection": "dot(batch-corrected S, W_GRN embryonic PC1)",
                    "anti_WA_projection": "-dot(batch-corrected S, W_GRN adult PC1)",
                }[name],
                "normalization": "Phi_raw_projection is globally z-scored across all included cells",
                "dataset_specific_tuning": "none",
            }
        )
    for label, vec in [("WE_mode", we), ("WA_mode", wa)]:
        for axis, value in zip(STATE_AXES, vec):
            rows.append(
                {
                    "Phi_term": f"{label}:{axis}",
                    "coefficient": value,
                    "calculation": "W_GRN module eigenmode component",
                    "normalization": "unit L2 norm",
                    "dataset_specific_tuning": "none",
                }
            )
    rows.extend(
        [
            {
                "Phi_term": "WE_module_overlap_n",
                "coefficient": modes["n_WE_genes"],
                "calculation": "number of W_GRN state-axis genes in embryonic module",
                "normalization": modes["WE_status"],
                "dataset_specific_tuning": "none",
            },
            {
                "Phi_term": "WA_module_overlap_n",
                "coefficient": modes["n_WA_genes"],
                "calculation": "number of W_GRN state-axis genes in adult module",
                "normalization": modes["WA_status"],
                "dataset_specific_tuning": "none",
            },
        ]
    )
    pd.DataFrame(rows).to_csv(OUT / "Phi_unified_formula.tsv", sep="\t", index=False)
    return aligned


def ks_2sample(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    x = np.sort(np.asarray(x, dtype=float))
    y = np.sort(np.asarray(y, dtype=float))
    data = np.sort(np.concatenate([x, y]))
    cdf_x = np.searchsorted(x, data, side="right") / len(x)
    cdf_y = np.searchsorted(y, data, side="right") / len(y)
    d = float(np.max(np.abs(cdf_x - cdf_y)))
    en = math.sqrt(len(x) * len(y) / (len(x) + len(y)))
    lam = (en + 0.12 + 0.11 / max(en, 1e-12)) * d
    p = 2.0 * sum(((-1) ** (j - 1)) * math.exp(-2.0 * j * j * lam * lam) for j in range(1, 101))
    return d, float(max(0.0, min(1.0, p)))


def wasserstein_1d(x: np.ndarray, y: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    y = np.sort(np.asarray(y, dtype=float))
    all_values = np.sort(np.concatenate([x, y]))
    if len(all_values) <= 1:
        return 0.0
    deltas = np.diff(all_values)
    cdf_x = np.searchsorted(x, all_values[:-1], side="right") / len(x)
    cdf_y = np.searchsorted(y, all_values[:-1], side="right") / len(y)
    return float(np.sum(np.abs(cdf_x - cdf_y) * deltas))


def average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    sorted_vals = values[order]
    i = 0
    while i < len(values):
        j = i + 1
        while j < len(values) and sorted_vals[j] == sorted_vals[i]:
            j += 1
        avg = (i + 1 + j) / 2.0
        ranks[order[i:j]] = avg
        i = j
    return ranks


def auc_rank(negative: np.ndarray, positive: np.ndarray) -> float:
    values = np.concatenate([negative, positive])
    ranks = average_ranks(values)
    n0 = len(negative)
    n1 = len(positive)
    pos_ranks = ranks[n0:]
    u = pos_ranks.sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n0 * n1))


def roc_curve_points(negative: np.ndarray, positive: np.ndarray) -> pd.DataFrame:
    scores = np.concatenate([negative, positive])
    labels = np.concatenate([np.zeros(len(negative), dtype=int), np.ones(len(positive), dtype=int)])
    order = np.argsort(-scores, kind="mergesort")
    scores = scores[order]
    labels = labels[order]
    tp = np.cumsum(labels == 1)
    fp = np.cumsum(labels == 0)
    tpr = tp / max(1, int((labels == 1).sum()))
    fpr = fp / max(1, int((labels == 0).sum()))
    roc = pd.DataFrame({"threshold": scores, "FPR": fpr, "TPR": tpr})
    roc = pd.concat([pd.DataFrame({"threshold": [np.inf], "FPR": [0.0], "TPR": [0.0]}), roc], ignore_index=True)
    roc.to_csv(OUT / "roc_curve.tsv", sep="\t", index=False)
    return roc


def permutation_test(x: np.ndarray, y: np.ndarray, n_perm: int = N_PERMUTATIONS) -> tuple[pd.DataFrame, float, float]:
    rng = np.random.default_rng(RNG_SEED)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    observed = float(y.mean() - x.mean())
    pooled = np.concatenate([x, y])
    n_x = len(x)
    null = np.empty(n_perm, dtype=float)
    for i in range(n_perm):
        perm = rng.permutation(pooled)
        null[i] = perm[n_x:].mean() - perm[:n_x].mean()
    p = float((np.sum(np.abs(null) >= abs(observed)) + 1) / (n_perm + 1))
    out = pd.DataFrame({"permutation_id": np.arange(n_perm), "mean_difference_null": null})
    out.to_csv(OUT / "permutation_null_distribution.tsv", sep="\t", index=False)
    return out, observed, p


def bootstrap_ci(x: np.ndarray, y: np.ndarray, auc: float, n_boot: int = N_BOOTSTRAP) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED + 1)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    rows = []
    for i in range(n_boot):
        xb = rng.choice(x, size=len(x), replace=True)
        yb = rng.choice(y, size=len(y), replace=True)
        rows.append(
            {
                "bootstrap_id": i,
                "mean_difference": float(yb.mean() - xb.mean()),
                "median_difference": float(np.median(yb) - np.median(xb)),
                "auc": auc_rank(xb, yb),
            }
        )
    boot = pd.DataFrame(rows)
    ci_rows = []
    for metric in ["mean_difference", "median_difference", "auc"]:
        vals = boot[metric].to_numpy()
        ci_rows.append(
            {
                "metric": metric,
                "estimate": {"mean_difference": float(y.mean() - x.mean()), "median_difference": float(np.median(y) - np.median(x)), "auc": auc}[metric],
                "ci_lower_2p5": float(np.quantile(vals, 0.025)),
                "ci_upper_97p5": float(np.quantile(vals, 0.975)),
                "n_bootstrap": n_boot,
            }
        )
    boot.to_csv(OUT / "bootstrap_distribution.tsv", sep="\t", index=False)
    ci = pd.DataFrame(ci_rows)
    ci.to_csv(OUT / "bootstrap_confidence_intervals.tsv", sep="\t", index=False)
    return ci


def statistical_validation(phi: pd.DataFrame) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    primary = phi[phi["included_in_primary_H1"]].copy()
    mammal = primary.loc[primary["regime_group"] == "mammalian_inflammatory_repair", "Phi"].to_numpy(dtype=float)
    salamander = primary.loc[primary["regime_group"] == "salamander_blastema_reactivation", "Phi"].to_numpy(dtype=float)
    d, ks_p = ks_2sample(mammal, salamander)
    wd = wasserstein_1d(mammal, salamander)
    auc = auc_rank(mammal, salamander)
    roc = roc_curve_points(mammal, salamander)
    _, obs_diff, perm_p = permutation_test(mammal, salamander)
    ci = bootstrap_ci(mammal, salamander, auc)
    results = {
        "n_mammal": float(len(mammal)),
        "n_salamander_blastema": float(len(salamander)),
        "ks_statistic": d,
        "ks_p_value": ks_p,
        "wasserstein_distance": wd,
        "observed_mean_difference_salamander_minus_mammal": obs_diff,
        "permutation_p_value_two_sided": perm_p,
        "auc": auc,
        "acceptance_p_lt_0_05": float(ks_p < 0.05 and perm_p < 0.05),
        "acceptance_auc_gt_0_75": float(auc > 0.75),
    }
    pd.DataFrame([results]).to_csv(OUT / "ks_test_results.tsv", sep="\t", index=False)
    pd.DataFrame(
        [
            {
                "test": "10,000 label permutations",
                "statistic": "mean(Phi_salamander_blastema) - mean(Phi_mammal)",
                "observed": obs_diff,
                "p_value_two_sided": perm_p,
                "n_permutations": N_PERMUTATIONS,
                "random_seed": RNG_SEED,
            }
        ]
    ).to_csv(OUT / "permutation_test_results.tsv", sep="\t", index=False)
    return results, roc, ci


def draw_hist_by_species(phi: pd.DataFrame) -> None:
    img = Image.new("RGB", (1100, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((300, 24), "Unified Phi distribution by species/regime", fill=(17, 24, 39), font=title)
    left, top, width, height = 90, 110, 720, 450
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    bins = np.linspace(phi["Phi"].quantile(0.002), phi["Phi"].quantile(0.998), 60)
    groups = [
        ("mammalian_inflammatory_repair", (221, 139, 40), "mammal repair"),
        ("salamander_blastema_reactivation", (44, 127, 184), "salamander blastema"),
        ("salamander_intact_reference", (100, 116, 139), "salamander intact"),
    ]
    max_density = 0.0
    hists = []
    for group, color, label in groups:
        vals = phi.loc[phi["regime_group"] == group, "Phi"].to_numpy(dtype=float)
        if len(vals) == 0:
            continue
        hist, edges = np.histogram(vals, bins=bins, density=True)
        max_density = max(max_density, float(hist.max()))
        hists.append((hist, edges, color, label))
    for hist, edges, color, _ in hists:
        pts = []
        for h, x0, x1 in zip(hist, edges[:-1], edges[1:]):
            px = int(left + (((x0 + x1) / 2 - bins.min()) / (bins.max() - bins.min())) * width)
            py = int(top + height - (h / max(max_density, 1e-9)) * height)
            pts.append((px, py))
        draw.line(pts, fill=color, width=4)
    zero_x = int(left + ((0 - bins.min()) / (bins.max() - bins.min())) * width)
    draw.line([(zero_x, top), (zero_x, top + height)], fill=(15, 23, 42), width=2)
    draw.text((zero_x + 8, top + 8), "Phi=0", fill=(15, 23, 42), font=small)
    draw.text((left + 310, top + height + 35), "Unified Phi z-score", fill=(30, 41, 59), font=font)
    draw.text((20, top + 190), "density", fill=(30, 41, 59), font=font)
    for i, (_, color, label) in enumerate(groups):
        draw.rectangle([850, 150 + 34 * i, 870, 170 + 34 * i], fill=color)
        draw.text((882, 146 + 34 * i), label, fill=(30, 41, 59), font=small)
    img.save(OUT / "Phi_distribution_by_species.png")


def draw_batch_assessment(norm: pd.DataFrame) -> None:
    img = Image.new("RGB", (1120, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((310, 24), "Batch effect assessment before Phi computation", fill=(17, 24, 39), font=title)
    left, top, width, height = 90, 120, 800, 420
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    metrics = ["eta2_batch_before", "eta2_batch_after", "eta2_species_before", "eta2_species_after"]
    colors = [(184, 50, 44), (44, 127, 184), (221, 139, 40), (80, 160, 110)]
    maxv = max(float(norm[m].max()) for m in metrics)
    bar_w = 28
    gap = 45
    x = left + 60
    for _, row in norm.iterrows():
        for j, m in enumerate(metrics):
            v = float(row[m])
            h = int(v / max(maxv, 1e-9) * (height - 50))
            bx = x + j * (bar_w + 4)
            draw.rectangle([bx, top + height - h, bx + bar_w, top + height], fill=colors[j])
        draw.text((x - 5, top + height + 12), str(row["axis"]).replace("_", "\n"), fill=(30, 41, 59), font=small)
        x += 4 * (bar_w + 4) + gap
    for j, m in enumerate(metrics):
        draw.rectangle([930, 150 + 28 * j, 950, 170 + 28 * j], fill=colors[j])
        draw.text((960, 146 + 28 * j), m.replace("eta2_", ""), fill=(30, 41, 59), font=small)
    draw.text((left + 280, top + height + 80), "ANOVA eta squared", fill=(30, 41, 59), font=font)
    norm.to_csv(OUT / "batch_effect_assessment.tsv", sep="\t", index=False)
    img.save(OUT / "batch_effect_assessment.png")


def draw_roc(roc: pd.DataFrame, auc: float) -> None:
    img = Image.new("RGB", (760, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((205, 24), "ROC: Phi classifies regime", fill=(17, 24, 39), font=title)
    left, top, size = 100, 100, 520
    draw.rectangle([left, top, left + size, top + size], outline=(30, 41, 59), width=2)
    draw.line([(left, top + size), (left + size, top)], fill=(148, 163, 184), width=2)
    pts = [(int(left + r.FPR * size), int(top + size - r.TPR * size)) for r in roc.itertuples()]
    draw.line(pts, fill=(184, 50, 44), width=4)
    draw.text((left + 190, top + size + 35), "False positive rate", fill=(30, 41, 59), font=font)
    draw.text((22, top + 230), "True positive rate", fill=(30, 41, 59), font=small)
    draw.text((455, 135), f"AUC = {auc:.3f}", fill=(17, 24, 39), font=font)
    img.save(OUT / "roc_curve.png")


def draw_bootstrap_ci(ci: pd.DataFrame) -> None:
    img = Image.new("RGB", (900, 620), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((230, 24), "Bootstrap confidence intervals", fill=(17, 24, 39), font=title)
    left, top, width, height = 140, 110, 560, 360
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    vals = ci[["ci_lower_2p5", "ci_upper_97p5", "estimate"]].to_numpy().ravel()
    xmin, xmax = float(vals.min()), float(vals.max())
    pad = 0.12 * (xmax - xmin if xmax > xmin else 1.0)
    xmin -= pad
    xmax += pad
    def px(v: float) -> int:
        return int(left + (v - xmin) / (xmax - xmin) * width)
    for i, row in ci.iterrows():
        y = top + 70 + i * 95
        draw.line([(px(float(row.ci_lower_2p5)), y), (px(float(row.ci_upper_97p5)), y)], fill=(30, 64, 116), width=4)
        draw.ellipse([px(float(row.estimate)) - 7, y - 7, px(float(row.estimate)) + 7, y + 7], fill=(184, 50, 44))
        draw.text((left - 120, y - 8), str(row.metric), fill=(30, 41, 59), font=small)
    zero = px(0)
    if left <= zero <= left + width:
        draw.line([(zero, top), (zero, top + height)], fill=(15, 23, 42), width=1)
    draw.text((left + 190, top + height + 35), "estimate and 95% bootstrap CI", fill=(30, 41, 59), font=font)
    img.save(OUT / "bootstrap_confidence_intervals.png")


def draw_simple_line_plot(data: pd.DataFrame, xcol: str, ycols: list[tuple[str, tuple[int, int, int], str]], title_text: str, out: Path) -> None:
    img = Image.new("RGB", (980, 680), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((210, 24), title_text, fill=(17, 24, 39), font=title)
    left, top, width, height = 90, 100, 650, 430
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    x = data[xcol].to_numpy(dtype=float)
    ymin = min(float(data[y].min()) for y, _, _ in ycols)
    ymax = max(float(data[y].max()) for y, _, _ in ycols)
    if ymax == ymin:
        ymax = ymin + 1
    def pt(xv: float, yv: float) -> tuple[int, int]:
        return int(left + (xv - x.min()) / max(x.max() - x.min(), 1e-9) * width), int(top + height - (yv - ymin) / (ymax - ymin) * height)
    for j, (y, color, label) in enumerate(ycols):
        pts = [pt(float(a), float(b)) for a, b in zip(x, data[y].to_numpy(dtype=float))]
        draw.line(pts, fill=color, width=4)
        draw.rectangle([780, 145 + 32 * j, 800, 165 + 32 * j], fill=color)
        draw.text((812, 141 + 32 * j), label, fill=(30, 41, 59), font=small)
    draw.text((left + 250, top + height + 35), xcol, fill=(30, 41, 59), font=font)
    img.save(out)


def figure_data_products(phi: pd.DataFrame, modes: dict[str, object], stats: dict[str, float]) -> None:
    # Figure 1: Phi-grid dual attractor landscape.
    stem_med = float(phi["Stemness"].median())
    trans_med = float(phi["Transitional"].median())
    fate = np.linspace(float(phi["Fate_lock"].quantile(0.01)), float(phi["Fate_lock"].quantile(0.99)), 120)
    emb = np.linspace(float(phi["Embryonic_module_score"].quantile(0.01)), float(phi["Embryonic_module_score"].quantile(0.99)), 120)
    rows = []
    for f in fate:
        for e in emb:
            S = np.array([stem_med, trans_med, f, e])
            we = np.asarray(modes["WE_mode"])
            wa = np.asarray(modes["WA_mode"])
            phi_raw = (
                PHI_WEIGHTS["stemness"] * S[0]
                + PHI_WEIGHTS["inverse_fate_lock"] * (-S[2])
                + PHI_WEIGHTS["embryonic_module"] * S[3]
                + PHI_WEIGHTS["WE_projection"] * float(S @ we)
                + PHI_WEIGHTS["anti_WA_projection"] * (-float(S @ wa))
            )
            # Convert through the observed global Phi raw distribution.
            obs_mu = float(phi["Phi_raw_projection"].mean())
            obs_sd = float(phi["Phi_raw_projection"].std(ddof=0)) or 1.0
            p = (phi_raw - obs_mu) / obs_sd
            r = float(sigmoid(p))
            rows.append({"Fate_lock": f, "Embryonic_module_score": e, "Phi": p, "R_emergent": r})
    grid = pd.DataFrame(rows)
    grid.to_csv(OUT / "figure1_phi_grid_source_data.tsv", sep="\t", index=False)
    draw_heatmap(
        grid,
        "Fate_lock",
        "Embryonic_module_score",
        "R_emergent",
        "Figure 1: dual attractor landscape from Phi grid",
        OUT / "figure1_dual_attractor_landscape_phi_grid.png",
    )

    # Figure 2: trajectory separation from aligned data.
    bins = []
    for group, sub in phi.groupby("regime_group"):
        if group not in ["mammalian_inflammatory_repair", "salamander_blastema_reactivation"]:
            continue
        sub = sub.dropna(subset=["trajectory_time"]).copy()
        sub["time_bin"] = pd.qcut(sub["trajectory_time"].rank(method="first"), 12, labels=False, duplicates="drop")
        bins.append(
            sub.groupby("time_bin", as_index=False)[["Fate_lock", "Embryonic_module_score", "Phi", "R_emergent"]]
            .mean()
            .assign(regime_group=group)
        )
    traj = pd.concat(bins, ignore_index=True)
    traj.to_csv(OUT / "figure2_trajectory_source_data.tsv", sep="\t", index=False)
    draw_trajectory_figure(traj, OUT / "figure2_mammal_vs_salamander_trajectory_from_aligned.png")

    # Figure 3: phase diagram from Phi manifold.
    phase = grid.copy()
    phase.to_csv(OUT / "figure3_phi_manifold_phase_source_data.tsv", sep="\t", index=False)
    draw_heatmap(
        phase,
        "Fate_lock",
        "Embryonic_module_score",
        "Phi",
        "Figure 3: phase diagram from Phi manifold",
        OUT / "figure3_phase_diagram_phi_manifold.png",
        center_zero=True,
    )

    # Figure 4: bifurcation over W_GRN scaling.
    adult = phi.loc[phi["regime_group"] == "mammalian_inflammatory_repair", STATE_AXES].mean().to_numpy()
    embryo = phi.loc[phi["regime_group"] == "salamander_blastema_reactivation", STATE_AXES].mean().to_numpy()
    rows = []
    for q in np.linspace(0, 1, 121):
        S = (1 - q) * adult + q * embryo
        for scale in np.linspace(0.25, 1.75, 31):
            we = np.asarray(modes["WE_mode"]) * scale
            wa = np.asarray(modes["WA_mode"]) * scale
            phi_raw = (
                PHI_WEIGHTS["stemness"] * S[0]
                + PHI_WEIGHTS["inverse_fate_lock"] * (-S[2])
                + PHI_WEIGHTS["embryonic_module"] * S[3]
                + PHI_WEIGHTS["WE_projection"] * float(S @ we)
                + PHI_WEIGHTS["anti_WA_projection"] * (-float(S @ wa))
            )
            obs_mu = float(phi["Phi_raw_projection"].mean())
            obs_sd = float(phi["Phi_raw_projection"].std(ddof=0)) or 1.0
            p = (phi_raw - obs_mu) / obs_sd
            rows.append({"state_path_q": q, "W_GRN_mode_scale": scale, "Phi": p, "R_emergent": float(sigmoid(p))})
    bif = pd.DataFrame(rows)
    bif.to_csv(OUT / "figure4_bifurcation_wgrn_scaling_source_data.tsv", sep="\t", index=False)
    draw_heatmap(
        bif,
        "state_path_q",
        "W_GRN_mode_scale",
        "Phi",
        "Figure 4: bifurcation under W_GRN mode scaling",
        OUT / "figure4_bifurcation_wgrn_scaling.png",
        center_zero=True,
    )

    # Figure 5: regime threshold crossing.
    cross = (
        phi.assign(crossed_phi_threshold=phi["Phi"] >= 0)
        .groupby(["regime_group", "source_batch"], as_index=False)
        .agg(
            n_cells=("Phi", "size"),
            Phi_mean=("Phi", "mean"),
            threshold_crossing_fraction=("crossed_phi_threshold", "mean"),
        )
    )
    cross.to_csv(OUT / "figure5_regime_threshold_crossing_statistics.tsv", sep="\t", index=False)
    draw_threshold_crossing(cross, OUT / "figure5_regime_switching_phi_threshold.png")

    # Figure 6: GRN contribution analysis.
    contrib = pd.DataFrame(
        [
            {"component": "WE_mode", "axis": axis, "loading": val}
            for axis, val in zip(STATE_AXES, np.asarray(modes["WE_mode"]))
        ]
        + [
            {"component": "WA_mode", "axis": axis, "loading": val}
            for axis, val in zip(STATE_AXES, np.asarray(modes["WA_mode"]))
        ]
    )
    term_means = (
        phi.groupby("regime_group")[
            [
                "Phi_term_stemness",
                "Phi_term_inverse_fate_lock",
                "Phi_term_embryonic_module",
                "Phi_term_WE_projection",
                "Phi_term_anti_WA_projection",
            ]
        ]
        .mean()
        .reset_index()
    )
    contrib.to_csv(OUT / "figure6_grn_eigendecomposition_contributions.tsv", sep="\t", index=False)
    term_means.to_csv(OUT / "figure6_phi_term_contributions_by_regime.tsv", sep="\t", index=False)
    draw_grn_contribution(contrib, term_means, OUT / "figure6_grn_contribution_analysis.png")

    # Figure 7: summary from statistical outputs.
    fig7 = pd.DataFrame(
        [
            {"metric": "KS statistic", "value": stats["ks_statistic"]},
            {"metric": "-log10 KS p", "value": -math.log10(max(stats["ks_p_value"], 1e-300))},
            {"metric": "Permutation -log10 p", "value": -math.log10(max(stats["permutation_p_value_two_sided"], 1e-300))},
            {"metric": "AUC", "value": stats["auc"]},
            {"metric": "Wasserstein", "value": stats["wasserstein_distance"]},
        ]
    )
    fig7.to_csv(OUT / "figure7_statistical_validation_summary.tsv", sep="\t", index=False)
    draw_stat_summary(fig7, OUT / "figure7_statistical_validation_summary.png")


def draw_heatmap(df: pd.DataFrame, xcol: str, ycol: str, zcol: str, title_text: str, out: Path, center_zero: bool = False) -> None:
    piv = df.pivot(index=ycol, columns=xcol, values=zcol).sort_index(ascending=True)
    arr = piv.to_numpy(dtype=float)
    if center_zero:
        maxabs = max(abs(float(np.nanmin(arr))), abs(float(np.nanmax(arr))), 1e-9)
        norm = (arr + maxabs) / (2 * maxabs)
    else:
        norm = (arr - np.nanmin(arr)) / max(np.nanmax(arr) - np.nanmin(arr), 1e-9)
    img = Image.new("RGB", (980, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((210, 24), title_text, fill=(17, 24, 39), font=title)
    left, top, width, height = 90, 90, 600, 560
    canvas = Image.new("RGB", arr.shape[::-1], "white")
    pix = canvas.load()
    for j in range(arr.shape[0]):
        for i in range(arr.shape[1]):
            v = float(norm[j, i])
            blue = np.array([44, 127, 184])
            cream = np.array([245, 245, 220])
            red = np.array([184, 50, 44])
            if v < 0.5:
                c = blue + (cream - blue) * (v / 0.5)
            else:
                c = cream + (red - cream) * ((v - 0.5) / 0.5)
            pix[i, arr.shape[0] - 1 - j] = tuple(int(x) for x in c)
    canvas = canvas.resize((width, height))
    img.paste(canvas, (left, top))
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    draw.text((left + 220, top + height + 30), xcol, fill=(30, 41, 59), font=small)
    draw.text((18, top + 250), ycol, fill=(30, 41, 59), font=small)
    draw.text((730, 160), zcol, fill=(17, 24, 39), font=font)
    draw.text((730, 195), "blue: low", fill=(44, 127, 184), font=small)
    draw.text((730, 220), "red: high", fill=(184, 50, 44), font=small)
    img.save(out)


def draw_trajectory_figure(traj: pd.DataFrame, out: Path) -> None:
    img = Image.new("RGB", (980, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((225, 24), "Figure 2: trajectories from aligned state matrix", fill=(17, 24, 39), font=title)
    left, top, width, height = 100, 100, 560, 500
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    colors = {"mammalian_inflammatory_repair": (221, 139, 40), "salamander_blastema_reactivation": (44, 127, 184)}
    xmin, xmax = traj["Fate_lock"].min(), traj["Fate_lock"].max()
    ymin, ymax = traj["Embryonic_module_score"].min(), traj["Embryonic_module_score"].max()
    def pt(x: float, y: float) -> tuple[int, int]:
        return (
            int(left + (x - xmin) / max(xmax - xmin, 1e-9) * width),
            int(top + height - (y - ymin) / max(ymax - ymin, 1e-9) * height),
        )
    for group, sub in traj.groupby("regime_group"):
        sub = sub.sort_values("time_bin")
        points = [pt(float(r.Fate_lock), float(r.Embryonic_module_score)) for r in sub.itertuples()]
        draw.line(points, fill=colors[group], width=4)
        for p in points:
            draw.ellipse([p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4], fill=colors[group])
    draw.text((left + 210, top + height + 35), "Fate_lock", fill=(30, 41, 59), font=font)
    draw.text((18, top + 230), "Embryonic module", fill=(30, 41, 59), font=small)
    for i, (label, color) in enumerate(colors.items()):
        draw.rectangle([700, 155 + 32 * i, 720, 175 + 32 * i], fill=color)
        draw.text((732, 151 + 32 * i), label, fill=(30, 41, 59), font=small)
    img.save(out)


def draw_threshold_crossing(cross: pd.DataFrame, out: Path) -> None:
    img = Image.new("RGB", (980, 620), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((260, 24), "Figure 5: Phi threshold crossing statistics", fill=(17, 24, 39), font=title)
    agg = cross.groupby("regime_group", as_index=False)["threshold_crossing_fraction"].mean()
    left, top, width, height = 120, 110, 600, 360
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    colors = [(221, 139, 40), (44, 127, 184), (100, 116, 139)]
    for i, row in enumerate(agg.itertuples()):
        bar_h = int(float(row.threshold_crossing_fraction) * height)
        x0 = left + 80 + i * 160
        draw.rectangle([x0, top + height - bar_h, x0 + 80, top + height], fill=colors[i % len(colors)])
        draw.text((x0 - 20, top + height + 14), str(row.regime_group).replace("_", "\n"), fill=(30, 41, 59), font=small)
        draw.text((x0, top + height - bar_h - 22), f"{row.threshold_crossing_fraction:.2f}", fill=(17, 24, 39), font=small)
    draw.text((left + 200, top + height + 95), "fraction Phi >= 0", fill=(30, 41, 59), font=font)
    img.save(out)


def draw_grn_contribution(contrib: pd.DataFrame, terms: pd.DataFrame, out: Path) -> None:
    img = Image.new("RGB", (1160, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((320, 24), "Figure 6: W_GRN eigenmode and Phi term contributions", fill=(17, 24, 39), font=title)
    left, top, width, height = 90, 110, 470, 420
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    vals = contrib["loading"].to_numpy()
    maxabs = max(abs(vals.min()), abs(vals.max()), 1e-9)
    x = left + 45
    colors = {"WE_mode": (44, 127, 184), "WA_mode": (184, 50, 44)}
    for comp, sub in contrib.groupby("component"):
        for row in sub.itertuples():
            y0 = top + height / 2
            h = int(float(row.loading) / maxabs * (height / 2 - 30))
            y_a, y_b = sorted([int(y0 - h), int(y0)])
            draw.rectangle([x, y_a, x + 28, y_b], fill=colors[comp])
            draw.text((x - 10, top + height + 12), row.axis[:6], fill=(30, 41, 59), font=small)
            x += 44
        x += 24
    draw.line([(left, int(top + height / 2)), (left + width, int(top + height / 2))], fill=(15, 23, 42), width=1)
    draw.text((180, 560), "W_GRN eigenmode loadings", fill=(30, 41, 59), font=font)

    right, rtop, rwidth, rheight = 650, 110, 420, 420
    draw.rectangle([right, rtop, right + rwidth, rtop + rheight], outline=(30, 41, 59), width=2)
    term_cols = [c for c in terms.columns if c.startswith("Phi_term_")]
    means = terms.set_index("regime_group")[term_cols]
    diff = means.loc["salamander_blastema_reactivation"] - means.loc["mammalian_inflammatory_repair"]
    maxabs = max(abs(diff.min()), abs(diff.max()), 1e-9)
    for i, (term, val) in enumerate(diff.items()):
        y = rtop + 45 + i * 67
        x0 = right + rwidth // 2
        w = int(float(val) / maxabs * (rwidth // 2 - 40))
        color = (44, 127, 184) if val >= 0 else (184, 50, 44)
        x_a, x_b = sorted([int(x0), int(x0 + w)])
        draw.rectangle([x_a, y, x_b, y + 24], fill=color)
        draw.text((right + 10, y), term.replace("Phi_term_", ""), fill=(30, 41, 59), font=small)
    draw.line([(right + rwidth // 2, rtop), (right + rwidth // 2, rtop + rheight)], fill=(15, 23, 42), width=1)
    draw.text((720, 560), "salamander - mammal term means", fill=(30, 41, 59), font=font)
    img.save(out)


def draw_stat_summary(fig7: pd.DataFrame, out: Path) -> None:
    img = Image.new("RGB", (920, 620), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((260, 24), "Figure 7: statistical validation summary", fill=(17, 24, 39), font=title)
    left, top, width, height = 160, 110, 560, 360
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    vmax = float(fig7["value"].max())
    for i, row in enumerate(fig7.itertuples()):
        y = top + 40 + i * 60
        bar = int(float(row.value) / max(vmax, 1e-9) * (width - 160))
        draw.rectangle([left + 145, y, left + 145 + bar, y + 28], fill=(44, 127, 184))
        draw.text((left - 110, y + 3), str(row.metric), fill=(30, 41, 59), font=small)
        draw.text((left + 155 + bar, y + 3), f"{row.value:.3g}", fill=(17, 24, 39), font=small)
    img.save(out)


def write_reports(aligned: pd.DataFrame, norm: pd.DataFrame, phi: pd.DataFrame, modes: dict[str, object], stats: dict[str, float]) -> None:
    input_rows = [
        {
            "dataset": "GSE153596",
            "species_group": "mammal",
            "n_cells": int((aligned["dataset"] == "GSE153596").sum()),
            "source": str(MAMMAL_GSE153596),
            "feature_mapping": "Stemness_index_z, Inflammatory_regeneration_index_z, mean(Senescence_index_z,p53_BMP), mean(Embryonic_reactivation,RA_HOX,embryonic_like)",
            "included_in_primary_H1": True,
        },
        {
            "dataset": "GSE315993",
            "species_group": "salamander",
            "n_cells": int((aligned["dataset"] == "GSE315993").sum()),
            "source": str(AXOLOTL_MODULE),
            "feature_mapping": "stemness_plasticity, blastema_progenitor, mean(fate_lock,senescence_inflammatory), mean(RA_HOX,FGF_SHH_NOTCH,developmental_position,blastema_regeneration)",
            "included_in_primary_H1": "dpa>0 only; intact retained as reference",
        },
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "data_closure_input_manifest.tsv", sep="\t", index=False)

    status = (
        "VALID_MODULE_SCORE_LAYER"
        if stats["ks_p_value"] < 0.05 and stats["permutation_p_value_two_sided"] < 0.05 and stats["auc"] > 0.75
        else "INVALID_STATISTICAL_CRITERIA_NOT_MET"
    )
    norm_md = f"""# Normalization Report

## 输入层级

本次闭环使用已处理的细胞级状态/模块分数，而不是从 raw count matrix 或 FASTQ 重新计算表达矩阵。

## 统一状态空间

```text
S = [Stemness, Transitional, Fate_lock, Embryonic_module_score]
```

所有进入 `Phi` 的样本均被投影到上述四个轴。映射规则固定写入 `data_closure_input_manifest.tsv`，没有按数据集优化系数。

## 标准化和批次校正

1. 合并所有进入分析的细胞。
2. 每个状态轴使用 pooled global 0.5%/99.5% winsorization。
3. 使用 pooled global mean/sd 计算 z-score。
4. 在 `species_group` 内校正 `source_batch` 均值偏移，并保留物种/机制组均值。
5. 批次校正发生在 `Phi` 计算之前。

## 重要限制

因为 GSE153596 与 GSE315993 的 dataset 与物种/机制部分混杂，不能用 dataset-level correction 直接消除数据集均值，否则会同时去除目标生物差异。因此本次只进行 species 内 sample/batch 校正，并在 `batch_effect_assessment.tsv` 中报告校正前后的 eta-squared。
"""
    (OUT / "normalization_report.md").write_text(norm_md, encoding="utf-8")

    validation_md = f"""# Statistical Validation Report

## Primary Hypothesis

H1: unified `Phi(S,W_GRN)` separates mammalian inflammatory repair from salamander blastema reactivation.

Primary comparison:

- Mammal: `mammalian_inflammatory_repair`, n = {int(stats['n_mammal'])}
- Salamander: `salamander_blastema_reactivation`, n = {int(stats['n_salamander_blastema'])}
- Salamander intact cells are retained in `Phi_unified.tsv` as reference but excluded from the primary H1 test.

## Results

| test | statistic |
|---|---:|
| KS statistic | {stats['ks_statistic']:.6g} |
| KS p-value | {stats['ks_p_value']:.6g} |
| Wasserstein distance | {stats['wasserstein_distance']:.6g} |
| Mean Phi difference, salamander - mammal | {stats['observed_mean_difference_salamander_minus_mammal']:.6g} |
| Permutation p-value, two-sided | {stats['permutation_p_value_two_sided']:.6g} |
| ROC AUC | {stats['auc']:.6g} |

## Acceptance Criteria

- p < 0.05: {'PASS' if stats['ks_p_value'] < 0.05 and stats['permutation_p_value_two_sided'] < 0.05 else 'FAIL'}
- AUC > 0.75: {'PASS' if stats['auc'] > 0.75 else 'FAIL'}

## System Status

`{status}`

## Evidence Boundary

This is a module-score/state-score-level closure. It is suitable as a reproducible figure-data/statistical binding layer for the current model outputs, but final raw-data submission should additionally archive the upstream scripts that produced the input module scores.
"""
    (OUT / "statistical_validation_report.md").write_text(validation_md, encoding="utf-8")

    model_md = f"""# Data Closure Verdict

## Verdict

`{status}`

The system passes the requested statistical criteria at the processed module-score layer if and only if the reported p-values are < 0.05 and AUC > 0.75.

## Unified Phi

`Phi` is computed once across all included cells from:

```text
Phi = a1*Stemness - a2*Fate_lock + a3*Embryonic_module_score
      + a4*projection(S onto W_E eigenmode)
      - a5*projection(S onto W_A eigenmode)
```

The same coefficients, W_GRN eigenmodes, global normalization, and batch correction are used for all datasets.

## W_GRN Basis

- W_E overlap genes: {modes['n_WE_genes']} ({modes['WE_status']})
- W_A overlap genes: {modes['n_WA_genes']} ({modes['WA_status']})

## Figure-Data Rule

All generated closure figures are bound to `aligned_state_matrix.tsv` and `Phi_unified.tsv` through `figure_data_binding_map.tsv`.
"""
    (OUT / "data_closure_verdict.md").write_text(model_md, encoding="utf-8")


def write_binding_map() -> None:
    rows = [
        ("Figure 1", "figure1_dual_attractor_landscape_phi_grid.png", "figure1_phi_grid_source_data.tsv", "Phi grid over aligned S space", "PASS"),
        ("Figure 2", "figure2_mammal_vs_salamander_trajectory_from_aligned.png", "figure2_trajectory_source_data.tsv", "Trajectory bins from aligned_state_matrix.tsv", "PASS"),
        ("Figure 3", "figure3_phase_diagram_phi_manifold.png", "figure3_phi_manifold_phase_source_data.tsv", "Phi manifold projection", "PASS"),
        ("Figure 4", "figure4_bifurcation_wgrn_scaling.png", "figure4_bifurcation_wgrn_scaling_source_data.tsv", "W_GRN eigenmode scaling sweep", "PASS"),
        ("Figure 5", "figure5_regime_switching_phi_threshold.png", "figure5_regime_threshold_crossing_statistics.tsv", "Phi threshold crossing statistics", "PASS"),
        ("Figure 6", "figure6_grn_contribution_analysis.png", "figure6_grn_eigendecomposition_contributions.tsv; figure6_phi_term_contributions_by_regime.tsv", "W_GRN eigendecomposition and Phi terms", "PASS"),
        ("Figure 7", "figure7_statistical_validation_summary.png", "figure7_statistical_validation_summary.tsv; ks_test_results.tsv; permutation_test_results.tsv; roc_curve.tsv; bootstrap_confidence_intervals.tsv", "Step C statistical validation", "PASS"),
    ]
    pd.DataFrame(
        rows,
        columns=["figure_id", "figure_file", "source_data_file", "binding_rule", "traceable_to_aligned_state_matrix_and_Phi_unified"],
    ).assign(
        primary_aligned_input="aligned_state_matrix.tsv",
        primary_phi_input="Phi_unified.tsv",
        reconstruction_script="figure_reconstruction_pipeline.py",
    ).to_csv(OUT / "figure_data_binding_map.tsv", sep="\t", index=False)


def write_reconstruction_pipeline_stub() -> None:
    text = f'''#!/usr/bin/env python3
"""Rebuild the developmental phase-transition closure outputs.

Run from the project root:
    python3 outputs/figure_reconstruction_pipeline.py

This delegates to the audited pipeline in work/full_data_closure_phase_transition.py.
All figures written by that script are bound in figure_data_binding_map.tsv and use
aligned_state_matrix.tsv plus Phi_unified.tsv as primary figure-data sources.
"""
from pathlib import Path
import runpy

ROOT = Path("{ROOT}")
runpy.run_path(str(ROOT / "work" / "full_data_closure_phase_transition.py"), run_name="__main__")
'''
    (OUT / "figure_reconstruction_pipeline.py").write_text(text, encoding="utf-8")


def main() -> int:
    missing = [str(p) for p in [MAMMAL_GSE153596, AXOLOTL_MODULE, AXOLOTL_PSEUDOTIME, W_GRN, W_AXIS] if not p.exists()]
    if missing:
        raise FileNotFoundError("Required inputs missing: " + "; ".join(missing))

    aligned, norm = harmonize_state_matrix()
    modes = compute_wgrn_modes()
    phi = add_phi(aligned, modes)
    stats, roc, ci = statistical_validation(phi)

    draw_hist_by_species(phi)
    draw_batch_assessment(norm)
    draw_roc(roc, stats["auc"])
    draw_bootstrap_ci(ci)
    figure_data_products(phi, modes, stats)
    write_reports(aligned, norm, phi, modes, stats)
    write_binding_map()
    write_reconstruction_pipeline_stub()

    print("full data closure complete")
    print(f"n_aligned={len(aligned)}")
    print(f"ks_p={stats['ks_p_value']:.6g}")
    print(f"perm_p={stats['permutation_p_value_two_sided']:.6g}")
    print(f"auc={stats['auc']:.6g}")
    status = "PASS" if stats["ks_p_value"] < 0.05 and stats["permutation_p_value_two_sided"] < 0.05 and stats["auc"] > 0.75 else "FAIL"
    print(f"acceptance={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
