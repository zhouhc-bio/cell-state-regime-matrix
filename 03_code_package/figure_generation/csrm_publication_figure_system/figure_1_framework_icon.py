#!/usr/bin/env python3
from __future__ import annotations

import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

from csrm_visual_system import (
    PALETTE,
    PZ_COLS,
    REGIME_COLORS,
    REGIME_ORDER,
    add_panel_label,
    clean_axes,
    export_figure,
    failed_scalar_axis,
    make_figure,
    matrix_glyph,
    posterior_ribbon,
    read_tsv,
    readable_label,
    require_columns,
    source_row,
    write_source_map,
)


FIGURE = "Figure_1"
STEM = "Figure_1_framework_icon"


def select_matrix_rows(df):
    rows = []
    for regime, col in zip(REGIME_ORDER, PZ_COLS):
        sub = df.sort_values([col, "sample_id"], ascending=[False, True]).head(2)
        rows.append(sub)
    picked = np.concatenate([r.index.to_numpy() for r in rows])
    return df.loc[picked].reset_index(drop=True)


def build() -> dict[str, str]:
    posterior = read_tsv("Figure_8/regime_posterior_probabilities.tsv")
    require_columns(posterior, ["sample_id", "Fate_lock", "Embryonic_module_score", *PZ_COLS], "Figure_8/regime_posterior_probabilities.tsv")
    sample = posterior.sort_values("sample_id").iloc[:: max(len(posterior) // 1200, 1)].copy()
    sample["dominant"] = sample[PZ_COLS].idxmax(axis=1).str.replace("P_Z_", "", regex=False)
    matrix_rows = select_matrix_rows(posterior)
    matrix_values = matrix_rows[PZ_COLS].to_numpy(float)

    fig = make_figure(116)
    ax0 = fig.add_axes([0, 0, 1, 1])
    ax0.set_xlim(0, 1)
    ax0.set_ylim(0, 1)
    ax0.axis("off")

    ax0.text(0.04, 0.955, "Cell-State Regime Matrix framework", fontsize=9, color=PALETTE["ink"], fontweight="bold")
    ax0.text(0.04, 0.925, "Observed states are represented as posterior regime vectors, not scalar ranks.", fontsize=7.5, color=PALETTE["muted"])

    # a. Subordinate failed scalar axis
    ax_scalar = fig.add_axes([0.055, 0.58, 0.18, 0.18])
    ax_scalar.set_xlim(0, 1)
    ax_scalar.set_ylim(0, 1)
    ax_scalar.axis("off")
    add_panel_label(ax_scalar, "a", x=-0.12, y=1.05)
    failed_scalar_axis(ax_scalar, 0.08, 0.46, 0.78, label="Phi", rejected=True)
    ax_scalar.text(0.5, 0.10, "rejected scalar ordering", ha="center", va="center", fontsize=6.8, color=PALETTE["muted"])

    # b. Observed manifold
    ax_man = fig.add_axes([0.27, 0.50, 0.25, 0.31])
    add_panel_label(ax_man, "b")
    x = sample["Fate_lock"].to_numpy(float)
    y = sample["Embryonic_module_score"].to_numpy(float)
    colors = [REGIME_COLORS.get(r, PALETTE["muted"]) for r in sample["dominant"]]
    ax_man.scatter(x, y, s=4, c=colors, alpha=0.42, linewidths=0)
    clean_axes(ax_man, grid=True)
    ax_man.set_xlabel("Scalar proxy coordinate", fontsize=7.2)
    ax_man.set_ylabel("Embryonic module", fontsize=7.2)
    ax_man.set_title("Observed cell-state field", loc="left", fontsize=8.5, fontweight="bold")

    # c. Posterior vectors
    ax_vec = fig.add_axes([0.56, 0.52, 0.16, 0.28])
    ax_vec.set_xlim(0, 1)
    ax_vec.set_ylim(0, 1)
    ax_vec.axis("off")
    add_panel_label(ax_vec, "c", x=-0.03, y=1.08)
    ax_vec.text(0.5, 0.92, "posterior regime vectors", ha="center", va="center", fontsize=8.2, fontweight="bold", color=PALETTE["ink"])
    for i, row in enumerate(matrix_values[:5]):
        yy = 0.76 - i * 0.145
        posterior_ribbon(ax_vec, 0.08, yy, 0.84, 0.055, row)
    ax_vec.text(0.5, 0.05, "P(Z | S, W_GRN)", ha="center", va="center", fontsize=7.5, color=PALETTE["matrix"], fontweight="bold")

    # d. Matrix
    ax_mat = fig.add_axes([0.74, 0.45, 0.20, 0.35])
    ax_mat.set_xlim(0, 1)
    ax_mat.set_ylim(0, 1)
    ax_mat.axis("off")
    add_panel_label(ax_mat, "d", x=-0.08)
    matrix_glyph(ax_mat, 0.18, 0.20, 0.64, 0.56, matrix_values, row_labels=[f"S{i+1}" for i in range(len(matrix_values))], label="M_ik = P(Z=k | S_i, W_GRN)")
    ax_mat.text(0.50, 0.91, "cell-state regime matrix", ha="center", va="center", fontsize=8.2, color=PALETTE["matrix"], fontweight="bold")
    ax_mat.text(0.50, 0.09, "rows = observed S_i; columns = latent regimes", ha="center", va="center", fontsize=5.8, color=PALETTE["muted"])

    # e. Biological interpretation
    ax_out = fig.add_axes([0.15, 0.11, 0.70, 0.22])
    ax_out.set_xlim(0, 1)
    ax_out.set_ylim(0, 1)
    ax_out.axis("off")
    add_panel_label(ax_out, "e", x=-0.03)
    ax_out.text(0.5, 0.90, "biological interpretation is downstream of posterior regime structure", ha="center", va="center", fontsize=8.4, color=PALETTE["ink"], fontweight="bold")
    outcomes = [
        ("organized\nregeneration", PALETTE["salamander_blastema"], 0.17),
        ("adult tissue\nrepair", PALETTE["adult_repair"], 0.39),
        ("posterior-mixed\nstates", PALETTE["matrix"], 0.61),
        ("tumour-like\nboundary", PALETTE["tumour_like"], 0.83),
    ]
    for text, color, cx in outcomes:
        ax_out.add_patch(Rectangle((cx - 0.085, 0.30), 0.17, 0.25, facecolor="white", edgecolor=color, linewidth=0.8))
        ax_out.text(cx, 0.425, text, ha="center", va="center", fontsize=6.3, color=color, fontweight="bold")
    ax_out.text(0.86, 0.18, "outside locked four-regime vocabulary", ha="center", va="center", fontsize=6.3, color=PALETTE["tumour_like"])

    # Figure-level arrows
    for start, end in [((0.235, 0.66), (0.27, 0.66)), ((0.52, 0.66), (0.56, 0.66)), ((0.72, 0.66), (0.74, 0.66)), ((0.84, 0.45), (0.58, 0.33))]:
        ax0.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=7, lw=0.75, color=PALETTE["ink"], transform=ax0.transAxes))

    outputs = export_figure(fig, STEM)
    write_source_map(
        FIGURE,
        [
            source_row("b", "Figure_8/regime_posterior_probabilities.tsv", ["sample_id", "Fate_lock", "Embryonic_module_score", *PZ_COLS], len(posterior), "deterministic thinning for display", "dominant posterior assignment used for color", "No new statistics"),
            source_row("c,d", "Figure_8/regime_posterior_probabilities.tsv", ["sample_id", *PZ_COLS], len(posterior), "top two cells per dominant posterior regime", "transparent row selection for example matrix", "Rows are observed examples"),
        ],
    )
    return outputs


if __name__ == "__main__":
    build()
