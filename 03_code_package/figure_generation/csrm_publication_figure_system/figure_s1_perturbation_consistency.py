#!/usr/bin/env python3
from __future__ import annotations

import numpy as np
import matplotlib as mpl
from matplotlib.patches import Rectangle

from csrm_visual_system import (
    PALETTE,
    REGIME_COLORS,
    REGIME_ORDER,
    add_panel_label,
    clean_axes,
    export_figure,
    make_figure,
    read_tsv,
    readable_label,
    require_columns,
    source_row,
    write_source_map,
)


FIGURE = "Supplementary_Figure_1"
STEM = "Supplementary_Figure_1_perturbation_consistency"


def zscore(values):
    arr = np.asarray(values, dtype=float)
    if np.nanmax(arr) - np.nanmin(arr) == 0:
        return np.zeros_like(arr)
    return (arr - np.nanmin(arr)) / (np.nanmax(arr) - np.nanmin(arr))


def draw_status_box(ax, y, title, value, color, note):
    ax.add_patch(Rectangle((0.03, y - 0.080), 0.94, 0.15, facecolor=PALETTE["soft"], edgecolor=color, linewidth=0.8))
    ax.text(0.08, y + 0.035, title, ha="left", va="center", fontsize=6.8, fontweight="bold", color=color)
    ax.text(0.08, y - 0.010, value, ha="left", va="center", fontsize=6.5, color=PALETTE["ink"])
    ax.text(0.08, y - 0.050, note, ha="left", va="center", fontsize=5.6, color=PALETTE["muted"])


