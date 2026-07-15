#!/usr/bin/env python3
from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

from csrm_visual_system import (
    PALETTE,
    add_panel_label,
    clean_axes,
    export_figure,
    make_figure,
    read_tsv,
    require_columns,
    source_row,
    write_source_map,
)


FIGURE = "Figure_6"
STEM = "Figure_6_boundary_branch"


def minmax(values: np.ndarray, vmin: float | None = None, vmax: float | None = None) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    lo = float(np.nanmin(arr) if vmin is None else vmin)
    hi = float(np.nanmax(arr) if vmax is None else vmax)
    if hi <= lo:
        hi = lo + 1.0
    return lo, hi


def add_segmented_scale(ax, cmap, vmin: float, vmax: float, x: float = 1.02, y: float = 0.08, h: float = 0.80, label_fmt: str = "{:.1f}") -> None:
    n = 22
    for i, frac in enumerate(np.linspace(0, 1, n)):
        yy = y + h * i / n
        ax.add_patch(
            Rectangle((x, yy), 0.025, h / n + 0.002, transform=ax.transAxes, facecolor=cmap(frac), edgecolor="none", clip_on=False)
        )
    ax.add_patch(Rectangle((x, y), 0.025, h, transform=ax.transAxes, facecolor="none", edgecolor=PALETTE["ink"], linewidth=0.4, clip_on=False))
    ax.text(x + 0.04, y, label_fmt.format(vmin), transform=ax.transAxes, fontsize=5.5, ha="left", va="center", color=PALETTE["ink"])
    ax.text(x + 0.04, y + h, label_fmt.format(vmax), transform=ax.transAxes, fontsize=5.5, ha="left", va="center", color=PALETTE["ink"])


def scatter_panel(ax, df: pd.DataFrame, value_col: str, title: str, cmap, label: str) -> None:
    vmin = float(df.get("color_scale_vmin_2pct", pd.Series([df[value_col].min()])).iloc[0])
    vmax = float(df.get("color_scale_vmax_98pct", pd.Series([df[value_col].max()])).iloc[0])
    vmin, vmax = minmax(df[value_col].to_numpy(float), vmin, vmax)
    vals = np.clip((df[value_col].to_numpy(float) - vmin) / (vmax - vmin), 0, 1)
    ax.scatter(df["embedding_1"], df["embedding_2"], c=[cmap(v) for v in vals], s=3.2, linewidths=0, alpha=0.82)
    add_panel_label(ax, label, x=-0.12, y=1.08)
    ax.set_title(title, loc="left", fontsize=8.0, fontweight="normal", color=PALETTE["ink"])
    ax.set_xlabel("Embedding 1", fontsize=7.0)
    ax.set_ylabel("Embedding 2", fontsize=7.0)
    ax.set_xticks([])
    ax.set_yticks([])
    clean_axes(ax, grid=False)
    add_segmented_scale(ax, cmap, vmin, vmax)


def box_strip(ax, df: pd.DataFrame, value_col: str, title: str, label: str) -> None:
    order = ["other tumor cells", "top tumor-like quartile"]
    colors = ["#58B9B4", "#E1B84B"]
    rng = np.random.default_rng(20260715)
    data = [df.loc[df["tumor_like_quartile"].eq(group), value_col].dropna().to_numpy(float) for group in order]
    for i, (vals, color) in enumerate(zip(data, colors), start=1):
        show = vals
        if len(show) > 650:
            show = rng.choice(show, size=650, replace=False)
        ax.scatter(rng.normal(i, 0.045, len(show)), show, s=3.2, color=color, alpha=0.35, linewidths=0)
    ax.boxplot(
        data,
        positions=[1, 2],
        widths=0.48,
        patch_artist=True,
        showfliers=False,
        boxprops={"facecolor": "#D7EEE9", "edgecolor": "#5F6673", "linewidth": 0.7},
        medianprops={"color": PALETTE["ink"], "linewidth": 1.0},
        whiskerprops={"color": PALETTE["ink"], "linewidth": 0.75},
        capprops={"color": PALETTE["ink"], "linewidth": 0.75},
    )
    means = [float(np.nanmean(vals)) for vals in data]
    ax.scatter([1, 2], means, marker="D", s=18, color="black", zorder=5)
    add_panel_label(ax, label, x=-0.13, y=1.06)
    ax.set_title(title, loc="left", fontsize=8.0, fontweight="normal", color=PALETTE["ink"])
    ax.set_xticks([1, 2], ["other tumor cells", "top tumor-like"], fontsize=6.2)
    ax.set_ylabel(value_col.replace("_", " ").replace("score", "score").capitalize(), fontsize=7.0)
    clean_axes(ax, grid=False)


