#!/usr/bin/env python3
from __future__ import annotations

import itertools
import numpy as np
from matplotlib.patches import Circle, Rectangle

from csrm_visual_system import (
    PALETTE,
    REGIME_COLORS,
    REGIME_ORDER,
    add_panel_label,
    add_subtitle,
    clean_axes,
    export_figure,
    make_figure,
    read_tsv,
    readable_label,
    require_columns,
    source_row,
    write_source_map,
)


FIGURE = "Figure_9"
STEM = "Figure_9_overlap_divergence"


def undirected_pairs(df, value_col):
    rows = []
    seen = set()
    for _, row in df.iterrows():
        a, b = row.iloc[0], row.iloc[1]
        key = tuple(sorted([a, b]))
        if a == b or key in seen:
            continue
        seen.add(key)
        rows.append({"a": a, "b": b, value_col: float(row[value_col])})
    return rows


def build() -> dict[str, str]:
    overlap = read_tsv("Figure_9/regime_overlap_matrix.tsv")
    kl = read_tsv("Figure_9/regime_KL_divergence_matrix.tsv")
    post_overlap = read_tsv("Figure_9/regime_posterior_overlap_matrix.tsv")
    require_columns(overlap, ["regime_i", "regime_j", "bhattacharyya_overlap_proxy"], "Figure_9/regime_overlap_matrix.tsv")
    require_columns(kl, ["regime_i", "regime_j", "symmetric_KL"], "Figure_9/regime_KL_divergence_matrix.tsv")
    require_columns(post_overlap, ["assigned_regime", "posterior_regime", "mean_posterior_probability"], "Figure_9/regime_posterior_overlap_matrix.tsv")

    fig = make_figure(122)
    ax_net = fig.add_axes([0.06, 0.52, 0.36, 0.38])
    ax_net.set_xlim(0, 1)
    ax_net.set_ylim(0, 1)
    ax_net.axis("off")
    add_panel_label(ax_net, "a", x=-0.04)
    ax_net.text(0.02, 0.98, "Overlap network: non-separability without identity", fontsize=8.5, fontweight="bold", color=PALETTE["ink"], ha="left", va="top")
    positions = {
        "adult_repair": (0.20, 0.50),
        "embryonic_reactivation": (0.50, 0.80),
        "salamander_blastema": (0.80, 0.50),
        "salamander_intact": (0.50, 0.20),
    }
    label_offsets = {
        "adult_repair": (-0.06, -0.11, "right"),
        "embryonic_reactivation": (0.00, 0.09, "center"),
        "salamander_blastema": (0.02, -0.13, "center"),
        "salamander_intact": (0.00, -0.10, "center"),
    }
    od = {(r["regime_i"], r["regime_j"]): float(r["bhattacharyya_overlap_proxy"]) for _, r in overlap.iterrows()}
    for a, b in itertools.combinations(REGIME_ORDER, 2):
        val = od.get((a, b), od.get((b, a), 0))
        x0, y0 = positions[a]
        x1, y1 = positions[b]
        highlight = set([a, b]) == {"adult_repair", "salamander_blastema"}
        ax_net.plot([x0, x1], [y0, y1], color=PALETTE["grid"] if not highlight else PALETTE["failed_phi"], lw=0.55 + 3.2 * val, alpha=0.50 if not highlight else 0.78)
        if highlight:
            ax_net.text((x0 + x1) / 2, (y0 + y1) / 2 + 0.04, f"overlap {val:.2f}", fontsize=6.2, color=PALETTE["failed_phi"], ha="center", va="center", fontweight="bold")
    for regime, (x, y) in positions.items():
        ax_net.add_patch(Circle((x, y), 0.055, facecolor=REGIME_COLORS[regime], edgecolor="white", linewidth=0.8, zorder=4))
        dx, dy, ha = label_offsets[regime]
        ax_net.text(x + dx, y + dy, readable_label(regime).replace("\n", " "), ha=ha, va="center", fontsize=6.2, color=PALETTE["ink"])
    ax_net.text(0.50, 0.04, "edge width = supplied overlap proxy; no arrows, no causality", ha="center", va="center", fontsize=6.3, color=PALETTE["muted"])

    ax_mat = fig.add_axes([0.61, 0.56, 0.31, 0.30])
    add_panel_label(ax_mat, "b")
    add_subtitle(ax_mat, "One overlap matrix retained for exact values")
    mat = np.zeros((len(REGIME_ORDER), len(REGIME_ORDER)))
    for i, a in enumerate(REGIME_ORDER):
        for j, b in enumerate(REGIME_ORDER):
            mat[i, j] = od.get((a, b), od.get((b, a), np.nan))
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            alpha = 0.10 + 0.78 * v
            ax_mat.add_patch(Rectangle((j, mat.shape[0] - 1 - i), 1, 1, facecolor=PALETTE["matrix"], alpha=alpha, edgecolor="white", linewidth=0.55))
            ax_mat.text(j + 0.5, mat.shape[0] - 0.5 - i, f"{v:.2f}", ha="center", va="center", fontsize=6.0, color="white" if v > 0.55 else PALETTE["ink"])
    ax_mat.set_xlim(0, 4)
    ax_mat.set_ylim(0, 4)
    ax_mat.set_xticks(np.arange(4) + 0.5)
    ax_mat.set_yticks(np.arange(4) + 0.5)
    ax_mat.set_xticklabels([readable_label(r).replace("\n", " ") for r in REGIME_ORDER], fontsize=5.8, rotation=28, ha="right")
    ax_mat.set_yticklabels(list(reversed([readable_label(r).replace("\n", " ") for r in REGIME_ORDER])), fontsize=5.8)
    ax_mat.tick_params(length=0)
    for spine in ax_mat.spines.values():
        spine.set_visible(False)

    ax_rank = fig.add_axes([0.10, 0.12, 0.38, 0.25])
    add_panel_label(ax_rank, "c", x=-0.08)
    add_subtitle(ax_rank, "Symmetrized KL divergence ranking")
    kl_pairs = undirected_pairs(kl, "symmetric_KL")
    kl_pairs = sorted(kl_pairs, key=lambda x: x["symmetric_KL"], reverse=True)[:6]
    labels = [f"{readable_label(r['a']).replace(chr(10),' ')} vs {readable_label(r['b']).replace(chr(10),' ')}" for r in kl_pairs]
    vals = [r["symmetric_KL"] for r in kl_pairs]
    y = np.arange(len(vals))
    ax_rank.hlines(y, 0, vals, color=PALETTE["grid"], lw=1.0)
    colors = [PALETTE["failed_phi"] if set([r["a"], r["b"]]) == {"adult_repair", "salamander_blastema"} else PALETTE["matrix"] for r in kl_pairs]
    ax_rank.scatter(vals, y, s=26, color=colors, zorder=3)
    ax_rank.set_yticks(y)
    ax_rank.set_yticklabels(labels, fontsize=5.8)
    ax_rank.invert_yaxis()
    ax_rank.set_xlabel("symmetrized KL divergence", fontsize=7.2)
    clean_axes(ax_rank, grid=True)

    ax_pair = fig.add_axes([0.62, 0.12, 0.30, 0.25])
    add_panel_label(ax_pair, "d")
    add_subtitle(ax_pair, "Overlap and divergence are different statements")
    overlap_pairs = {tuple(sorted([r["a"], r["b"]])): r["bhattacharyya_overlap_proxy"] for r in undirected_pairs(overlap, "bhattacharyya_overlap_proxy")}
    xs, ys, cs, labs = [], [], [], []
    for r in undirected_pairs(kl, "symmetric_KL"):
        key = tuple(sorted([r["a"], r["b"]]))
        if key in overlap_pairs:
            xs.append(overlap_pairs[key])
            ys.append(r["symmetric_KL"])
            cs.append(PALETTE["failed_phi"] if set(key) == {"adult_repair", "salamander_blastema"} else PALETTE["matrix"])
            labs.append(key)
    ax_pair.scatter(xs, ys, s=28, color=cs, alpha=0.9)
    for x, yv, key in zip(xs, ys, labs):
        if set(key) == {"adult_repair", "salamander_blastema"}:
            ax_pair.annotate("adult repair vs blastema", xy=(x, yv), xytext=(0.22, 13.2), textcoords="data", fontsize=6.2, color=PALETTE["failed_phi"], arrowprops={"arrowstyle": "-", "color": PALETTE["failed_phi"], "lw": 0.6})
    ax_pair.set_xlabel("overlap proxy", fontsize=7.2)
    ax_pair.set_ylabel("symmetrized KL", fontsize=7.2)
    clean_axes(ax_pair, grid=True)
    ax_pair.text(0.03, 0.08, "KL is distributional divergence,\nnot a scalar biological axis", transform=ax_pair.transAxes, fontsize=6.2, color=PALETTE["muted"], va="bottom")

    outputs = export_figure(fig, STEM)
    write_source_map(
        FIGURE,
        [
            source_row("a,b,d", "Figure_9/regime_overlap_matrix.tsv", ["regime_i", "regime_j", "bhattacharyya_overlap_proxy"], len(overlap), "pairwise matrix lookup", "network edge width and matrix cells from supplied overlap values", "Fixed deterministic layout"),
            source_row("c,d", "Figure_9/regime_KL_divergence_matrix.tsv", ["regime_i", "regime_j", "symmetric_KL"], len(kl), "undirected pair deduplication for display", "ranked lollipop and overlap-versus-KL scatter", "No new divergence computed"),
            source_row("source audit", "Figure_9/regime_posterior_overlap_matrix.tsv", ["assigned_regime", "posterior_regime", "mean_posterior_probability"], len(post_overlap), "none", "available but not plotted to avoid repeated heatmaps", "Used as source completeness check"),
        ],
    )
    return outputs


if __name__ == "__main__":
    build()
