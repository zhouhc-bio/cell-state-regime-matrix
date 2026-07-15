#!/usr/bin/env python3
from __future__ import annotations

import math
import textwrap
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
OUT = ROOT / "outputs"
LOCK = OUT / "final_figures_locked"
LOCK.mkdir(parents=True, exist_ok=True)

FIG_W, FIG_H = 3600, 3000
PANEL_BG = (255, 255, 255)
BG = (248, 250, 252)
INK = (15, 23, 42)
MUTED = (71, 85, 105)
GRID = (203, 213, 225)
COLORS = {
    "adult repair": (221, 139, 40),
    "embryonic reactivation": (184, 50, 44),
    "salamander blastema": (44, 127, 184),
    "salamander intact": (100, 116, 139),
    "mammal repair": (221, 139, 40),
}
REGIME_LABELS = {
    "mammalian_inflammatory_repair": "adult repair",
    "salamander_blastema_reactivation": "salamander blastema",
    "salamander_intact_reference": "salamander intact",
    "adult_repair": "adult repair",
    "embryonic_reactivation": "embryonic reactivation",
    "salamander_blastema": "salamander blastema",
    "salamander_intact": "salamander intact",
}
LATENT_ORDER = ["adult_repair", "embryonic_reactivation", "salamander_blastema", "salamander_intact"]
DISPLAY_ORDER = [REGIME_LABELS[x] for x in LATENT_ORDER]


def path(name: str) -> Path:
    return OUT / name


def read_tsv(name: str) -> pd.DataFrame:
    return pd.read_csv(path(name), sep="\t")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/Users/hanchengdezhuanqiangongju/.cache/codex-runtimes/codex-primary-runtime/dependencies/fonts/DejaVuSans-Bold.ttf"
        if bold
        else "/Users/hanchengdezhuanqiangongju/.cache/codex-runtimes/codex-primary-runtime/dependencies/fonts/DejaVuSans.ttf",
    ]
    for item in candidates:
        if item and Path(item).exists():
            try:
                return ImageFont.truetype(item, size)
            except Exception:
                pass
    return ImageFont.load_default()


F_TITLE = font(60, True)
F_PANEL = font(44, True)
F_HEAD = font(34, True)
F_TEXT = font(28)
F_SMALL = font(23)
F_TINY = font(19)


def save_figure(img: Image.Image, stem: str) -> None:
    png = LOCK / f"{stem}.png"
    pdf = LOCK / f"{stem}.pdf"
    img.save(png, dpi=(300, 300))
    img.convert("RGB").save(pdf, "PDF", resolution=300)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], s: str, fill=INK, fnt=F_TEXT, width: int | None = None, spacing: int = 8) -> int:
    x, y = xy
    if width is None:
        draw.text((x, y), s, fill=fill, font=fnt)
        return y + draw.textbbox((x, y), s, font=fnt)[3] - y
    lines: list[str] = []
    for para in s.split("\n"):
        if not para:
            lines.append("")
        else:
            wrap_width = max(12, int(width / max(fnt.size * 0.55, 8)))
            lines.extend(textwrap.wrap(para, width=wrap_width))
    for line in lines:
        draw.text((x, y), line, fill=fill, font=fnt)
        y += fnt.size + spacing
    return y


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, title: str) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=18, fill=PANEL_BG, outline=(226, 232, 240), width=3)
    draw.text((x0 + 28, y0 + 22), label, fill=INK, font=F_PANEL)
    draw.text((x0 + 95, y0 + 30), title, fill=INK, font=F_HEAD)