def boundary_panel(ax, boundary: pd.DataFrame) -> None:
    boundary = boundary.copy()
    boundary["score"] = pd.to_numeric(boundary["score"], errors="coerce")
    score_order = ["embryonic_like_score", "inflammatory_regeneration_score", "inflammatory_repair_score"]
    score_order = [s for s in score_order if s in set(boundary["boundary_score"])]
    group_order = ["other tumor cells", "top tumor-like"]
    data = []
    positions = []
    colors = []
    pos = 1
    for score_name in score_order:
        for group in group_order:
            vals = boundary[(boundary["boundary_score"].eq(score_name)) & (boundary["tumor_like_group"].eq(group))]["score"].dropna().to_numpy(float)
            if len(vals):
                data.append(vals)
                positions.append(pos)
                colors.append("#F2D69B" if "other" in group else "#B9DED7")
                pos += 1
        pos += 0.55
    bp = ax.boxplot(data, positions=positions, widths=0.52, patch_artist=True, showfliers=False)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_edgecolor(PALETTE["ink"])
        patch.set_linewidth(0.75)
    for key in ["medians", "whiskers", "caps"]:
        for item in bp[key]:
            item.set_color(PALETTE["ink"])
            item.set_linewidth(0.75)
    ax.axhline(0, color=PALETTE["grid"], lw=0.6)
    add_panel_label(ax, "g", x=-0.12, y=1.05)
    ax.set_title("Boundary score comparison", loc="left", fontsize=8.0, fontweight="normal", color=PALETTE["ink"])
    ax.set_ylabel("Boundary score", fontsize=7.0)
    ax.set_xticks([1.5, 4.05], ["Embryonic-like", "Inflammatory repair"], fontsize=6.4)
    if {"cohen_d_top_vs_other_embryonic_like", "q_top_vs_other_embryonic_like", "cohen_d_top_vs_other_inflammatory_repair", "q_top_vs_other_inflammatory_repair"} <= set(boundary.columns):
        row = boundary.iloc[0]
        txt = (
            f"embryonic-like score: d={float(row['cohen_d_top_vs_other_embryonic_like']):.2f}, "
            f"q={float(row['q_top_vs_other_embryonic_like']):.3f}\n"
            f"inflammatory repair score: d={float(row['cohen_d_top_vs_other_inflammatory_repair']):.2f}, "
            f"q={float(row['q_top_vs_other_inflammatory_repair']):.3f}"
        )
        ax.text(0.08, 0.84, txt, transform=ax.transAxes, fontsize=5.3, ha="left", va="top", color=PALETTE["ink"])
    clean_axes(ax, grid=False)


def heatmap_panel(ax, module: pd.DataFrame) -> None:
    order = ["other tumor cells", "top tumor-like quartile"]
    features = [
        "tumor_plasticity_proxy_score",
        "stemness_score",
        "differentiation_score",
        "embryonic_like_score",
        "inflammatory_regeneration_score",
        "local_self_retention",
    ]
    values = module.set_index("tumor_like_quartile").loc[order, features].to_numpy(float)
    cmap = LinearSegmentedColormap.from_list("old_fig6_heat", ["#08306B", "#4393C3", "#F7F7F7", "#D6604D", "#8E0038"])
    vmin, vmax = minmax(values)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            frac = (values[i, j] - vmin) / (vmax - vmin)
            ax.add_patch(Rectangle((j, values.shape[0] - 1 - i), 1, 1, facecolor=cmap(frac), edgecolor="white", linewidth=0.5))
    add_panel_label(ax, "h", x=-0.12, y=1.06)
    ax.set_title("Module mean heatmap", loc="left", fontsize=8.0, fontweight="normal", color=PALETTE["ink"])
    ax.set_xlim(0, len(features))
    ax.set_ylim(0, len(order))
    ax.set_xticks(np.arange(len(features)) + 0.5)
    ax.set_xticklabels([f.replace("_score", "").replace("_", " ") for f in features], fontsize=5.8, rotation=32, ha="right")
    ax.set_yticks(np.arange(len(order)) + 0.5)
    ax.set_yticklabels(["top tumor-like", "other tumor cells"], fontsize=6.5)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    add_segmented_scale(ax, cmap, vmin, vmax, x=1.02, y=0.02, h=0.92)


