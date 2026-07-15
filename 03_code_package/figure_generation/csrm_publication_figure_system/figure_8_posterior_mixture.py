#!/usr/bin/env python3
from __future__ import annotations

import numpy as np
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MplPath

from csrm_visual_system import (
    PALETTE,
    PZ_COLS,
    REGIME_COLORS,
    REGIME_ORDER,
    add_panel_label,
    add_subtitle,
    clean_axes,
    export_figure,
    make_figure,
    matrix_glyph,
    posterior_entropy,
    read_tsv,
    readable_label,
    require_columns,
    source_row,
    write_source_map,
)


FIGURE = "Figure_8"
STEM = "Figure_8_posterior_mixture"


def add_flow(ax, x0, y0, x1, y1, width, color, alpha=0.55):
    verts = [
        (x0, y0 + width / 2),
        ((x0 + x1) / 2, y0 + width / 2),
        ((x0 + x1) / 2, y1 + width / 2),
        (x1, y1 + width / 2),
        (x1, y1 - width / 2),
        ((x0 + x1) / 2, y1 - width / 2),
        ((x0 + x1) / 2, y0 - width / 2),
        (x0, y0 - width / 2),
        (x0, y0 + width / 2),
    ]
    codes = [
        MplPath.MOVETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.LINETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CLOSEPOLY,
    ]
    ax.add_patch(PathPatch(MplPath(verts, codes), facecolor=color, edgecolor="none", alpha=alpha))