def build() -> dict[str, str]:
    closure = read_tsv("Supplementary_Figure_1/closure_model_comparison.tsv")
    scores = read_tsv("Supplementary_Figure_1/causal_closure_score_summary.tsv")
    delta = read_tsv("Supplementary_Figure_1/regime_conditioned_deltaZ_consistency.tsv")
    nulls = read_tsv("Supplementary_Figure_1/null_perturbation_control_results.tsv")
    counter = read_tsv("Supplementary_Figure_1/counterfactual_consistency_scores.tsv")
    grn = read_tsv("Supplementary_Figure_1/regime_conditioned_grn_summary.tsv")

    require_columns(closure, ["global_MSE", "regime_conditioned_MSE_LOO", "counterfactual_direction_reversal_frequency", "final_closure_classification"], "Supplementary_Figure_1/closure_model_comparison.tsv")
    require_columns(scores, ["pathway", "directional_consistency_component", "counterfactual_agreement_component", "null_separation_component", "CCS_available_evidence_rescaled", "available_weight_fraction"], "Supplementary_Figure_1/causal_closure_score_summary.tsv")
    require_columns(delta, ["pathway", "latent_regime", "global_abs_error", "regime_conditioned_abs_error_LOO", "regime_conditioned_sign_alignment_LOO"], "Supplementary_Figure_1/regime_conditioned_deltaZ_consistency.tsv")
    require_columns(nulls, ["pathway", "null_component_score"], "Supplementary_Figure_1/null_perturbation_control_results.tsv")
    require_columns(counter, ["pathway", "counterfactual_component_score"], "Supplementary_Figure_1/counterfactual_consistency_scores.tsv")
    require_columns(grn, ["latent_regime", "module", "mean_abs_regime_conditioned_weight"], "Supplementary_Figure_1/regime_conditioned_grn_summary.tsv")

    row = closure.iloc[0]
    global_mse = float(row["global_MSE"])
    regime_mse = float(row["regime_conditioned_MSE_LOO"])
    reduction = float(row["prediction_error_reduction_fraction"])
    reversal = float(row["counterfactual_direction_reversal_frequency"])

    fig = make_figure(142)

    ax_model = fig.add_axes([0.06, 0.62, 0.22, 0.25])
    add_panel_label(ax_model, "a")
    ax_model.bar([0, 1], [global_mse, regime_mse], color=[PALETTE["adult_repair"], PALETTE["matrix"]], width=0.55)
    ax_model.set_xticks([0, 1], ["global W", "regime W(Z)"], fontsize=6.8)
    ax_model.set_ylabel("mean squared error", fontsize=7.2)
    ax_model.set_title("Prediction error", loc="left", fontsize=7.4, fontweight="bold")
    ax_model.text(0.03, 0.92, f"error reduction {reduction:.2f}", transform=ax_model.transAxes, fontsize=7.0, color=PALETTE["matrix"], fontweight="bold")
    clean_axes(ax_model, grid=True)

    ax_score = fig.add_axes([0.37, 0.62, 0.26, 0.25])
    add_panel_label(ax_score, "b")
    components = [
        "directional_consistency_component",
        "counterfactual_agreement_component",
        "null_separation_component",
        "CCS_available_evidence_rescaled",
    ]
    mat = scores.set_index("pathway")[components].astype(float)
    cmap = mpl.colormaps["Blues"]
    ax_score.set_xlim(-0.5, mat.shape[1] - 0.5)
    ax_score.set_ylim(mat.shape[0] - 0.5, -0.5)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = mat.iat[i, j]
            ax_score.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=cmap(float(val)), edgecolor="white", linewidth=0.45))
    ax_score.set_xticks(range(len(components)), ["direction", "counterfactual", "null", "CCS"], rotation=30, ha="right", fontsize=6.3)
    ax_score.set_yticks(range(len(mat.index)), mat.index, fontsize=6.6)
    ax_score.set_title("Evidence components", loc="left", fontsize=7.4, fontweight="bold")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = mat.iat[i, j]
            ax_score.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=5.7, color="white" if val > 0.55 else PALETTE["ink"])
    for spine in ax_score.spines.values():
        spine.set_visible(False)

    ax_delta = fig.add_axes([0.73, 0.62, 0.21, 0.25])
    add_panel_label(ax_delta, "c")
    agg = delta.groupby("latent_regime", as_index=False).agg(
        global_error=("global_abs_error", "mean"),
        conditioned_error=("regime_conditioned_abs_error_LOO", "mean"),
        alignment=("regime_conditioned_sign_alignment_LOO", "mean"),
    )
    agg["latent_regime"] = [r for r in REGIME_ORDER if r in set(agg["latent_regime"])]
    x = np.arange(len(agg))
    width = 0.35
    ax_delta.bar(x - width / 2, agg["global_error"], width=width, color=PALETTE["adult_repair"], alpha=0.75, label="global W")
    ax_delta.bar(x + width / 2, agg["conditioned_error"], width=width, color=PALETTE["matrix"], alpha=0.85, label="regime W(Z)")
    ax_delta.set_xticks(x, [readable_label(r).replace("\n", " ") for r in agg["latent_regime"]], rotation=25, ha="right", fontsize=6.2)
    ax_delta.set_ylabel("mean abs. error", fontsize=7.0)
    ax_delta.set_title("Regime-dependent improvement", loc="left", fontsize=7.4, fontweight="bold")
    ax_delta.legend(frameon=False, fontsize=5.8)
    clean_axes(ax_delta, grid=True)

    ax_null = fig.add_axes([0.06, 0.15, 0.28, 0.30])
    add_panel_label(ax_null, "d")
    merged = scores[["pathway", "CCS_available_evidence_rescaled"]].merge(nulls[["pathway", "null_component_score"]], on="pathway", how="left").merge(counter[["pathway", "counterfactual_component_score"]], on="pathway", how="left")
    xx = np.arange(len(merged))
    ax_null.plot(xx, merged["CCS_available_evidence_rescaled"], color=PALETTE["matrix"], lw=1.0, marker="o", ms=3, label="CCS")
    ax_null.plot(xx, merged["null_component_score"], color=PALETTE["embryonic_reactivation"], lw=1.0, marker="s", ms=3, label="null separation")
    ax_null.plot(xx, merged["counterfactual_component_score"], color=PALETTE["tumour_like"], lw=1.0, marker="^", ms=3, label="counterfactual")
    ax_null.set_xticks(xx, merged["pathway"], fontsize=6.5)
    ax_null.set_ylim(-0.05, 1.05)
    ax_null.set_ylabel("component score", fontsize=7.0)
    ax_null.set_title("Evidence is partial, not causal closure", loc="left", fontsize=7.4, fontweight="bold")
    ax_null.legend(frameon=False, fontsize=5.8, ncol=1)
    clean_axes(ax_null, grid=True)

    ax_w = fig.add_axes([0.41, 0.15, 0.25, 0.30])
    add_panel_label(ax_w, "e")
    all_modules = grn[grn["module"].eq("ALL_MODULES")].copy()
    if not len(all_modules):
        all_modules = grn.groupby("latent_regime", as_index=False)["mean_abs_regime_conditioned_weight"].mean()
    all_modules["latent_regime"] = [r for r in REGIME_ORDER if r in set(all_modules["latent_regime"])]
    vals = all_modules["mean_abs_regime_conditioned_weight"].to_numpy(float)
    ax_w.bar(np.arange(len(all_modules)), vals, color=[REGIME_COLORS.get(r, PALETTE["muted"]) for r in all_modules["latent_regime"]], width=0.6)
    ax_w.set_xticks(np.arange(len(all_modules)), [readable_label(r).replace("\n", " ") for r in all_modules["latent_regime"]], rotation=25, ha="right", fontsize=6.2)
    ax_w.set_ylabel("mean |W(Z)|", fontsize=7.0)
    ax_w.set_title("Regime-conditioned GRN summaries", loc="left", fontsize=7.4, fontweight="bold")
    clean_axes(ax_w, grid=True)

    ax_verdict = fig.add_axes([0.72, 0.13, 0.23, 0.36])
    ax_verdict.set_xlim(0, 1)
    ax_verdict.set_ylim(0, 1)
    ax_verdict.axis("off")
    add_panel_label(ax_verdict, "f", x=-0.04, y=1.02)
    ax_verdict.text(0.03, 0.95, "interpretation boundary", ha="left", va="center", fontsize=7.5, fontweight="bold", color=PALETTE["ink"])
    draw_status_box(ax_verdict, 0.72, "partial closure", f"MSE {global_mse:.4f} -> {regime_mse:.4f}", PALETTE["matrix"], "local support")
    draw_status_box(ax_verdict, 0.50, "counterfactual limits", f"reversal frequency {reversal:.2f}", PALETTE["tumour_like"], "not full closure")
    draw_status_box(ax_verdict, 0.28, "claim boundary", str(row["final_closure_classification"]), PALETTE["failed_phi"], "dry-lab only")
    ax_verdict.text(0.50, 0.08, "Supports regime-conditioned consistency,\nnot wet-lab causal validation.", ha="center", va="center", fontsize=6.7, color=PALETTE["matrix"], fontweight="bold")

    outputs = export_figure(fig, STEM)
    write_source_map(
        FIGURE,
        [
            source_row("a", "Supplementary_Figure_1/closure_model_comparison.tsv", ["global_MSE", "regime_conditioned_MSE_LOO", "prediction_error_reduction_fraction"], len(closure), "none", "displayed locked model-comparison values", "No new statistics"),
            source_row("b,d", "Supplementary_Figure_1/causal_closure_score_summary.tsv", ["pathway", *components, "available_weight_fraction"], len(scores), "none", "pathway evidence score display", "No new statistics"),
            source_row("c", "Supplementary_Figure_1/regime_conditioned_deltaZ_consistency.tsv", ["latent_regime", "global_abs_error", "regime_conditioned_abs_error_LOO", "regime_conditioned_sign_alignment_LOO"], len(delta), "mean by latent_regime", "summary display from supplied rows", "No new hypothesis tests"),
            source_row("d", "Supplementary_Figure_1/null_perturbation_control_results.tsv", ["pathway", "null_component_score"], len(nulls), "none", "line display of supplied score"),
            source_row("d", "Supplementary_Figure_1/counterfactual_consistency_scores.tsv", ["pathway", "counterfactual_component_score"], len(counter), "none", "line display of supplied score"),
            source_row("e", "Supplementary_Figure_1/regime_conditioned_grn_summary.tsv", ["latent_regime", "module", "mean_abs_regime_conditioned_weight"], len(grn), "ALL_MODULES if available", "bar display of supplied summary"),
        ],
    )
    return outputs


if __name__ == "__main__":
    build()