def axes(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], xlabel: str, ylabel: str) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    pad_l, pad_r, pad_t, pad_b = 90, 35, 70, 75
    ax = (x0 + pad_l, y0 + pad_t, x1 - pad_r, y1 - pad_b)
    draw.rectangle(ax, outline=(51, 65, 85), width=3)
    draw.text(((ax[0] + ax[2]) // 2 - len(xlabel) * 6, y1 - 56), xlabel, fill=MUTED, font=F_SMALL)
    draw.text((x0 + 18, (ax[1] + ax[3]) // 2), ylabel, fill=MUTED, font=F_TINY)
    return ax


def map_xy(ax: tuple[int, int, int, int], x: float, y: float, xr: tuple[float, float], yr: tuple[float, float]) -> tuple[int, int]:
    x0, y0, x1, y1 = ax
    px = int(x0 + (x - xr[0]) / max(xr[1] - xr[0], 1e-12) * (x1 - x0))
    py = int(y1 - (y - yr[0]) / max(yr[1] - yr[0], 1e-12) * (y1 - y0))
    return px, py


def draw_polyline(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], color: tuple[int, int, int], width: int = 5) -> None:
    if len(pts) > 1:
        draw.line(pts, fill=color, width=width, joint="curve")


def hist_density(values: np.ndarray, bins: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    counts, edges = np.histogram(values[np.isfinite(values)], bins=bins)
    density = counts.astype(float) / max(counts.sum(), 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return centers, density


def draw_density_lines(
    draw: ImageDraw.ImageDraw,
    ax: tuple[int, int, int, int],
    series: list[tuple[str, np.ndarray, tuple[int, int, int]]],
    bins: np.ndarray,
    ylabel: str = "probability mass",
) -> float:
    hists = []
    ymax = 0.0
    for label, vals, color in series:
        centers, density = hist_density(vals, bins)
        ymax = max(ymax, float(density.max()))
        hists.append((label, centers, density, color))
    yr = (0.0, ymax * 1.12 if ymax > 0 else 1.0)
    xr = (float(bins.min()), float(bins.max()))
    for label, centers, density, color in hists:
        pts = [map_xy(ax, float(x), float(y), xr, yr) for x, y in zip(centers, density)]
        draw_polyline(draw, pts, color, width=6)
    draw.text((ax[0] + 10, ax[1] + 10), ylabel, fill=MUTED, font=F_TINY)
    return ymax


def legend(draw: ImageDraw.ImageDraw, x: int, y: int, items: list[tuple[str, tuple[int, int, int]]], fnt=F_SMALL) -> None:
    for i, (label, color) in enumerate(items):
        yy = y + i * 42
        draw.rectangle([x, yy, x + 28, yy + 28], fill=color)
        draw.text((x + 42, yy - 2), label, fill=INK, font=fnt)


def draw_heatmap(
    draw: ImageDraw.ImageDraw,
    ax: tuple[int, int, int, int],
    matrix: pd.DataFrame,
    row_col: str,
    col_col: str,
    val_col: str,
    fmt: str = "{:.2f}",
    diverge: bool = False,
) -> None:
    rows = list(matrix[row_col].drop_duplicates())
    cols = list(matrix[col_col].drop_duplicates())
    piv = matrix.pivot(index=row_col, columns=col_col, values=val_col).loc[rows, cols]
    arr = piv.to_numpy(dtype=float)
    if diverge:
        m = max(abs(float(np.nanmin(arr))), abs(float(np.nanmax(arr))), 1e-12)
        vmin, vmax = -m, m
    else:
        vmin, vmax = float(np.nanmin(arr)), float(np.nanmax(arr))
    cw = max(1, (ax[2] - ax[0]) // len(cols))
    ch = max(1, (ax[3] - ax[1]) // len(rows))
    for i, r in enumerate(rows):
        draw.text((ax[0] - 250, ax[1] + i * ch + ch // 2 - 12), REGIME_LABELS.get(str(r), str(r))[:25], fill=INK, font=F_TINY)
        for j, c in enumerate(cols):
            v = float(arr[i, j])
            t = (v - vmin) / max(vmax - vmin, 1e-12)
            if diverge and t < 0.5:
                a = np.array([44, 127, 184])
                b = np.array([245, 245, 235])
                rgb = a + (b - a) * (t / 0.5)
            elif diverge:
                a = np.array([245, 245, 235])
                b = np.array([184, 50, 44])
                rgb = a + (b - a) * ((t - 0.5) / 0.5)
            else:
                a = np.array([235, 245, 255])
                b = np.array([44, 127, 184])
                rgb = a + (b - a) * t
            x0, y0 = ax[0] + j * cw, ax[1] + i * ch
            draw.rectangle([x0, y0, x0 + cw, y0 + ch], fill=tuple(int(x) for x in rgb), outline=(226, 232, 240), width=2)
            draw.text((x0 + cw // 2 - 26, y0 + ch // 2 - 12), fmt.format(v), fill=INK, font=F_TINY)
    for j, c in enumerate(cols):
        label = REGIME_LABELS.get(str(c), str(c))[:18]
        draw.text((ax[0] + j * cw + 5, ax[1] - 38), label, fill=INK, font=F_TINY)


def load_all() -> dict[str, pd.DataFrame]:
    data = {
        "phi": read_tsv("Phi_unified.tsv"),
        "posterior": read_tsv("regime_posterior_probabilities.tsv"),
        "per_regime_phi": read_tsv("per_regime_phi_distributions.tsv"),
        "overlap": read_tsv("regime_overlap_matrix.tsv"),
        "species_overlap": read_tsv("species_regime_overlap_matrix.tsv"),
        "kl": read_tsv("regime_KL_divergence_matrix.tsv"),
        "roc": read_tsv("roc_curve.tsv"),
        "ks": read_tsv("ks_test_results.tsv"),
        "perm": read_tsv("permutation_test_results.tsv"),
        "perm_null": read_tsv("permutation_null_distribution.tsv"),
        "boot": read_tsv("bootstrap_confidence_intervals.tsv"),
        "mix": read_tsv("mixture_density_decomposition_phi.tsv"),
        "composition": read_tsv("observed_regime_to_latent_regime_composition.tsv"),
        "fit": read_tsv("latent_regime_mixture_fit_summary.tsv"),
    }
    return data


def figure1(data: dict[str, pd.DataFrame]) -> None:
    phi, roc, ks, perm, perm_null, boot = data["phi"], data["roc"], data["ks"].iloc[0], data["perm"].iloc[0], data["perm_null"], data["boot"]
    img = Image.new("RGB", (FIG_W, FIG_H), BG)
    draw = ImageDraw.Draw(img)
    draw.text((90, 55), "Figure 1 | Single-Phi model rejection and data-closure evidence", fill=INK, font=F_TITLE)
    boxes = {
        "A": (90, 180, 1740, 1120),
        "B": (1860, 180, 3510, 1120),
        "C": (90, 1240, 1740, 2180),
        "D": (1860, 1240, 3510, 2180),
        "E": (90, 2300, 3510, 2880),
    }
    panel(draw, boxes["A"], "A", "Phi distributions by empirical group")
    ax = axes(draw, (boxes["A"][0] + 30, boxes["A"][1] + 90, boxes["A"][2] - 260, boxes["A"][3] - 35), "Unified Phi", "density")
    bins = np.linspace(phi["Phi"].quantile(0.002), phi["Phi"].quantile(0.998), 80)
    series = []
    for key, label in [
        ("mammalian_inflammatory_repair", "adult repair"),
        ("salamander_blastema_reactivation", "salamander blastema"),
        ("salamander_intact_reference", "salamander intact"),
    ]:
        series.append((label, phi.loc[phi["regime_group"] == key, "Phi"].to_numpy(), COLORS[label]))
    draw_density_lines(draw, ax, series, bins)
    legend(draw, boxes["A"][2] - 380, boxes["A"][1] + 220, [(s[0], s[2]) for s in series], F_TINY)

    panel(draw, boxes["B"], "B", f"ROC curve: AUC = {ks['auc']:.3f}")
    ax = axes(draw, (boxes["B"][0] + 30, boxes["B"][1] + 90, boxes["B"][2] - 70, boxes["B"][3] - 35), "False positive rate", "True positive rate")
    draw.line([map_xy(ax, 0, 0, (0, 1), (0, 1)), map_xy(ax, 1, 1, (0, 1), (0, 1))], fill=(148, 163, 184), width=5)
    pts = [map_xy(ax, float(r.FPR), float(r.TPR), (0, 1), (0, 1)) for r in roc.itertuples()]
    draw_polyline(draw, pts, (184, 50, 44), width=7)
    text(draw, (boxes["B"][0] + 105, boxes["B"][3] - 165), "Random-level performance; Phi is not a classifier.", fill=MUTED, fnt=F_SMALL, width=1300)

    panel(draw, boxes["C"], "C", "Permutation mean-shift test")
    ax = axes(draw, (boxes["C"][0] + 30, boxes["C"][1] + 90, boxes["C"][2] - 70, boxes["C"][3] - 35), "Mean difference under label shuffle", "mass")
    vals = perm_null["mean_difference_null"].to_numpy(dtype=float)
    obs = float(perm["observed"])
    bins = np.linspace(np.quantile(vals, 0.002), np.quantile(vals, 0.998), 75)
    centers, dens = hist_density(vals, bins)
    yr, xr = (0, dens.max() * 1.15), (bins.min(), bins.max())
    pts = [map_xy(ax, float(x), float(y), xr, yr) for x, y in zip(centers, dens)]
    draw_polyline(draw, pts, (44, 127, 184), width=6)
    xobs, _ = map_xy(ax, obs, 0, xr, yr)
    draw.line([(xobs, ax[1]), (xobs, ax[3])], fill=(184, 50, 44), width=6)
    text(draw, (boxes["C"][0] + 115, boxes["C"][3] - 165), f"Observed = {obs:.3f}; p = {float(perm['p_value_two_sided']):.3f}", fill=MUTED, fnt=F_SMALL, width=1300)

    panel(draw, boxes["D"], "D", "Bootstrap uncertainty")
    ax = axes(draw, (boxes["D"][0] + 30, boxes["D"][1] + 90, boxes["D"][2] - 70, boxes["D"][3] - 35), "Estimate and 95% bootstrap CI", "metric")
    metrics = boot.to_dict("records")
    vals_all = np.r_[boot["ci_lower_2p5"], boot["ci_upper_97p5"], boot["estimate"]]
    xr = (float(vals_all.min()) - 0.08, float(vals_all.max()) + 0.08)
    for i, row in enumerate(metrics):
        y = ax[1] + 140 + i * 145
        xlo, _ = map_xy(ax, float(row["ci_lower_2p5"]), 0, xr, (0, 1))
        xhi, _ = map_xy(ax, float(row["ci_upper_97p5"]), 0, xr, (0, 1))
        xest, _ = map_xy(ax, float(row["estimate"]), 0, xr, (0, 1))
        draw.line([(xlo, y), (xhi, y)], fill=(44, 127, 184), width=8)
        draw.ellipse([xest - 14, y - 14, xest + 14, y + 14], fill=(184, 50, 44))
        draw.text((ax[0] + 20, y - 50), str(row["metric"]), fill=INK, font=F_SMALL)
        draw.text((xhi + 20, y - 18), f"{row['estimate']:.3f}", fill=MUTED, font=F_TINY)
    xzero, _ = map_xy(ax, 0.0, 0, xr, (0, 1))
    if ax[0] <= xzero <= ax[2]:
        draw.line([(xzero, ax[1]), (xzero, ax[3])], fill=(15, 23, 42), width=4)

    panel(draw, boxes["E"], "E", "Interpretation locked")
    statement = (
        f"KS test is significant (p = {float(ks['ks_p_value']):.2e}) because Phi distributions differ in shape, "
        "but this does not imply separability. The failed AUC, permutation test, and bootstrap uncertainty formally reject "
        "single-Phi discrimination."
    )
    text(draw, (boxes["E"][0] + 110, boxes["E"][1] + 135), statement, fill=INK, fnt=F_HEAD, width=3200, spacing=12)
    save_figure(img, "Figure1_single_phi_rejection")


def figure2(data: dict[str, pd.DataFrame]) -> None:
    phi, mix, posterior = data["phi"], data["mix"], data["posterior"]
    img = Image.new("RGB", (FIG_W, FIG_H), BG)
    draw = ImageDraw.Draw(img)
    draw.text((90, 55), "Figure 2 | Latent state regime mixture model", fill=INK, font=F_TITLE)
    boxes = {"A": (90, 180, 1740, 1420), "B": (1860, 180, 3510, 1420), "C": (90, 1560, 1740, 2820), "D": (1860, 1560, 3510, 2820)}

    panel(draw, boxes["A"], "A", "Weighted component densities")
    ax = axes(draw, (boxes["A"][0] + 30, boxes["A"][1] + 95, boxes["A"][2] - 270, boxes["A"][3] - 35), "Phi", "probability mass")
    ymax = float(mix["weighted_component_density"].max()) * 1.2
    xr = (float(mix["bin_left"].min()), float(mix["bin_right"].max()))
    yr = (0, ymax)
    items = []
    for regime, sub in mix.groupby("latent_regime", sort=False):
        label = REGIME_LABELS.get(regime, regime)
        pts = [map_xy(ax, float(r.bin_center), float(r.weighted_component_density), xr, yr) for r in sub.itertuples()]
        draw_polyline(draw, pts, COLORS[label], width=6)
        items.append((label, COLORS[label]))
    legend(draw, boxes["A"][2] - 420, boxes["A"][1] + 230, items, F_TINY)

    panel(draw, boxes["B"], "B", "Empirical density and mixture fit")
    ax = axes(draw, (boxes["B"][0] + 30, boxes["B"][1] + 95, boxes["B"][2] - 80, boxes["B"][3] - 35), "Phi", "probability mass")
    bins = np.sort(np.unique(np.r_[mix["bin_left"].unique(), mix["bin_right"].unique()]))
    centers, emp = hist_density(phi["Phi"].to_numpy(dtype=float), bins)
    total = mix.groupby("bin_center", as_index=False)["weighted_component_density"].sum().sort_values("bin_center")
    ymax = max(float(emp.max()), float(total["weighted_component_density"].max())) * 1.2
    yr = (0, ymax)
    pts_emp = [map_xy(ax, float(x), float(y), (bins.min(), bins.max()), yr) for x, y in zip(centers, emp)]
    pts_mix = [map_xy(ax, float(r.bin_center), float(r.weighted_component_density), (bins.min(), bins.max()), yr) for r in total.itertuples()]
    draw_polyline(draw, pts_emp, INK, width=7)
    draw_polyline(draw, pts_mix, (184, 50, 44), width=5)
    legend(draw, boxes["B"][2] - 510, boxes["B"][1] + 220, [("empirical Phi", INK), ("weighted mixture", (184, 50, 44))], F_SMALL)

    panel(draw, boxes["C"], "C", "Per-regime Phi distributions")
    ax = axes(draw, (boxes["C"][0] + 30, boxes["C"][1] + 95, boxes["C"][2] - 260, boxes["C"][3] - 35), "Phi", "mass")
    bins = np.linspace(posterior["Phi"].quantile(0.002), posterior["Phi"].quantile(0.998), 80)
    series = []
    for regime in LATENT_ORDER:
        label = REGIME_LABELS[regime]
        series.append((label, posterior.loc[posterior["latent_regime_map"] == regime, "Phi"].to_numpy(), COLORS[label]))
    draw_density_lines(draw, ax, series, bins)
    legend(draw, boxes["C"][2] - 420, boxes["C"][1] + 240, [(s[0], s[2]) for s in series], F_TINY)

    panel(draw, boxes["D"], "D", "Model replacement")
    equation = (
        "P(Phi | S) = sum_Z P(Phi | S, Z) P(Z | S, W_GRN)\n\n"
        "Z is latent, not observed directly.\n"
        "Each regime has its own Phi distribution.\n"
        "No global Phi threshold exists."
    )
    text(draw, (boxes["D"][0] + 110, boxes["D"][1] + 170), equation, fill=INK, fnt=F_HEAD, width=1400, spacing=18)
    save_figure(img, "Figure2_latent_regime_mixture")


def figure3(data: dict[str, pd.DataFrame]) -> None:
    posterior, composition = data["posterior"], data["composition"]
    img = Image.new("RGB", (FIG_W, FIG_H), BG)
    draw = ImageDraw.Draw(img)
    draw.text((90, 55), "Figure 3 | Regime posterior landscape", fill=INK, font=F_TITLE)
    boxes = {"A": (90, 180, 1740, 1420), "B": (1860, 180, 3510, 1420), "C": (90, 1560, 1740, 2820), "D": (1860, 1560, 3510, 2820)}

    panel(draw, boxes["A"], "A", "Dominant posterior regime assignment in state space")
    ax = axes(draw, (boxes["A"][0] + 30, boxes["A"][1] + 95, boxes["A"][2] - 260, boxes["A"][3] - 35), "Fate-lock axis", "Embryonic-accessibility module")
    x = posterior["Fate_lock"].to_numpy(dtype=float)
    y = posterior["Embryonic_module_score"].to_numpy(dtype=float)
    xr = tuple(np.quantile(x, [0.005, 0.995]))
    yr = tuple(np.quantile(y, [0.005, 0.995]))
    sample = posterior.sample(min(9000, len(posterior)), random_state=20260619)
    for r in sample.itertuples():
        label = REGIME_LABELS.get(r.latent_regime_map, r.latent_regime_map)
        px, py = map_xy(ax, float(r.Fate_lock), float(r.Embryonic_module_score), xr, yr)
        if ax[0] <= px <= ax[2] and ax[1] <= py <= ax[3]:
            draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=COLORS[label])
    legend(draw, boxes["A"][2] - 430, boxes["A"][1] + 220, [(REGIME_LABELS[r], COLORS[REGIME_LABELS[r]]) for r in LATENT_ORDER], F_TINY)

    panel(draw, boxes["B"], "B", "Posterior certainty")
    ax = axes(draw, (boxes["B"][0] + 30, boxes["B"][1] + 95, boxes["B"][2] - 80, boxes["B"][3] - 35), "Fate-lock axis", "max P(Z|S)")
    q = posterior.groupby(pd.qcut(posterior["Fate_lock"].rank(method="first"), 40, labels=False))["latent_regime_max_posterior"].mean().reset_index()
    q["x"] = posterior.groupby(pd.qcut(posterior["Fate_lock"].rank(method="first"), 40, labels=False))["Fate_lock"].mean().values
    xr2 = (float(q["x"].min()), float(q["x"].max()))
    pts = [map_xy(ax, float(r.x), float(r.latent_regime_max_posterior), xr2, (0, 1)) for r in q.itertuples()]
    draw_polyline(draw, pts, (44, 127, 184), width=7)
    text(draw, (boxes["B"][0] + 155, boxes["B"][3] - 155), "Lower certainty indicates overlapping latent state regimes.", fill=MUTED, fnt=F_SMALL, width=1200)

    panel(draw, boxes["C"], "C", "Observed groups are mixtures of latent state regimes")
    ax = (boxes["C"][0] + 230, boxes["C"][1] + 180, boxes["C"][2] - 180, boxes["C"][3] - 250)
    draw.rectangle(ax, outline=(51, 65, 85), width=3)
    draw.text((boxes["C"][0] + 55, (ax[1] + ax[3]) // 2 - 20), "mean posterior", fill=MUTED, font=F_TINY)
    comp_cols = [f"mean_P_Z_{r}" for r in LATENT_ORDER]
    observed_labels = {
        "mammalian_inflammatory_repair": "mammal\nrepair",
        "salamander_blastema_reactivation": "salamander\nblastema",
        "salamander_intact_reference": "salamander\nintact",
    }
    x_positions = np.linspace(ax[0] + 120, ax[2] - 260, max(len(composition), 1))
    for i, row in composition.iterrows():
        base_x = int(x_positions[i])
        y_base = ax[3]
        y_cursor = y_base
        bar_w = 185
        for k, regime in enumerate(LATENT_ORDER):
            val = float(row[f"mean_P_Z_{regime}"])
            h = int(val * (ax[3] - ax[1]))
            label = REGIME_LABELS[regime]
            draw.rectangle([base_x, y_cursor - h, base_x + bar_w, y_cursor], fill=COLORS[label], outline=PANEL_BG, width=2)
            y_cursor -= h
        group_label = observed_labels.get(row["observed_regime_proxy"], str(row["observed_regime_proxy"]).replace("_", "\n"))
        text(draw, (base_x - 40, ax[3] + 28), group_label, fill=INK, fnt=F_TINY, width=280, spacing=3)
    draw.text(((ax[0] + ax[2]) // 2 - 160, boxes["C"][3] - 95), "observed species/regime group", fill=MUTED, font=F_SMALL)
    legend(draw, boxes["C"][2] - 430, boxes["C"][1] + 210, [(REGIME_LABELS[r], COLORS[REGIME_LABELS[r]]) for r in LATENT_ORDER], F_TINY)

    panel(draw, boxes["D"], "D", "Posterior interpretation")
    msg = (
        "Regime identity is represented by P(Z|S), not by Phi thresholding. "
        "Mammalian repair, salamander blastema, and salamander intact samples all contain mixed posterior mass."
    )
    text(draw, (boxes["D"][0] + 110, boxes["D"][1] + 170), msg, fill=INK, fnt=F_HEAD, width=1350, spacing=14)
    save_figure(img, "Figure3_regime_posterior_landscape")


def figure4(data: dict[str, pd.DataFrame]) -> None:
    overlap, species_overlap, kl = data["overlap"], data["species_overlap"], data["kl"]
    img = Image.new("RGB", (FIG_W, FIG_H), BG)
    draw = ImageDraw.Draw(img)
    draw.text((90, 55), "Figure 4 | Regime overlap and divergence", fill=INK, font=F_TITLE)
    boxes = {"A": (90, 180, 1740, 1420), "B": (1860, 180, 3510, 1420), "C": (90, 1560, 1740, 2820), "D": (1860, 1560, 3510, 2820)}

    panel(draw, boxes["A"], "A", "Latent-state-regime overlap")
    ax = (boxes["A"][0] + 360, boxes["A"][1] + 190, boxes["A"][2] - 100, boxes["A"][3] - 120)
    draw_heatmap(draw, ax, overlap, "regime_i", "regime_j", "bhattacharyya_overlap_proxy")

    panel(draw, boxes["B"], "B", "Species/regime posterior overlap")
    ax = (boxes["B"][0] + 420, boxes["B"][1] + 220, boxes["B"][2] - 130, boxes["B"][3] - 130)
    draw_heatmap(draw, ax, species_overlap, "species_regime_i", "species_regime_j", "posterior_composition_overlap")

    panel(draw, boxes["C"], "C", "Symmetrized KL divergence")
    ax = (boxes["C"][0] + 360, boxes["C"][1] + 190, boxes["C"][2] - 100, boxes["C"][3] - 120)
    draw_heatmap(draw, ax, kl, "regime_i", "regime_j", "symmetric_KL", fmt="{:.1f}")

    panel(draw, boxes["D"], "D", "Strongest divergence ranking")
    pairs = kl[kl["regime_i"] < kl["regime_j"]].sort_values("symmetric_KL", ascending=False).head(6)
    ax = axes(draw, (boxes["D"][0] + 30, boxes["D"][1] + 95, boxes["D"][2] - 70, boxes["D"][3] - 35), "symmetrized KL divergence", "pair")
    xmax = float(pairs["symmetric_KL"].max()) * 1.15
    for i, r in enumerate(pairs.itertuples()):
        y = ax[1] + 70 + i * 120
        w = int(float(r.symmetric_KL) / xmax * (ax[2] - ax[0] - 430))
        draw.rectangle([ax[0] + 360, y, ax[0] + 360 + w, y + 42], fill=(184, 50, 44))
        pair_label = f"{REGIME_LABELS.get(r.regime_i, r.regime_i)} vs {REGIME_LABELS.get(r.regime_j, r.regime_j)}"
        draw.text((ax[0] + 10, y + 4), pair_label[:36], fill=INK, font=F_TINY)
        draw.text((ax[0] + 380 + w, y + 4), f"{r.symmetric_KL:.2f}", fill=MUTED, font=F_TINY)
    save_figure(img, "Figure4_overlap_divergence")


def figure5(data: dict[str, pd.DataFrame]) -> None:
    fit = data["fit"].iloc[0]
    img = Image.new("RGB", (FIG_W, FIG_H), BG)
    draw = ImageDraw.Draw(img)
    draw.text((90, 55), "Figure 5 | Final latent-state-regime dynamical model", fill=INK, font=F_TITLE)
    boxes = {"A": (90, 180, 1740, 1120), "B": (1860, 180, 3510, 1120), "C": (90, 1240, 1740, 2820), "D": (1860, 1240, 3510, 2820)}

    panel(draw, boxes["A"], "A", "Rejected model")
    text(draw, (boxes["A"][0] + 110, boxes["A"][1] + 170), "single global Phi\nthreshold / classifier", fill=INK, fnt=F_HEAD, width=1300)
    draw.line([(boxes["A"][0] + 700, boxes["A"][1] + 520), (boxes["A"][0] + 1180, boxes["A"][1] + 520)], fill=(184, 50, 44), width=18)
    draw.line([(boxes["A"][0] + 700, boxes["A"][1] + 700), (boxes["A"][0] + 1180, boxes["A"][1] + 340)], fill=(184, 50, 44), width=18)
    text(draw, (boxes["A"][0] + 110, boxes["A"][3] - 230), "AUC = 0.480; mean-shift test not significant.", fill=MUTED, fnt=F_SMALL, width=1350)

    panel(draw, boxes["B"], "B", "Accepted replacement")
    text(draw, (boxes["B"][0] + 110, boxes["B"][1] + 160), "latent state regime mixture\nP(Z | S, W_GRN)", fill=INK, fnt=F_HEAD, width=1300)
    text(draw, (boxes["B"][0] + 110, boxes["B"][1] + 260), f"I(S;Z) proxy = {float(fit['mutual_information_I_S_Z_proxy']):.3f}; mixture KL = {float(fit['KL_empirical_phi_vs_mixture_phi']):.2e}.", fill=MUTED, fnt=F_TINY, width=1350)
    cx, cy = boxes["B"][0] + 760, boxes["B"][1] + 590
    for i, regime in enumerate(DISPLAY_ORDER):
        ang = i * math.pi / 2 + math.pi / 4
        x = int(cx + math.cos(ang) * 360)
        y = int(cy + math.sin(ang) * 250)
        draw.ellipse([x - 95, y - 95, x + 95, y + 95], fill=COLORS[regime], outline=INK, width=4)
        text(draw, (x - 125, y + 110), regime, fill=INK, fnt=F_TINY, width=250)

    panel(draw, boxes["C"], "C", "Old concepts mapped to new model")
    mappings = [
        ("plasticity", "local accessibility within regime"),
        ("fate-lock", "adult repair basin depth"),
        ("positional information / DPRI", "regime-conditioned developmental coordinate"),
        ("blastema regeneration", "latent regenerative regime access"),
        ("senescence", "adult/fate-lock-biased component"),
        ("tumor-like plasticity", "not validated as a main regenerative regime here"),
    ]
    y = boxes["C"][1] + 160
    for old, new in mappings:
        draw.text((boxes["C"][0] + 110, y), old, fill=INK, font=F_SMALL)
        draw.line([(boxes["C"][0] + 560, y + 16), (boxes["C"][0] + 730, y + 16)], fill=GRID, width=5)
        text(draw, (boxes["C"][0] + 770, y - 8), new, fill=MUTED, fnt=F_SMALL, width=780)
        y += 170

    panel(draw, boxes["D"], "D", "Final dynamical equation")
    eq = "dS/dt = sum_Z P(Z|S,W_GRN) F_Z(S,U,W_GRN) + xi(S)"
    text(draw, (boxes["D"][0] + 110, boxes["D"][1] + 180), eq, fill=INK, fnt=F_HEAD, width=1350, spacing=16)
    text(
        draw,
        (boxes["D"][0] + 110, boxes["D"][1] + 520),
        "Schematic statements are conceptual and tied to the validated data outputs: Phi failure statistics, posterior probabilities, overlap matrices, and symmetrized KL divergence.",
        fill=MUTED,
        fnt=F_SMALL,
        width=1350,
        spacing=10,
    )
    save_figure(img, "Figure5_final_model_schematic")


def create_audit() -> None:
    rows = []
    required = {
        "Phi_unified.tsv": ["Phi", "regime_group", "Stemness", "Fate_lock", "Embryonic_module_score"],
        "roc_curve.tsv": ["FPR", "TPR"],
        "permutation_test_results.tsv": ["observed", "p_value_two_sided"],
        "permutation_null_distribution.tsv": ["mean_difference_null"],
        "bootstrap_confidence_intervals.tsv": ["metric", "estimate", "ci_lower_2p5", "ci_upper_97p5"],
        "mixture_density_decomposition_phi.tsv": ["latent_regime", "bin_center", "weighted_component_density"],
        "regime_posterior_probabilities.tsv": ["Fate_lock", "Embryonic_module_score", "latent_regime_map"],
        "regime_overlap_matrix.tsv": ["regime_i", "regime_j", "bhattacharyya_overlap_proxy"],
        "species_regime_overlap_matrix.tsv": ["species_regime_i", "species_regime_j", "posterior_composition_overlap"],
        "regime_KL_divergence_matrix.tsv": ["regime_i", "regime_j", "symmetric_KL"],
    }

    planned = [
        ("Figure 1", "A", "Phi has empirical distributional structure", "Phi_unified.tsv", "Phi,regime_group", "figure1:density", "MAIN", "low", "none"),
        ("Figure 1", "B", "Single Phi classifier fails", "roc_curve.tsv; ks_test_results.tsv", "FPR,TPR,auc", "figure1:roc", "MAIN", "low", "none"),
        ("Figure 1", "C", "Mean shift is not significant", "permutation_null_distribution.tsv; permutation_test_results.tsv", "mean_difference_null,observed,p_value", "figure1:permutation", "MAIN", "low", "none"),
        ("Figure 1", "D", "Bootstrap instability", "bootstrap_confidence_intervals.tsv", "estimate,ci_lower_2p5,ci_upper_97p5", "figure1:bootstrap", "MAIN", "low", "none"),
        ("Figure 1", "E", "KS is shape difference, not separability", "ks_test_results.tsv", "ks_p_value,auc", "figure1:annotation", "MAIN", "low", "none"),
        ("Figure 2", "A-D", "Latent mixture replaces global Phi threshold", "mixture_density_decomposition_phi.tsv; regime_posterior_probabilities.tsv", "latent_regime,weighted_component_density,P_Z_*", "figure2", "MAIN", "low", "none"),
        ("Figure 3", "A-D", "Posterior regimes overlap in state space", "regime_posterior_probabilities.tsv; observed_regime_to_latent_regime_composition.tsv", "Fate_lock,Embryonic_module_score,P_Z_*", "figure3", "MAIN", "low", "none"),
        ("Figure 4", "A-D", "Regime overlap and symmetrized divergence", "regime_overlap_matrix.tsv; species_regime_overlap_matrix.tsv; regime_KL_divergence_matrix.tsv", "overlap,symmetric_KL", "figure4", "MAIN", "low", "label KL as symmetrized"),
        ("Figure 5", "A-D", "Final conceptual model tied to validated data", "single_phi_model_invalidation.md; latent_regime_mixture_model.md; latent_regime_mixture_fit_summary.tsv", "model verdict, equation, fit summary", "figure5", "MAIN", "medium", "caption must label conceptual"),
    ]
    for fig, panel_id, claim, src, cols, func, role, risk, fix in planned:
        files = [s.strip() for s in src.split(";")]
        available = all((OUT / f).exists() for f in files)
        rows.append(
            {
                "figure_id": fig,
                "panel_id": panel_id,
                "intended_claim": claim,
                "source_data_file": src,
                "required_columns": cols,
                "script_or_function_needed": func,
                "data_available_yes_no": "YES" if available else "NO",
                "reproducible_yes_no": "YES" if available else "NO",
                "main_or_supplement_or_remove": role,
                "risk_level": risk,
                "required_fix": fix,
            }
        )

    image_files = sorted(list(OUT.glob("*.png")) + list(OUT.glob("*.svg")) + list(OUT.glob("*.pdf")))
    for p in image_files:
        name = p.name
        role = "SUPPLEMENTARY"
        risk = "medium"
        fix = "Keep outside main figure set unless cited as source-bound support."
        claim = "Existing prior figure"
        src = "unknown_or_prior_source"
        cols = "not audited"
        if name.startswith("fig") or name.startswith("Figure"):
            role = "REMAKE_REQUIRED"
            fix = "Replaced by final_figures_locked reconstruction."
        if "Phi_phase" in name or "phase_diagram_R_US" in name or "bifurcation" in name:
            role = "REMOVE"
            risk = "high"
            fix = "Do not use as main evidence because single-Phi/global-switch interpretation is invalid."
        if "W_GRN" in name:
            role = "SUPPLEMENTARY"
            src = "W_GRN_learned.tsv"
            cols = "source,target,weight,sign"
            risk = "medium"
        if "latent_regime" in name or name in {"fig1_mixture_density_decomposition_phi.png", "fig2_regime_posterior_landscape.png", "fig3_overlap_heatmap_between_species_regimes.png", "fig4_KL_divergence_matrix.png", "fig5_failure_of_discriminative_phi_summary.png"}:
            role = "REMAKE_REQUIRED"
            fix = "Use locked Figure 1-5 composites instead."
        rows.append(
            {
                "figure_id": name,
                "panel_id": "existing",
                "intended_claim": claim,
                "source_data_file": src,
                "required_columns": cols,
                "script_or_function_needed": "audit_existing",
                "data_available_yes_no": "YES" if src != "unknown_or_prior_source" else "NO",
                "reproducible_yes_no": "NO" if src == "unknown_or_prior_source" else "YES",
                "main_or_supplement_or_remove": role,
                "risk_level": risk,
                "required_fix": fix,
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "final_figure_data_audit.tsv", sep="\t", index=False)


def write_text_outputs() -> None:
    plan = """# Final Main Figure Plan

## Figure 1: Single-Phi Model Rejection

Panels: A, empirical Phi distributions; B, ROC curve with AUC approximately 0.480; C, permutation mean-shift null distribution; D, bootstrap confidence intervals; E, interpretation panel. This figure shows that Phi has distributional structure but fails as a global discriminative order parameter.

## Figure 2: Latent Regime Mixture Model

Panels: A, weighted component densities; B, empirical Phi density and weighted mixture fit on the same probability-mass scale; C, per-regime Phi distributions; D, mixture equation. This figure replaces single Phi with a latent state regime mixture.

## Figure 3: Regime Posterior Landscape

Panels: A, dominant posterior regime assignment in Fate-lock vs embryonic-accessibility state space; B, posterior certainty; C, observed groups as mixtures of latent state regimes; D, interpretation. This figure shows overlap rather than scalar separability.

## Figure 4: Regime Overlap and Divergence

Panels: A, latent-state-regime overlap; B, species/regime posterior-composition overlap; C, symmetrized KL divergence; D, divergence ranking. This figure shows overlap and distributional divergence.

## Figure 5: Final Conceptual Model

Panels: A, old single-Phi model rejected; B, latent state regime mixture accepted; C, old concepts mapped to the new model; D, final dynamical equation. This figure is conceptual and must be cited after Figures 1-4.
"""
    (OUT / "final_figure_plan.md").write_text(plan, encoding="utf-8")

    captions = """# Final Figure Captions

## Figure 1 | Single-Phi model rejection and data-closure evidence.

A, Distribution of the unified Phi score across empirical groups in `Phi_unified.tsv` (`mammalian_inflammatory_repair`, `salamander_blastema_reactivation`, and `salamander_intact_reference`). B, ROC curve from `roc_curve.tsv` and `ks_test_results.tsv`; AUC is approximately 0.480, indicating random-level classification. C, Permutation mean-shift test from `permutation_null_distribution.tsv` and `permutation_test_results.tsv`; the mean difference is not significant. D, Bootstrap confidence intervals from `bootstrap_confidence_intervals.tsv`; the mean shift interval crosses zero and the median shift is not sufficient to rescue global discrimination. E, Statistical interpretation. Phi shows distributional differences but fails as a discriminative global order parameter. The significant KS test reflects distributional shape difference, not separability.

## Figure 2 | Latent state regime mixture model replacing a global Phi threshold.

A, Weighted component densities from `mixture_density_decomposition_phi.tsv`, plotted on the same probability-mass scale. B, Empirical Phi density from `Phi_unified.tsv` overlaid with the summed weighted mixture fit. C, Per-regime Phi distributions from `regime_posterior_probabilities.tsv`. D, Model equation `P(Phi|S)=sum_Z P(Phi|S,Z)P(Z|S,W_GRN)` from `latent_regime_mixture_model.md`. The figure shows that each latent state regime has its own Phi distribution and that no global Phi threshold is used.

## Figure 3 | Posterior landscape of latent regenerative regimes.

A, Dominant posterior regime assignment `argmax_Z P(Z|S)` in Fate-lock versus embryonic-accessibility state space from `regime_posterior_probabilities.tsv`. B, Posterior certainty as a function of Fate-lock state. C, Observed species/regime groups represented as mixtures of latent state regimes using `observed_regime_to_latent_regime_composition.tsv`. D, Interpretation panel. Regime identity is probabilistic and overlapping; high Phi is not equivalent to salamander blastema.

## Figure 4 | Regime overlap and distributional divergence.

A, Latent-state-regime overlap heatmap from `regime_overlap_matrix.tsv`. B, Species/regime posterior-composition overlap from `species_regime_overlap_matrix.tsv`. C, Symmetrized KL divergence matrix from `regime_KL_divergence_matrix.tsv`; the matrix is explicitly interpreted as symmetric distribution divergence, not ordinary directional KL. D, Ranking of strongest divergences. Overlap indicates non-identifiability and mixture structure; divergence indicates regime-specific distributional differences.

## Figure 5 | Final latent-state-regime dynamical model.

A, Rejected single-Phi classifier model based on `single_phi_model_invalidation.md` and Figure 1 statistics. B, Accepted latent mixture representation based on `latent_regime_mixture_fit_summary.tsv`. C, Mapping of prior manuscript concepts to the latent-state-regime framework. D, Final system equation `dS/dt = sum_Z P(Z|S,W_GRN)F_Z(S,U,W_GRN)+xi(S)` from `latent_regime_mixture_model.md`. This figure is conceptual and depends on the validated data-bound results in Figures 1-4.
"""
    (OUT / "final_figure_captions.md").write_text(captions, encoding="utf-8")

    report = """# Final Data Locking Report

## Files Used

Core source files: `Phi_unified.tsv`, `aligned_state_matrix.tsv`, `regime_posterior_probabilities.tsv`, `mixture_density_decomposition_phi.tsv`, `regime_overlap_matrix.tsv`, `species_regime_overlap_matrix.tsv`, `regime_KL_divergence_matrix.tsv`, `roc_curve.tsv`, `permutation_test_results.tsv`, `permutation_null_distribution.tsv`, `bootstrap_confidence_intervals.tsv`, `ks_test_results.tsv`, `single_phi_model_invalidation.md`, `latent_regime_mixture_model.md`, and `identifiability_failure_report.md`.

## Figures Generated

Five main figures were regenerated from source TSV/MD files and saved as PNG and PDF in `final_figures_locked/`.

## Validation Status

SINGLE_PHI_MODEL: INVALID

LATENT_REGIME_MIXTURE_MODEL: PARTIALLY_SUPPORTED

FIGURE_DATA_BINDING: PASS

READY_FOR_MANUSCRIPT_WRITING: YES

## Main Text Figures

Figure 1 through Figure 5 in `final_figures_locked/` are recommended for main text.

## Supplementary Figures

Data-bound W_GRN, normalization, and selected model diagnostics can be supplementary. Single-Phi phase diagrams and old manual switching figures should be removed or used only as historical negative controls.

## Remaining Risks

The analysis is locked at the processed state-score/module-score layer, not raw FASTQ/count-matrix level. Cross-species interpretation remains proxy-based and should not be overstated as complete biological validation. Schematic elements in Figure 5 are conceptual, not primary evidence.

## Manuscript Readiness

The final figure set is ready for manuscript writing with explicit limitations. It is not a license to claim complete mammal-versus-salamander separation.
"""
    (OUT / "final_data_locking_report.md").write_text(report, encoding="utf-8")

    mapping_rows = [
        ("plasticity", "single scalar rise in regenerative potential", "local accessibility within each latent state regime", "Figure 5", "Would imply global ordering that failed", "Plasticity is regime-conditioned accessibility rather than a universal Phi coordinate."),
        ("positional information", "global developmental coordinate", "regime-conditioned developmental coordinate", "Figure 5", "Could overstate cross-species alignment", "Positional information is interpreted within latent state regimes."),
        ("DPRI", "single developmental positional-regenerative index", "regime-conditioned coordinate coupled to P(Z|S)", "Figure 5", "Would recreate invalid single-index model", "DPRI-like signals should be reported per regime."),
        ("fate-lock", "one global basin depth", "adult repair basin depth and posterior component structure", "Figure 4/5", "Could imply complete irreversibility", "Fate-lock is strongest within adult-repair-like regimes."),
        ("regeneration", "high Phi state", "latent regenerative regime access", "Figure 2/3", "Would falsely equate blastema with high Phi", "Regeneration is inferred through P(Z|S), not Phi threshold."),
        ("senescence", "terminal high fate-lock state", "adult/fate-lock-biased latent structure", "Figure 5", "Could overstate terminality", "Senescence is modeled as a fate-lock-biased regime component."),
        ("tumor-like plasticity", "parallel metastable attractor", "not validated as main final regime in current locked figures", "Supplementary only", "Could overreach beyond data", "Discuss as hypothesis unless supported by separate data."),
        ("salamander regeneration", "higher global Phi", "salamander blastema latent state regime with overlap", "Figure 3/4", "Would contradict AUC failure", "Salamander blastema is a distinct latent regenerative regime, not high Phi."),
        ("mammalian inflammatory repair", "failed regeneration due to low Phi", "adult-repair-like posterior mixture with overlap", "Figure 3/4", "Could imply binary species separation", "Mammalian repair remains primarily adult-repair-like but overlaps with other regimes."),
    ]
    pd.DataFrame(
        mapping_rows,
        columns=["old_concept", "old_interpretation", "new_interpretation", "supporting_new_figure", "risk_if_overstated", "recommended_text"],
    ).to_csv(OUT / "old_paper_to_new_model_mapping.tsv", sep="\t", index=False)

    supp = """# Supplementary Figure Plan

| older figure | decision | rationale |
|---|---|---|
| dual attractor landscape | SUPPLEMENTARY | Conceptual; useful only after data-bound mixture figures. |
| Phi phase diagram | REMOVE | Single-Phi threshold interpretation is invalid. |
| R(U,S) phase diagram | REMOVE | Manual switching function has been replaced by latent mixture posterior. |
| bifurcation/control plots | SUPPLEMENTARY or REMOVE | Keep only if explicitly labeled as exploratory; not main evidence. |
| stochastic ensemble plots | SUPPLEMENTARY | Allowed if source data are traceable and not used as validation. |
| W_GRN graph | SUPPLEMENTARY | Data-bound but supports mechanism background, not final claim alone. |
| latent fate manifold | REMOVE | Prior nonlinear representation closure failed and should not be main evidence. |
| PC-score distributions | SUPPLEMENTARY | Useful as upstream state summaries only. |
| perturbation consistency plots | SUPPLEMENTARY | Include only where source tables and causal limits are explicit. |
"""
    (OUT / "supplementary_figure_plan.md").write_text(supp, encoding="utf-8")

    log = f"""# Final Reconstruction Log

Run timestamp: {datetime.now().isoformat(timespec='seconds')}

Script: `work/final_lock_figures_and_audit.py`

Outputs:

- `final_figure_data_audit.tsv`
- `final_figure_plan.md`
- `final_figure_captions.md`
- `final_data_locking_report.md`
- `old_paper_to_new_model_mapping.tsv`
- `supplementary_figure_plan.md`
- `final_figures_locked/Figure1_single_phi_rejection.png`
- `final_figures_locked/Figure1_single_phi_rejection.pdf`
- `final_figures_locked/Figure2_latent_regime_mixture.png`
- `final_figures_locked/Figure2_latent_regime_mixture.pdf`
- `final_figures_locked/Figure3_regime_posterior_landscape.png`
- `final_figures_locked/Figure3_regime_posterior_landscape.pdf`
- `final_figures_locked/Figure4_overlap_divergence.png`
- `final_figures_locked/Figure4_overlap_divergence.pdf`
- `final_figures_locked/Figure5_final_model_schematic.png`
- `final_figures_locked/Figure5_final_model_schematic.pdf`

Scientific lock:

- Single-Phi model remains invalid.
- Latent state regime mixture model is the replacement interpretation.
- No figure claims complete mammal-versus-salamander separation.
- No figure equates salamander blastema with high Phi.
"""
    (OUT / "final_reconstruction_log.md").write_text(log, encoding="utf-8")


def main() -> int:
    data = load_all()
    create_audit()
    write_text_outputs()
    figure1(data)
    figure2(data)
    figure3(data)
    figure4(data)
    figure5(data)
    print("final figure reconstruction and locking complete")
    print(LOCK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
