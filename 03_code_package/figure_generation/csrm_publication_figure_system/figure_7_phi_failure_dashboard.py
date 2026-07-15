#!/usr/bin/env python3
from __future__ import annotations

import numpy as np
from matplotlib.patches import Rectangle

from csrm_visual_system import (
    PALETTE,
    add_panel_label,
    add_subtitle,
    clean_axes,
    export_figure,
    make_figure,
    read_tsv,
    readable_label,
    regime_color_for_name,
    require_columns,
    source_row,
    write_source_map,
)


FIGURE = "Figure_7"
STEM = "Figure_7_phi_failure_dashboard"


def build() -> dict[str, str]:
    phi = read_tsv("Figure_7/Phi_unified.tsv")
    roc = read_tsv("Figure_7/roc_curve.tsv")
    null = read_tsv("Figure_7/permutation_null_distribution.tsv")
    perm = read_tsv("Figure_7/permutation_test_results.tsv")
    boot = read_tsv("Figure_7/bootstrap_confidence_intervals.tsv")
    ks = read_tsv("Figure_7/ks_test_results.tsv")
    require_columns(phi, ["Phi", "regime_group"], "Figure_7/Phi_unified.tsv")
    require_columns(roc, ["FPR", "TPR"], "Figure_7/roc_curve.tsv")
    require_columns(null, ["mean_difference_null"], "Figure_7/permutation_null_distribution.tsv")
    require_columns(perm, ["observed", "p_value_two_sided"], "Figure_7/permutation_test_results.tsv")
    require_columns(boot, ["metric", "estimate", "ci_lower_2p5", "ci_upper_97p5"], "Figure_7/bootstrap_confidence_intervals.tsv")
    require_columns(ks, ["auc", "ks_p_value"], "Figure_7/ks_test_results.tsv")

    auc = float(ks.loc[0, "auc"])
    p_perm = float(perm.loc[0, "p_value_two_sided"])
    obs = float(perm.loc[0, "observed"])
    ks_p = float(ks.loc[0, "ks_p_value"])

    fig = make_figure(116)

    ax_roc = fig.add_axes([0.34, 0.50, 0.35, 0.40])
    add_panel_label(ax_roc, "b")
    add_subtitle(ax_roc, "ROC anchor: random-level scalar discrimination")
    ax_roc.plot([0, 1], [0, 1], color=PALETTE["grid"], lw=0.9)
    ax_roc.plot(roc["FPR"], roc["TPR"], color=PALETTE["failed_phi"], lw=1.2)
    ax_roc.set_xlim(0, 1)
    ax_roc.set_ylim(0, 1)
    ax_roc.set_xlabel("false positive rate", fontsize=7.2)
    ax_roc.set_ylabel("true positive rate", fontsize=7.2)
    ax_roc.text(0.58, 0.18, f"AUC = {auc:.3f}", transform=ax_roc.transAxes, fontsize=10.0, fontweight="bold", color=PALETTE["failed_phi"])
    ax_roc.text(0.58, 0.10, "classifier failed", transform=ax_roc.transAxes, fontsize=7.0, color=PALETTE["muted"])
    clean_axes(ax_roc, grid=True)

    ax_phi = fig.add_axes([0.06, 0.57, 0.23, 0.33])
    add_panel_label(ax_phi, "a")
    add_subtitle(ax_phi, "Empirical Phi distributions")
    groups = [g for g in ["mammalian_inflammatory_repair", "salamander_blastema_reactivation", "salamander_intact_reference"] if g in set(phi["regime_group"])]
    bins = np.linspace(float(phi["Phi"].quantile(0.005)), float(phi["Phi"].quantile(0.995)), 70)
    for group in groups:
        vals = phi.loc[phi["regime_group"] == group, "Phi"].dropna().to_numpy()
        hist, edges = np.histogram(vals, bins=bins, density=True)
        centers = (edges[:-1] + edges[1:]) / 2
        ax_phi.plot(centers, hist, color=regime_color_for_name(group), lw=1.0, label=readable_label(group).replace("\n", " "))
    ax_phi.set_xlabel("Phi", fontsize=7.2)
    ax_phi.set_ylabel("density", fontsize=7.2)
    ax_phi.legend(frameon=False, fontsize=5.9, loc="upper right")
    clean_axes(ax_phi, grid=False)

    ax_perm = fig.add_axes([0.06, 0.18, 0.30, 0.25])
    add_panel_label(ax_perm, "c")
    add_subtitle(ax_perm, "Permutation null: mean shift unsupported")
    vals = null["mean_difference_null"].dropna().to_numpy()
    ax_perm.hist(vals, bins=55, histtype="stepfilled", color="#E8EEF3", edgecolor=PALETTE["matrix"], linewidth=0.8)
    ax_perm.axvline(obs, color=PALETTE["failed_phi"], lw=1.1)
    ax_perm.text(0.04, 0.88, f"observed = {obs:.3f}\np = {p_perm:.3f}", transform=ax_perm.transAxes, fontsize=7.2, color=PALETTE["failed_phi"], fontweight="bold", va="top")
    ax_perm.set_xlabel("mean difference under label shuffle", fontsize=7.2)
    ax_perm.set_ylabel("count", fontsize=7.2)
    clean_axes(ax_perm, grid=False)

    ax_boot = fig.add_axes([0.42, 0.18, 0.25, 0.25])
    add_panel_label(ax_boot, "d")
    add_subtitle(ax_boot, "Bootstrap uncertainty")
    boot_plot = boot.copy().reset_index(drop=True)
    y = np.arange(len(boot_plot))
    ax_boot.axvline(0, color=PALETTE["grid"], lw=0.9)
    for i, row in boot_plot.iterrows():
        color = PALETTE["failed_phi"] if row["metric"] in {"mean_difference", "auc"} else PALETTE["matrix"]
        ax_boot.plot([row["ci_lower_2p5"], row["ci_upper_97p5"]], [i, i], color=color, lw=1.1)
        ax_boot.scatter([row["estimate"]], [i], color=color, s=18, zorder=3)
    ax_boot.set_yticks(y)
    ax_boot.set_yticklabels([str(x).replace("_", " ") for x in boot_plot["metric"]], fontsize=6.5)
    ax_boot.set_xlabel("estimate and 95% bootstrap CI", fontsize=7.2)
    ax_boot.invert_yaxis()
    clean_axes(ax_boot, grid=True)

    ax_verdict = fig.add_axes([0.73, 0.18, 0.22, 0.72])
    ax_verdict.set_xlim(0, 1)
    ax_verdict.set_ylim(0, 1)
    ax_verdict.axis("off")
    add_panel_label(ax_verdict, "e", x=-0.08, y=1.02)
    ax_verdict.text(0.02, 0.96, "verdict rail", fontsize=8.5, fontweight="bold", color=PALETTE["ink"], ha="left")
    verdicts = [
        ("classification failed", f"AUC {auc:.3f}", PALETTE["failed_phi"]),
        ("mean shift unsupported", f"p {p_perm:.3f}", PALETTE["failed_phi"]),
        ("uncertainty crosses zero", "mean CI includes 0", PALETTE["failed_phi"]),
        ("KS is shape only", f"p {ks_p:.1e}", PALETTE["muted"]),
    ]
    for i, (title, detail, color) in enumerate(verdicts):
        y0 = 0.80 - i * 0.19
        ax_verdict.add_patch(Rectangle((0.02, y0), 0.92, 0.13, facecolor=PALETTE["soft"], edgecolor=color, linewidth=0.75))
        ax_verdict.text(0.06, y0 + 0.083, title, fontsize=7.0, color=color, fontweight="bold", ha="left", va="center")
        ax_verdict.text(0.06, y0 + 0.038, detail, fontsize=6.5, color=PALETTE["muted"], ha="left", va="center")
    ax_verdict.text(0.50, 0.04, "Phi is a rejected scalar proxy,\nnot a softened CSRM model.", ha="center", va="center", fontsize=7.2, color=PALETTE["matrix"], fontweight="bold")

    outputs = export_figure(fig, STEM)
    write_source_map(
        FIGURE,
        [
            source_row("a", "Figure_7/Phi_unified.tsv", ["Phi", "regime_group"], len(phi), "empirical histogram density", "no smoothing; no new tests"),
            source_row("b", "Figure_7/roc_curve.tsv", ["FPR", "TPR"], len(roc), "none", "ROC curve from locked table"),
            source_row("b,e", "Figure_7/ks_test_results.tsv", ["auc", "ks_p_value"], len(ks), "none", "locked AUC and KS p displayed"),
            source_row("c,e", "Figure_7/permutation_null_distribution.tsv", ["mean_difference_null"], len(null), "histogram", "null distribution displayed"),
            source_row("c,e", "Figure_7/permutation_test_results.tsv", ["observed", "p_value_two_sided"], len(perm), "none", "locked observed statistic and p displayed"),
            source_row("d,e", "Figure_7/bootstrap_confidence_intervals.tsv", ["metric", "estimate", "ci_lower_2p5", "ci_upper_97p5"], len(boot), "none", "locked bootstrap CIs displayed"),
        ],
    )
    return outputs


if __name__ == "__main__":
    build()