def build() -> dict[str, str]:
    posterior = read_tsv("Figure_8/regime_posterior_probabilities.tsv")
    comp = read_tsv("Figure_8/observed_regime_to_latent_regime_composition.tsv")
    density = read_tsv("Figure_8/mixture_density_decomposition_phi.tsv")
    fit = read_tsv("Figure_8/latent_regime_mixture_fit_summary.tsv")
    require_columns(posterior, ["sample_id", "Fate_lock", "Embryonic_module_score", "Phi", *PZ_COLS], "Figure_8/regime_posterior_probabilities.tsv")
    require_columns(comp, ["observed_regime_proxy", "n_cells", *[f"mean_{c}" for c in PZ_COLS]], "Figure_8/observed_regime_to_latent_regime_composition.tsv")
    require_columns(density, ["latent_regime", "bin_center", "weighted_component_density"], "Figure_8/mixture_density_decomposition_phi.tsv")

    posterior = posterior.copy()
    posterior["dominant"] = posterior[PZ_COLS].idxmax(axis=1).str.replace("P_Z_", "", regex=False)
    posterior["entropy"] = posterior_entropy(posterior)
    sample = posterior.sort_values("sample_id").iloc[:: max(len(posterior) // 1600, 1)].copy()

    fig = make_figure(118)

    ax_map = fig.add_axes([0.06, 0.51, 0.36, 0.39])
    add_panel_label(ax_map, "a")
    add_subtitle(ax_map, "Posterior state-space map")
    rgba = []
    for _, row in sample.iterrows():
        base = REGIME_COLORS.get(row["dominant"], PALETTE["muted"])
        rgb = tuple(int(base.strip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4))
        alpha = 0.25 + 0.65 * (1 - float(row["entropy"]))
        rgba.append((*rgb, alpha))
    ax_map.scatter(sample["Fate_lock"], sample["Embryonic_module_score"], c=rgba, s=4, linewidths=0)
    ax_map.set_xlabel("Scalar proxy coordinate", fontsize=7.2)
    ax_map.set_ylabel("Embryonic module", fontsize=7.2)
    clean_axes(ax_map, grid=True)
    ax_map.text(0.03, 0.05, "opacity encodes lower posterior uncertainty", transform=ax_map.transAxes, fontsize=6.8, color=PALETTE["muted"])

    ax_flow = fig.add_axes([0.47, 0.50, 0.47, 0.40])
    ax_flow.set_xlim(0, 1)
    ax_flow.set_ylim(0, 1)
    ax_flow.axis("off")
    add_panel_label(ax_flow, "b", x=-0.04)
    ax_flow.text(0.02, 0.95, "Observed-group to latent-regime posterior allocation", fontsize=8.5, fontweight="bold", color=PALETTE["ink"], ha="left")
    obs_y = np.linspace(0.76, 0.28, len(comp))
    reg_y = np.linspace(0.80, 0.22, len(REGIME_ORDER))
    x0, x1 = 0.20, 0.78
    for y, (_, row) in zip(obs_y, comp.iterrows()):
        label = readable_label(row["observed_regime_proxy"]).replace("\n", " ")
        ax_flow.text(0.02, y, label, ha="left", va="center", fontsize=6.7, color=PALETTE["ink"])
        ax_flow.add_patch(Rectangle((x0 - 0.02, y - 0.018), 0.025, 0.036, facecolor=PALETTE["soft"], edgecolor=PALETTE["grid"], linewidth=0.5))
    for y, regime in zip(reg_y, REGIME_ORDER):
        ax_flow.add_patch(Rectangle((x1, y - 0.024), 0.035, 0.048, facecolor=REGIME_COLORS[regime], edgecolor="white", linewidth=0.5))
        ax_flow.text(x1 + 0.045, y, readable_label(regime).replace("\n", " "), ha="left", va="center", fontsize=6.7, color=PALETTE["ink"])
    scale = 0.075
    for y, (_, row) in zip(obs_y, comp.iterrows()):
        for ry, regime, col in zip(reg_y, REGIME_ORDER, [f"mean_{c}" for c in PZ_COLS]):
            val = float(row[col])
            add_flow(ax_flow, x0 + 0.01, y, x1, ry, max(val * scale, 0.003), REGIME_COLORS[regime], alpha=0.25 + 0.45 * val)
    ax_flow.text(0.50, 0.08, "ribbons show posterior mass, not lineage flow", ha="center", va="center", fontsize=7.0, color=PALETTE["matrix"], fontweight="bold")

    ax_den = fig.add_axes([0.06, 0.15, 0.28, 0.25])
    add_panel_label(ax_den, "c")
    add_subtitle(ax_den, "One Phi mixture-density view")
    for regime in REGIME_ORDER:
        sub = density[density["latent_regime"] == regime]
        if len(sub):
            ax_den.plot(sub["bin_center"], sub["weighted_component_density"], color=REGIME_COLORS[regime], lw=1.0, label=readable_label(regime).replace("\n", " "))
    ax_den.set_xlabel("Phi", fontsize=7.2)
    ax_den.set_ylabel("weighted density", fontsize=7.2)
    ax_den.legend(frameon=False, fontsize=5.7, ncol=1)
    clean_axes(ax_den, grid=False)

    ax_obj = fig.add_axes([0.43, 0.10, 0.49, 0.30])
    ax_obj.set_xlim(0, 1)
    ax_obj.set_ylim(0, 1)
    ax_obj.axis("off")
    add_panel_label(ax_obj, "d", x=-0.04)
    ax_obj.text(0.04, 0.88, "matrix and local transition representation", fontsize=8.5, fontweight="bold", color=PALETTE["ink"])
    matrix_glyph(ax_obj, 0.05, 0.28, 0.30, 0.35, posterior[PZ_COLS].head(5).to_numpy(float), label="M_ik")
    ax_obj.text(0.44, 0.58, "M_ik = P(Z=k | S_i, W_GRN)", fontsize=8.3, color=PALETTE["matrix"], fontweight="bold", ha="left")
    ax_obj.text(0.44, 0.42, "E[Delta S | S] = sum_k p_k(S) F_k(S)", fontsize=8.0, color=PALETTE["ink"], ha="left")
    if len(fit):
        ax_obj.text(0.44, 0.24, f"fit: {int(fit.loc[0,'n_components'])} latent state regimes; no AUC objective", fontsize=6.8, color=PALETTE["muted"], ha="left")

    outputs = export_figure(fig, STEM)
    write_source_map(
        FIGURE,
        [
            source_row("a", "Figure_8/regime_posterior_probabilities.tsv", ["sample_id", "Fate_lock", "Embryonic_module_score", *PZ_COLS], len(posterior), "deterministic thinning for display", "dominant posterior assignment and normalized entropy from supplied posterior probabilities", "Entropy is display-only uncertainty transform"),
            source_row("b", "Figure_8/observed_regime_to_latent_regime_composition.tsv", ["observed_regime_proxy", "n_cells", *[f"mean_{c}" for c in PZ_COLS]], len(comp), "none", "alluvial widths encode supplied mean posterior probabilities", "posterior mass allocation, not flow"),
            source_row("c", "Figure_8/mixture_density_decomposition_phi.tsv", ["latent_regime", "bin_center", "weighted_component_density"], len(density), "none", "single line-density view from supplied decomposition"),
            source_row("d", "Figure_8/regime_posterior_probabilities.tsv", ["sample_id", *PZ_COLS], len(posterior), "head rows for matrix glyph", "example posterior matrix object"),
            source_row("d", "Figure_8/latent_regime_mixture_fit_summary.tsv", ["model", "n_components", "objective"], len(fit), "none", "fit statement displayed"),
        ],
    )
    return outputs


if __name__ == "__main__":
    build()