def build() -> dict[str, str]:
    panel_a = read_tsv("Figure_6/Figure_7_panel_a_source_data.tsv")
    panel_b = read_tsv("Figure_6/Figure_7_panel_b_source_data.tsv")
    panel_c = read_tsv("Figure_6/Figure_7_panel_c_source_data.tsv")
    panel_d = read_tsv("Figure_6/Figure_7_panel_d_source_data.tsv")
    panel_e = read_tsv("Figure_6/Figure_7_panel_e_source_data.tsv")
    panel_f = read_tsv("Figure_6/Figure_7_panel_f_source_data.tsv")
    panel_g = read_tsv("Figure_6/Figure_7_panel_g_source_data_v5.tsv")
    panel_h = read_tsv("Figure_6/Figure_7_panel_h_source_data.tsv")

    require_columns(panel_a, ["embedding_1", "embedding_2", "tumor_plasticity_proxy_score"], "Figure_6/Figure_7_panel_a_source_data.tsv")
    require_columns(panel_b, ["embedding_1", "embedding_2", "stemness_score"], "Figure_6/Figure_7_panel_b_source_data.tsv")
    require_columns(panel_c, ["embedding_1", "embedding_2", "differentiation_score"], "Figure_6/Figure_7_panel_c_source_data.tsv")
    require_columns(panel_d, ["embedding_1", "embedding_2", "local_self_retention"], "Figure_6/Figure_7_panel_d_source_data.tsv")
    require_columns(panel_e, ["tumor_like_quartile", "stemness_score"], "Figure_6/Figure_7_panel_e_source_data.tsv")
    require_columns(panel_f, ["tumor_like_quartile", "differentiation_score"], "Figure_6/Figure_7_panel_f_source_data.tsv")
    require_columns(panel_g, ["tumor_like_group", "boundary_score", "score"], "Figure_6/Figure_7_panel_g_source_data_v5.tsv")
    require_columns(panel_h, ["tumor_like_quartile", "tumor_plasticity_proxy_score", "stemness_score", "differentiation_score", "embryonic_like_score", "inflammatory_regeneration_score", "local_self_retention"], "Figure_6/Figure_7_panel_h_source_data.tsv")

    fig = make_figure(210, width_mm=160)

    scatter_panel(fig.add_axes([0.08, 0.75, 0.34, 0.18]), panel_a, "tumor_plasticity_proxy_score", "Tumor-like plasticity proxy", colormaps["RdPu"], "a")
    scatter_panel(fig.add_axes([0.58, 0.75, 0.34, 0.18]), panel_b, "stemness_score", "Stemness score", colormaps["YlOrBr"], "b")
    scatter_panel(fig.add_axes([0.08, 0.53, 0.34, 0.18]), panel_c, "differentiation_score", "Differentiation score", colormaps["Greys"], "c")
    scatter_panel(fig.add_axes([0.58, 0.53, 0.34, 0.18]), panel_d, "local_self_retention", "local retention", colormaps["viridis"], "d")
    box_strip(fig.add_axes([0.08, 0.31, 0.34, 0.15]), panel_e, "stemness_score", "Stemness score by tumor-like quartile", "e")
    box_strip(fig.add_axes([0.58, 0.31, 0.34, 0.15]), panel_f, "differentiation_score", "Differentiation score by tumor-like quartile", "f")
    boundary_panel(fig.add_axes([0.08, 0.08, 0.34, 0.15]), panel_g)
    heatmap_panel(fig.add_axes([0.58, 0.08, 0.32, 0.15]), panel_h)

    outputs = export_figure(fig, STEM)
    write_source_map(
        FIGURE,
        [
            source_row("a", "Figure_6/Figure_7_panel_a_source_data.tsv", ["embedding_1", "embedding_2", "tumor_plasticity_proxy_score"], len(panel_a), "none", "embedding scatter colored by supplied tumor-like proxy"),
            source_row("b", "Figure_6/Figure_7_panel_b_source_data.tsv", ["embedding_1", "embedding_2", "stemness_score"], len(panel_b), "none", "embedding scatter colored by supplied stemness score"),
            source_row("c", "Figure_6/Figure_7_panel_c_source_data.tsv", ["embedding_1", "embedding_2", "differentiation_score"], len(panel_c), "none", "embedding scatter colored by supplied differentiation score"),
            source_row("d", "Figure_6/Figure_7_panel_d_source_data.tsv", ["embedding_1", "embedding_2", "local_self_retention"], len(panel_d), "none", "embedding scatter colored by supplied local retention"),
            source_row("e", "Figure_6/Figure_7_panel_e_source_data.tsv", ["tumor_like_quartile", "stemness_score"], len(panel_e), "grouped display", "box and strip plot; no new hypothesis tests"),
            source_row("f", "Figure_6/Figure_7_panel_f_source_data.tsv", ["tumor_like_quartile", "differentiation_score"], len(panel_f), "grouped display", "box and strip plot; no new hypothesis tests"),
            source_row("g", "Figure_6/Figure_7_panel_g_source_data_v5.tsv", ["tumor_like_group", "boundary_score", "score"], len(panel_g), "grouped display", "boxplot from supplied boundary-score rows"),
            source_row("h", "Figure_6/Figure_7_panel_h_source_data.tsv", ["tumor_like_quartile", "tumor_plasticity_proxy_score", "stemness_score", "differentiation_score", "embryonic_like_score", "inflammatory_regeneration_score", "local_self_retention"], len(panel_h), "none", "module mean heatmap from supplied values"),
        ],
    )
    return outputs


if __name__ == "__main__":
    build()
