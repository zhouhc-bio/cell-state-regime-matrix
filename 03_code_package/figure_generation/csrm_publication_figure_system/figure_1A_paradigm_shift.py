#!/usr/bin/env python3
from __future__ import annotations

from matplotlib.patches import FancyArrowPatch, Rectangle

from csrm_visual_system import (
    PALETTE,
    export_figure,
    failed_scalar_axis,
    make_figure,
    matrix_glyph,
    posterior_ribbon,
    read_tsv,
    source_row,
    write_source_map,
)


FIGURE = "Figure_1A"
STEM = "Figure_1A_paradigm_shift"


def build() -> dict[str, str]:
    ks = read_tsv("Figure_7/ks_test_results.tsv")
    perm = read_tsv("Figure_7/permutation_test_results.tsv")
    boot = read_tsv("Figure_7/bootstrap_confidence_intervals.tsv")
    auc = float(ks.loc[0, "auc"])
    p_perm = float(perm.loc[0, "p_value_two_sided"])
    mean_ci = boot.loc[boot["metric"] == "mean_difference"].iloc[0]
    ci_crosses = float(mean_ci["ci_lower_2p5"]) < 0 < float(mean_ci["ci_upper_97p5"])

    fig = make_figure(82)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.04, 0.90, "a", fontsize=10.5, fontweight="bold", color=PALETTE["ink"])
    ax.text(0.075, 0.90, "Model replacement, not scalar refinement", fontsize=8.8, fontweight="bold", color=PALETTE["ink"])

    # 1. Failed scalar Phi axis
    failed_scalar_axis(ax, 0.055, 0.56, 0.16, label="failed Phi axis")
    ax.text(0.135, 0.43, "single coordinate\ncannot separate regimes", ha="center", va="center", fontsize=7.2, color=PALETTE["muted"])

    # 2. Evidence gate
    gate_x, gate_y, gate_w, gate_h = 0.27, 0.38, 0.145, 0.36
    ax.add_patch(Rectangle((gate_x, gate_y), gate_w, gate_h, facecolor=PALETTE["soft"], edgecolor=PALETTE["grid"], linewidth=0.7))
    ax.text(gate_x + gate_w / 2, gate_y + gate_h - 0.035, "evidence gate", ha="center", va="center", fontsize=7.7, fontweight="bold", color=PALETTE["ink"])
    evidence = [
        f"AUC {auc:.3f}",
        f"perm. p={p_perm:.3f}",
        "bootstrap CI crosses 0" if ci_crosses else "bootstrap CI check",
        "KS: shape, not separation",
    ]
    for i, item in enumerate(evidence):
        y = gate_y + gate_h - 0.085 - i * 0.065
        ax.plot([gate_x + 0.018, gate_x + 0.035], [y, y], color=PALETTE["failed_phi"], lw=1.0)
        ax.text(gate_x + 0.044, y, item, ha="left", va="center", fontsize=6.6, color=PALETTE["muted"])

    # 3. Replacement decision
    ax.text(0.505, 0.62, "replacement,\nnot refinement", ha="center", va="center", fontsize=10.5, fontweight="bold", color=PALETTE["failed_phi"])
    ax.plot([0.47, 0.54], [0.50, 0.50], color=PALETTE["failed_phi"], lw=1.1)

    # 4. Posterior regime ribbon
    ax.text(0.64, 0.70, "posterior regime representation", ha="center", va="center", fontsize=7.7, fontweight="bold", color=PALETTE["ink"])
    posterior_ribbon(ax, 0.55, 0.58, 0.18, 0.065, labels=False)
    ax.text(0.64, 0.52, "P(Z | S, W_GRN)", ha="center", va="center", fontsize=8.2, color=PALETTE["matrix"], fontweight="bold")

    # 5. Matrix glyph
    matrix_glyph(ax, 0.765, 0.47, 0.105, 0.18, label="CSRM")
    ax.text(0.817, 0.70, "cell-state\nregime matrix", ha="center", va="center", fontsize=7.5, color=PALETTE["matrix"], fontweight="bold")

    # 6. Biological interpretations
    outcomes = [
        ("organized\nregeneration", PALETTE["salamander_blastema"], 0.75),
        ("adult tissue\nrepair", PALETTE["adult_repair"], 0.58),
        ("tumour-like\nplasticity", PALETTE["tumour_like"], 0.41),
    ]
    for text, color, y in outcomes:
        ax.add_patch(Rectangle((0.905, y - 0.045), 0.075, 0.08, facecolor="white", edgecolor=color, linewidth=0.8))
        ax.text(0.942, y - 0.004, text, ha="center", va="center", fontsize=6.5, color=color, fontweight="bold")

    # Connectors
    for x0, x1 in [(0.225, 0.27), (0.415, 0.47), (0.54, 0.55), (0.73, 0.765), (0.87, 0.905)]:
        ax.add_patch(FancyArrowPatch((x0, 0.56), (x1, 0.56), arrowstyle="-|>", mutation_scale=7, lw=0.75, color=PALETTE["ink"]))
    for _, color, y in outcomes:
        ax.add_patch(FancyArrowPatch((0.87, 0.56), (0.905, y), arrowstyle="-|>", mutation_scale=6, lw=0.75, color=color, alpha=0.9))

    ax.text(0.50, 0.18, "Cell states are not ordered by a scalar; they are represented as posterior mixtures over latent state regimes.", ha="center", va="center", fontsize=8.2, color=PALETTE["matrix"], fontweight="bold")

    outputs = export_figure(fig, STEM)
    write_source_map(
        FIGURE,
        [
            source_row("evidence gate", "Figure_7/ks_test_results.tsv", ["auc", "ks_p_value"], len(ks), "none", "locked values displayed", "AUC and KS interpretation"),
            source_row("evidence gate", "Figure_7/permutation_test_results.tsv", ["p_value_two_sided", "observed"], len(perm), "none", "locked values displayed", "Permutation p-value"),
            source_row("evidence gate", "Figure_7/bootstrap_confidence_intervals.tsv", ["metric", "ci_lower_2p5", "ci_upper_97p5"], len(boot), "filter mean_difference", "locked CI crossing zero displayed", "No new interval computed"),
        ],
    )
    return outputs


if __name__ == "__main__":
    build()
