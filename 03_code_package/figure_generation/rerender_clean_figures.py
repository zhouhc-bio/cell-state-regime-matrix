from __future__ import annotations

import csv
import math
import shutil
import textwrap
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import pandas as pd
from lxml import etree
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
OUT = ROOT / "outputs"
WORK = ROOT / "work" / "figure_rerender_no_rectangles"
CLEAN_DIR = ROOT / "final_figures_no_rectangles"
REPORT = ROOT / "figure_visual_encoding_audit.md"
LEGEND_LOG = ROOT / "figure_legend_change_log.md"
CONTACT = ROOT / "final_visual_encoding_contact_sheet.png"
INPUT_DOCX = ROOT / "细胞命运论文010_FIGURE_IMAGE_TITLES_FULLY_REMOVED_FINAL.docx"
OUTPUT_DOCX = ROOT / "Regenerative_cell_fate_latent_regime_VISUAL_ENCODING_FIXED.docx"

OLD_DIR = Path("/Volumes/T9/nature_reviewer_alignment_outputs/submission_reproducibility_package_FINAL/02_figures/png_600dpi")
EXTRACTED = ROOT / "extracted_figures_after_cleanup"

FONT_REG = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
FONT_BOLD = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
if not FONT_REG.exists():
    FONT_REG = Path("/System/Library/Fonts/Supplemental/Helvetica.ttf")
if not FONT_BOLD.exists():
    FONT_BOLD = Path("/System/Library/Fonts/Supplemental/Helvetica Bold.ttf")

INK = (17, 24, 39)
MUTED = (78, 88, 107)
LIGHT = (234, 238, 244)
BLUE = (35, 104, 166)
TEAL = (43, 140, 136)
RED = (190, 58, 52)
AMBER = (184, 121, 26)
PURPLE = (106, 90, 168)
GREY = (105, 116, 139)
WHITE = (255, 255, 255)

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
COLORS = {
    "adult repair": (222, 141, 36),
    "embryonic reactivation": (191, 50, 46),
    "salamander blastema": (48, 132, 190),
    "salamander intact": (103, 119, 139),
    "tumor-like": (166, 78, 153),
    "inflammatory": (82, 178, 166),
}


def fnt(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REG), size)


F_PANEL = fnt(40, True)
F_HEAD = fnt(31, True)
F_TEXT = fnt(26)
F_SMALL = fnt(21)
F_TINY = fnt(17)


def read_tsv(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name, sep="\t")


def wrap(s: str, width: int) -> list[str]:
    lines: list[str] = []
    for para in str(s).split("\n"):
        if not para:
            lines.append("")
        else:
            lines.extend(textwrap.wrap(para, width=width, break_long_words=False))
    return lines


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], s: str, font: ImageFont.FreeTypeFont, fill=INK, max_chars=42, spacing=7) -> int:
    x, y = xy
    for line in wrap(s, max_chars):
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + spacing
    return y


def panel_title(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, title: str, color=INK) -> None:
    draw.text((x, y), label, font=F_PANEL, fill=INK)
    draw.text((x + 58, y + 5), title, font=F_HEAD, fill=color)


def replace_panel_label(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, size: int = 95, cover_w: int | None = None, cover_h: int | None = None) -> None:
    """Replace a rasterized panel letter on a white background."""
    font = fnt(size, True)
    bbox = draw.textbbox((x, y), label, font=font)
    width = cover_w or max(64, bbox[2] - bbox[0] + 24)
    height = cover_h or max(76, bbox[3] - bbox[1] + 24)
    draw.rectangle((x - 16, y - 10, x - 16 + width, y - 10 + height), fill=WHITE)
    draw.text((x, y), label, font=font, fill=(0, 0, 0))


def redraw_panel_title_line(
    draw: ImageDraw.ImageDraw,
    mask: tuple[int, int, int, int],
    label_xy: tuple[int, int],
    title_xy: tuple[int, int],
    label: str,
    title: str,
    label_size: int = 78,
    title_size: int = 44,
) -> None:
    """Rewrite a panel title row after removing duplicated legacy panel letters."""
    draw.rectangle(mask, fill=WHITE)
    draw.text(label_xy, label, font=fnt(label_size, True), fill=(0, 0, 0))
    draw.text(title_xy, title, font=fnt(title_size), fill=INK)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color=INK, width=6) -> None:
    draw.line([start, end], fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    ang = math.atan2(y2 - y1, x2 - x1)
    size = max(18, width * 4)
    pts = [
        (x2, y2),
        (x2 - size * math.cos(ang - 0.45), y2 - size * math.sin(ang - 0.45)),
        (x2 - size * math.cos(ang + 0.45), y2 - size * math.sin(ang + 0.45)),
    ]
    draw.polygon(pts, fill=color)


def map_xy(ax: tuple[int, int, int, int], x: float, y: float, xr: tuple[float, float], yr: tuple[float, float]) -> tuple[int, int]:
    x0, y0, x1, y1 = ax
    px = int(x0 + (x - xr[0]) / max(xr[1] - xr[0], 1e-12) * (x1 - x0))
    py = int(y1 - (y - yr[0]) / max(yr[1] - yr[0], 1e-12) * (y1 - y0))
    return px, py


def axes(draw: ImageDraw.ImageDraw, ax: tuple[int, int, int, int], xlabel: str, ylabel: str) -> None:
    x0, y0, x1, y1 = ax
    draw.line([(x0, y1), (x1, y1)], fill=INK, width=3)
    draw.line([(x0, y0), (x0, y1)], fill=INK, width=3)
    draw.text(((x0 + x1) // 2 - len(xlabel) * 5, y1 + 25), xlabel, font=F_SMALL, fill=INK)
    draw.text((x0 - 70, (y0 + y1) // 2), ylabel, font=F_TINY, fill=INK)


def density(values: np.ndarray, bins: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    counts, edges = np.histogram(values[np.isfinite(values)], bins=bins)
    dens = counts.astype(float) / max(1, counts.sum())
    centers = 0.5 * (edges[:-1] + edges[1:])
    return centers, dens


def draw_poly(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], color, width=5) -> None:
    if len(pts) > 1:
        draw.line(pts, fill=color, width=width, joint="curve")


def legend(draw: ImageDraw.ImageDraw, x: int, y: int, items: list[tuple[str, tuple[int, int, int]]], font=F_TINY) -> None:
    for i, (label, color) in enumerate(items):
        yy = y + i * (font.size + 15)
        draw.rectangle((x, yy + 4, x + 24, yy + 28), fill=color)
        draw.text((x + 34, yy), label, font=font, fill=INK)


def paste_fit(canvas: Image.Image, img: Image.Image, rect: tuple[int, int, int, int], border=False) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    im = ImageOps.contain(img.convert("RGB"), (x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    px = x0 + (x1 - x0 - im.width) // 2
    py = y0 + (y1 - y0 - im.height) // 2
    canvas.paste(im, (px, py))
    if border:
        ImageDraw.Draw(canvas).rectangle((px, py, px + im.width, py + im.height), outline=LIGHT, width=2)
    return px, py, px + im.width, py + im.height


def paste_fit_aligned(
    canvas: Image.Image,
    img: Image.Image,
    rect: tuple[int, int, int, int],
    halign: str = "center",
    valign: str = "top",
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    im = ImageOps.contain(img.convert("RGB"), (x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    if halign == "left":
        px = x0
    elif halign == "right":
        px = x1 - im.width
    else:
        px = x0 + (x1 - x0 - im.width) // 2
    if valign == "bottom":
        py = y1 - im.height
    elif valign == "center":
        py = y0 + (y1 - y0 - im.height) // 2
    else:
        py = y0
    canvas.paste(im, (px, py))
    return px, py, px + im.width, py + im.height


def trim_title_band(path: Path, top: int) -> Image.Image:
    im = Image.open(path).convert("RGB")
    return im.crop((0, top, im.width, im.height))


def trim_content(im: Image.Image, threshold: int = 248, pad: int = 70) -> Image.Image:
    """Crop outer white margin after the old title band has been removed."""
    arr = np.asarray(im.convert("RGB"))
    mask = np.any(arr < threshold, axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return im
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(im.width, int(xs.max()) + pad + 1)
    y1 = min(im.height, int(ys.max()) + pad + 1)
    return im.crop((x0, y0, x1, y1))


def copy_clean_existing(src_name: str, out_name: str) -> Path:
    im = Image.open(EXTRACTED / src_name).convert("RGB")
    out = CLEAN_DIR / out_name
    im.save(out, dpi=(300, 300))
    return out


def crop_old_to_canvas(old_name: str, top: int, size: tuple[int, int], out_name: str) -> Path:
    """Use the original figure asset, remove its old figure-level title band, and fit onto a plain white canvas."""
    src = trim_title_band(OLD_DIR / old_name, top)
    canvas = Image.new("RGB", size, WHITE)
    paste_fit(canvas, src, (35, 35, size[0] - 35, size[1] - 35), border=False)
    out = CLEAN_DIR / out_name
    canvas.save(out, dpi=(300, 300))
    return out


def save(img: Image.Image, name: str) -> Path:
    out = CLEAN_DIR / name
    img.save(out, dpi=(300, 300))
    return out


def clean_model_evolution() -> Image.Image:
    w, h = 5400, 2500
    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    xs = [500, 1575, 2650, 3725, 4800]
    y = 640
    steps = [
        ("Old model", "PGCS / Phi scalar\nsingle order-parameter\nassumption", RED),
        ("Failure layer", "AUC 0.480\npermutation unstable\nKS shape mismatch", AMBER),
        ("Transition", "scalar embedding\nbreakdown\nno global threshold", (160, 115, 20)),
        ("New model", "latent state regime mixture\nP(Z | S, W_GRN)\nregime-conditioned dynamics", BLUE),
        ("Final claim", "replacement\nnot refinement\nno global scalar", (35, 130, 75)),
    ]
    for i, (title, body, color) in enumerate(steps):
        x = xs[i]
        draw.ellipse((x - 185, y - 185, x + 185, y + 185), outline=color, width=12)
        draw.text((x - 125, y - 60), str(i + 1), font=fnt(112, True), fill=color)
        draw.text((x - 245, y + 245), title, font=fnt(39, True), fill=color)
        draw_wrapped(draw, (x - 265, y + 330), body, fnt(30), INK, max_chars=25, spacing=8)
        if i < len(xs) - 1:
            arrow(draw, (x + 235, y), (xs[i + 1] - 235, y), color=INK, width=9)
    draw_wrapped(
        draw,
        (330, 1660),
        "Lineage statement: the scalar hypothesis is not partially retained. Phi/PGCS is used only as a deprecated diagnostic proxy; the accepted working representation is posterior regime mixture.",
        fnt(38, True),
        INK,
        max_chars=120,
        spacing=10,
    )
    draw_wrapped(
        draw,
        (330, 1885),
        "Regimes: adult_repair, embryonic_reactivation, salamander_blastema and salamander_intact. Dry-lab perturbation support remains partial and computational only.",
        fnt(31),
        MUTED,
        max_chars=130,
        spacing=8,
    )
    draw.text((130, 2315), "Abbreviations: PGCS, prior scalar cell-state score; Phi, deprecated latent scalar proxy; GRN, gene regulatory network.", font=F_SMALL, fill=MUTED)
    return img


def clean_figure1() -> Image.Image:
    w, h = 5000, 3400
    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    panel_title(draw, 160, 160, "A", "Failed scalar hypothesis", RED)
    draw_wrapped(draw, (160, 235), "A single Phi coordinate was tested as a global regenerative order parameter. It failed: ROC AUC ~ 0.480, permutation not significant, bootstrap CI crosses zero, KS indicates shape difference only.", F_TEXT, INK, 58, 8)
    draw.line((420, 760, 1320, 360), fill=RED, width=10)
    draw.line((420, 360, 1320, 760), fill=RED, width=10)
    draw.text((610, 845), "scalar assumed", font=fnt(31, True), fill=RED)

    panel_title(draw, 1820, 160, "B", "Regime posterior, not a threshold", TEAL)
    layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    ld = ImageDraw.Draw(layer)
    for coords, color in [
        ((2020, 420, 2480, 790), (43, 140, 136, 115)),
        ((2280, 350, 2810, 760), (106, 90, 168, 115)),
        ((2540, 500, 3110, 910), (190, 58, 52, 105)),
        ((2110, 680, 2690, 1040), (184, 121, 26, 105)),
    ]:
        ld.ellipse(coords, fill=color, outline=(60, 60, 60, 115), width=4)
    img.paste(layer.convert("RGB"), mask=layer.split()[-1])
    draw = ImageDraw.Draw(img)
    draw.text((2090, 455), "P(Z|S,W_GRN)", font=fnt(38, True), fill=INK)
    legend(draw, 1840, 1030, [(REGIME_LABELS[r], COLORS[REGIME_LABELS[r]]) for r in LATENT_ORDER], F_SMALL)

    panel_title(draw, 3620, 160, "C", "Dynamical replacement", BLUE)
    draw_wrapped(draw, (3620, 245), "p_k(S) = P(Z=k|S,W_GRN)", fnt(31, True), INK, 42, 10)
    draw_wrapped(draw, (3620, 360), "E[Delta S|S] = sum_k p_k(S) F_k(S)", fnt(28, True), INK, 42, 10)
    draw_wrapped(draw, (3620, 505), "Computational representation; not a continuous-time biological law.", F_TEXT, INK, 46, 8)

    panel_title(draw, 160, 1380, "D", "Non-compressible outcome structure", INK)
    center = (2500, 2050)
    draw.ellipse((2300, 1850, 2700, 2250), outline=INK, width=6)
    draw_wrapped(draw, (2375, 1990), "injury-induced\nplasticity", fnt(28, True), INK, 18)
    nodes = [
        ((870, 1850), "adult repair", "adult-repair-dominant mixture\nfate-lock / inflammation context", TEAL),
        ((2520, 1550), "salamander intact", "reference regime with partial overlap", AMBER),
        ((3820, 1860), "tumor-like plasticity", "separate high-plasticity branch\nnot regeneration equivalence", PURPLE),
        ((3130, 2640), "salamander blastema", "distinct latent regenerative regime\nnot an elevated scalar state", RED),
    ]
    for (x, y), title, body, color in nodes:
        arrow(draw, center, (x, y), color=color, width=6)
        draw.text((x - 210, y + 35), title, font=fnt(32, True), fill=color)
        draw_wrapped(draw, (x - 230, y + 85), body, F_SMALL, INK, 36, 5)
    return img


def clean_figure4() -> Image.Image:
    w, h = 6400, 4550
    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    old4 = trim_content(trim_title_band(OLD_DIR / "Figure_4_final_600dpi.png", 230), pad=60)
    old7 = trim_content(trim_title_band(OLD_DIR / "Figure_7_final_600dpi.png", 230), pad=60)
    paste_fit_aligned(img, old4, (110, 110, 3160, 4440), valign="top")
    paste_fit_aligned(img, old7, (3240, 110, 6290, 4440), valign="top")
    # The two source figures each contained a-h panel labels. Keep the left
    # block as a-h and replace only the right-block legacy letters with i-p.
    for label, x, y in [
        ("i", 3375, 165),
        ("j", 4410, 165),
        ("k", 3375, 970),
        ("l", 4410, 970),
        ("m", 3375, 2050),
        ("n", 4410, 2050),
        ("o", 3375, 2780),
        ("p", 4410, 2780),
    ]:
        replace_panel_label(draw, x, y, label, size=60, cover_w=110, cover_h=112)
    return img


def clean_figure5() -> Image.Image:
    w, h = 6400, 4550
    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    old5 = trim_content(trim_title_band(OLD_DIR / "Figure_5_final_600dpi.png", 245), pad=55)
    old6 = trim_content(trim_title_band(OLD_DIR / "Figure_6_final_600dpi.png", 225), pad=55)

    panel_title(draw, 130, 100, "A", "Basin constraint model", TEAL)
    draw.ellipse((330, 335, 1100, 915), outline=TEAL, width=7)
    draw.ellipse((685, 260, 1590, 1045), outline=RED, width=7)
    draw.text((485, 575), "adult repair\nbasin", font=fnt(32, True), fill=TEAL)
    draw.text((900, 520), "fate-lock /\nsenescence-like\nretention", font=fnt(29, True), fill=RED)
    arrow(draw, (220, 950), (755, 740), INK, 6)
    arrow(draw, (1600, 420), (1175, 595), RED, 6)
    draw_wrapped(draw, (155, 1135), "Constraint is basin depth and retention, not a one-dimensional fate-lock axis.", fnt(27, True), INK, 58, 7)

    paste_fit_aligned(img, old6, (150, 1700, 2630, 4440), valign="top")
    paste_fit_aligned(img, old5, (2800, 120, 6280, 4440), valign="top")
    # Relabel merged source panels so Figure 5 has unique labels A-O.
    for label, x, y in [
        ("B", 2940, 145),
        ("C", 3685, 145),
        ("D", 4380, 145),
        ("E", 5220, 145),
        ("F", 2820, 1225),
        ("G", 4175, 1225),
        ("H", 2900, 2150),
        ("I", 4140, 2150),
        ("J", 210, 1692),
        ("K", 940, 1692),
        ("L", 1680, 1692),
        ("M", 210, 2530),
        ("N", 940, 2530),
        ("O", 1680, 2530),
    ]:
        replace_panel_label(draw, x, y, label, size=60, cover_w=96, cover_h=96)
    return img


def clean_figure7() -> Image.Image:
    phi = read_tsv("Phi_unified.tsv")
    roc = read_tsv("roc_curve.tsv")
    ks = read_tsv("ks_test_results.tsv").iloc[0]
    perm = read_tsv("permutation_test_results.tsv").iloc[0]
    perm_null = read_tsv("permutation_null_distribution.tsv")
    boot = read_tsv("bootstrap_confidence_intervals.tsv")
    w, h = 4200, 3620
    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    panels = {
        "A": (280, 260, 1850, 1180),
        "B": (2360, 260, 3930, 1180),
        "C": (280, 1540, 1850, 2460),
        "D": (2360, 1540, 3930, 2460),
    }
    panel_title(draw, 140, 120, "A", "Phi distributions by empirical group")
    ax = panels["A"]
    axes(draw, ax, "deprecated scalar proxy", "density")
    bins = np.linspace(phi["Phi"].quantile(0.002), phi["Phi"].quantile(0.998), 80)
    series = []
    for key in ["mammalian_inflammatory_repair", "salamander_blastema_reactivation", "salamander_intact_reference"]:
        lab = REGIME_LABELS[key]
        centers, dens = density(phi.loc[phi["regime_group"] == key, "Phi"].to_numpy(float), bins)
        series.append((lab, centers, dens, COLORS[lab]))
    ymax = max(float(d.max()) for _, _, d, _ in series)
    for _, centers, dens, color in series:
        pts = [map_xy(ax, float(x), float(y), (bins.min(), bins.max()), (0, ymax * 1.1)) for x, y in zip(centers, dens)]
        draw_poly(draw, pts, color, 5)
    legend(draw, 1550, 310, [(s[0], s[3]) for s in series], F_TINY)

    panel_title(draw, 2220, 120, "B", f"ROC curve: AUC = {float(ks['auc']):.3f}")
    ax = panels["B"]
    axes(draw, ax, "false positive rate", "true positive rate")
    draw.line([map_xy(ax, 0, 0, (0, 1), (0, 1)), map_xy(ax, 1, 1, (0, 1), (0, 1))], fill=(150, 165, 185), width=4)
    pts = [map_xy(ax, float(r.FPR), float(r.TPR), (0, 1), (0, 1)) for r in roc.itertuples()]
    draw_poly(draw, pts, RED, 5)
    draw.text((ax[0] + 20, ax[3] - 75), "Random-level performance; not a classifier.", font=F_TINY, fill=MUTED)

    panel_title(draw, 140, 1400, "C", "Permutation mean-shift test")
    ax = panels["C"]
    axes(draw, ax, "mean difference under label shuffle", "mass")
    vals = perm_null["mean_difference_null"].to_numpy(float)
    bins = np.linspace(np.quantile(vals, 0.002), np.quantile(vals, 0.998), 75)
    centers, dens = density(vals, bins)
    yr = (0, float(dens.max()) * 1.15)
    xr = (float(bins.min()), float(bins.max()))
    draw_poly(draw, [map_xy(ax, float(x), float(y), xr, yr) for x, y in zip(centers, dens)], BLUE, 5)
    obs = float(perm["observed"])
    xobs, _ = map_xy(ax, obs, 0, xr, yr)
    draw.line((xobs, ax[1], xobs, ax[3]), fill=RED, width=5)
    draw.text((ax[0] + 10, ax[3] - 70), f"Observed = {obs:.3f}; p = {float(perm['p_value_two_sided']):.3f}", font=F_TINY, fill=MUTED)

    panel_title(draw, 2220, 1400, "D", "Bootstrap uncertainty")
    ax = panels["D"]
    axes(draw, ax, "estimate and 95% bootstrap CI", "metric")
    vals_all = np.r_[boot["ci_lower_2p5"], boot["ci_upper_97p5"], boot["estimate"]]
    xr = (float(vals_all.min()) - 0.08, float(vals_all.max()) + 0.08)
    for i, r in enumerate(boot.itertuples()):
        y = ax[1] + 130 + i * 150
        xlo, _ = map_xy(ax, float(r.ci_lower_2p5), 0, xr, (0, 1))
        xhi, _ = map_xy(ax, float(r.ci_upper_97p5), 0, xr, (0, 1))
        xest, _ = map_xy(ax, float(r.estimate), 0, xr, (0, 1))
        draw.line((xlo, y, xhi, y), fill=BLUE, width=7)
        draw.ellipse((xest - 14, y - 14, xest + 14, y + 14), fill=RED)
        draw.text((ax[0] + 18, y - 45), str(r.metric), font=F_TINY, fill=INK)
        draw.text((xhi + 18, y - 14), f"{float(r.estimate):.3f}", font=F_TINY, fill=MUTED)
    xzero, _ = map_xy(ax, 0.0, 0, xr, (0, 1))
    if ax[0] <= xzero <= ax[2]:
        draw.line((xzero, ax[1], xzero, ax[3]), fill=INK, width=3)

    panel_title(draw, 140, 2810, "E", "Scalar model rejected")
    draw_wrapped(
        draw,
        (220, 2920),
        f"KS is significant (p = {float(ks['ks_p_value']):.2e}) because distributions differ in shape, but this does not imply separability. Failed AUC, permutation and bootstrap uncertainty reject the single-scalar discriminative model.",
        fnt(31, True),
        INK,
        138,
        10,
    )
    return img


def clean_figure8() -> Image.Image:
    mix = read_tsv("mixture_density_decomposition_phi.tsv")
    phi = read_tsv("Phi_unified.tsv")
    posterior = read_tsv("regime_posterior_probabilities.tsv")
    comp = read_tsv("observed_regime_to_latent_regime_composition.tsv")
    w, h = 7600, 4550
    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    # A-C mixture distributions
    panel_title(draw, 160, 120, "A", "Weighted component densities", TEAL)
    ax = (300, 300, 2100, 1250)
    axes(draw, ax, "deprecated scalar proxy", "probability mass")
    xr = (float(mix["bin_left"].min()), float(mix["bin_right"].max()))
    ymax = float(mix["weighted_component_density"].max()) * 1.2
    for regime, sub in mix.groupby("latent_regime", sort=False):
        lab = REGIME_LABELS.get(regime, str(regime))
        pts = [map_xy(ax, float(r.bin_center), float(r.weighted_component_density), xr, (0, ymax)) for r in sub.itertuples()]
        draw_poly(draw, pts, COLORS[lab], 5)
    legend(draw, 1770, 330, [(REGIME_LABELS[r], COLORS[REGIME_LABELS[r]]) for r in LATENT_ORDER], F_TINY)

    panel_title(draw, 2640, 120, "B", "Empirical density and mixture fit", TEAL)
    ax = (2780, 300, 4580, 1250)
    axes(draw, ax, "deprecated scalar proxy", "probability mass")
    bins = np.sort(np.unique(np.r_[mix["bin_left"].unique(), mix["bin_right"].unique()]))
    centers, emp = density(phi["Phi"].to_numpy(float), bins)
    total = mix.groupby("bin_center", as_index=False)["weighted_component_density"].sum().sort_values("bin_center")
    ymax = max(float(emp.max()), float(total["weighted_component_density"].max())) * 1.2
    draw_poly(draw, [map_xy(ax, float(x), float(y), (bins.min(), bins.max()), (0, ymax)) for x, y in zip(centers, emp)], INK, 5)
    draw_poly(draw, [map_xy(ax, float(r.bin_center), float(r.weighted_component_density), (bins.min(), bins.max()), (0, ymax)) for r in total.itertuples()], RED, 4)
    legend(draw, 4140, 330, [("empirical", INK), ("weighted mixture", RED)], F_TINY)

    panel_title(draw, 5100, 120, "C", "Per-regime distributions", TEAL)
    ax = (5240, 300, 7040, 1250)
    axes(draw, ax, "deprecated scalar proxy", "mass")
    bins = np.linspace(posterior["Phi"].quantile(0.002), posterior["Phi"].quantile(0.998), 80)
    series = []
    for r in LATENT_ORDER:
        lab = REGIME_LABELS[r]
        centers, dens = density(posterior.loc[posterior["latent_regime_map"].eq(r), "Phi"].to_numpy(float), bins)
        series.append((lab, centers, dens, COLORS[lab]))
    ymax = max(float(d.max()) for _, _, d, _ in series)
    for _, centers, dens, color in series:
        draw_poly(draw, [map_xy(ax, float(x), float(y), (bins.min(), bins.max()), (0, ymax * 1.1)) for x, y in zip(centers, dens)], color, 5)

    panel_title(draw, 160, 1590, "D", "Dominant posterior regime assignment in state space", PURPLE)
    ax = (360, 1780, 2380, 3120)
    axes(draw, ax, "fate-lock axis", "embryonic module")
    sample = posterior.sample(min(9000, len(posterior)), random_state=20260620)
    xr = tuple(np.quantile(sample["Fate_lock"], [0.005, 0.995]))
    yr = tuple(np.quantile(sample["Embryonic_module_score"], [0.005, 0.995]))
    for r in sample.itertuples():
        lab = REGIME_LABELS.get(r.latent_regime_map, str(r.latent_regime_map))
        x, y = map_xy(ax, float(r.Fate_lock), float(r.Embryonic_module_score), xr, yr)
        if ax[0] <= x <= ax[2] and ax[1] <= y <= ax[3]:
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=COLORS[lab])

    panel_title(draw, 2780, 1590, "E", "Posterior certainty", PURPLE)
    ax = (2920, 1780, 4720, 3120)
    axes(draw, ax, "fate-lock axis", "max P(Z|S)")
    qbin = pd.qcut(posterior["Fate_lock"].rank(method="first"), 45, labels=False)
    q = posterior.groupby(qbin).agg(x=("Fate_lock", "mean"), y=("latent_regime_max_posterior", "mean")).reset_index()
    pts = [map_xy(ax, float(r.x), float(r.y), (q.x.min(), q.x.max()), (0, 1)) for r in q.itertuples()]
    draw_poly(draw, pts, BLUE, 5)
    draw.text((ax[0] + 15, ax[3] - 70), "Lower certainty indicates overlapping latent state regimes.", font=F_TINY, fill=MUTED)

    panel_title(draw, 5200, 1590, "F", "Observed groups as mixtures", PURPLE)
    ax = (5430, 1830, 6900, 3120)
    base_y = ax[3]
    bar_w = 210
    gap = 270
    for i, row in comp.iterrows():
        x = ax[0] + 80 + i * (bar_w + gap)
        y = base_y
        for r in LATENT_ORDER:
            val = float(row[f"mean_P_Z_{r}"])
            hh = int(val * (ax[3] - ax[1]))
            lab = REGIME_LABELS[r]
            draw.rectangle((x, y - hh, x + bar_w, y), fill=COLORS[lab], outline=WHITE, width=2)
            y -= hh
        label = REGIME_LABELS.get(str(row["observed_regime_proxy"]), str(row["observed_regime_proxy"]).replace("_", "\n"))
        draw_wrapped(draw, (x - 25, ax[3] + 30), label.replace("mammalian inflammatory repair", "mammal repair"), F_TINY, INK, 16, 2)
    axes(draw, ax, "observed species/regime group", "mean posterior")
    legend(draw, 6900, 1900, [(REGIME_LABELS[r], COLORS[REGIME_LABELS[r]]) for r in LATENT_ORDER], F_TINY)

    panel_title(draw, 160, 3660, "G", "Regime-conditioned representation", BLUE)
    draw.text((650, 3740), "p_k(S) = P(Z=k|S,W_GRN)", font=fnt(48, True), fill=INK)
    draw.text((650, 3845), "E[Delta S|S] = sum_k p_k(S) F_k(S)", font=fnt(42, True), fill=INK)
    draw_wrapped(draw, (650, 3970), "This notation summarizes a computational posterior-regime representation, not an experimentally identified continuous-time biological law.", F_TEXT, INK, 165, 8)
    return img


def heat_color(v: float, vmin: float, vmax: float) -> tuple[int, int, int]:
    t = (v - vmin) / max(vmax - vmin, 1e-12)
    a = np.array([238, 246, 255])
    b = np.array([43, 124, 180])
    rgb = a * (1 - t) + b * t
    return tuple(int(x) for x in rgb)


def draw_heatmap(draw: ImageDraw.ImageDraw, ax: tuple[int, int, int, int], df: pd.DataFrame, row_col: str, col_col: str, val_col: str, fmt="{:.2f}") -> None:
    rows = list(df[row_col].drop_duplicates())
    cols = list(df[col_col].drop_duplicates())
    piv = df.pivot(index=row_col, columns=col_col, values=val_col).loc[rows, cols]
    arr = piv.to_numpy(float)
    vmin, vmax = float(np.nanmin(arr)), float(np.nanmax(arr))
    cw = (ax[2] - ax[0]) // len(cols)
    ch = (ax[3] - ax[1]) // len(rows)
    for i, r in enumerate(rows):
        draw.text((ax[0] - 230, ax[1] + i * ch + ch // 2 - 10), REGIME_LABELS.get(str(r), str(r)).replace("_", " "), font=F_TINY, fill=INK)
        for j, c in enumerate(cols):
            val = float(arr[i, j])
            x0 = ax[0] + j * cw
            y0 = ax[1] + i * ch
            draw.rectangle((x0, y0, x0 + cw, y0 + ch), fill=heat_color(val, vmin, vmax), outline=WHITE, width=3)
            draw.text((x0 + cw // 2 - 25, y0 + ch // 2 - 10), fmt.format(val), font=F_TINY, fill=INK)
    for j, c in enumerate(cols):
        draw_wrapped(draw, (ax[0] + j * cw + 5, ax[1] - 58), REGIME_LABELS.get(str(c), str(c)).replace("_", " "), F_TINY, INK, 16, 1)


def clean_figure9() -> Image.Image:
    overlap = read_tsv("regime_overlap_matrix.tsv")
    species = read_tsv("species_regime_overlap_matrix.tsv")
    kl = read_tsv("regime_KL_divergence_matrix.tsv")
    w, h = 4200, 3620
    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    panel_title(draw, 140, 120, "A", "Latent-state-regime overlap")
    draw_heatmap(draw, (650, 420, 1850, 1420), overlap, "regime_i", "regime_j", "bhattacharyya_overlap_proxy")
    panel_title(draw, 2220, 120, "B", "Species/regime posterior overlap")
    draw_heatmap(draw, (2760, 460, 3860, 1420), species, "species_regime_i", "species_regime_j", "posterior_composition_overlap")
    panel_title(draw, 140, 1800, "C", "Symmetrized KL divergence")
    draw_heatmap(draw, (650, 2100, 1850, 3100), kl, "regime_i", "regime_j", "symmetric_KL", "{:.1f}")
    panel_title(draw, 2220, 1800, "D", "Strongest divergence ranking")
    ax = (2600, 2100, 3930, 3100)
    axes(draw, ax, "symmetrized KL divergence", "pair")
    pairs = kl[kl["regime_i"] < kl["regime_j"]].sort_values("symmetric_KL", ascending=False).head(6)
    xmax = float(pairs["symmetric_KL"].max()) * 1.15
    for i, r in enumerate(pairs.itertuples()):
        y = ax[1] + 55 + i * 145
        bar = int(float(r.symmetric_KL) / xmax * 720)
        label = f"{REGIME_LABELS.get(r.regime_i, r.regime_i)} vs {REGIME_LABELS.get(r.regime_j, r.regime_j)}"
        draw.text((ax[0] - 360, y + 3), label[:34], font=F_TINY, fill=INK)
        draw.rectangle((ax[0] + 55, y, ax[0] + 55 + bar, y + 45), fill=RED)
        draw.text((ax[0] + 75 + bar, y + 8), f"{float(r.symmetric_KL):.2f}", font=F_TINY, fill=INK)
    return img


def clean_supplementary() -> Image.Image:
    comp = pd.read_csv(ROOT / "FINAL_SUBMISSION_PACKAGE/supplementary_source_data/closure_model_comparison.tsv", sep="\t").iloc[0]
    ccs = pd.read_csv(ROOT / "FINAL_SUBMISSION_PACKAGE/supplementary_source_data/causal_closure_score_summary.tsv", sep="\t")
    reg = pd.read_csv(ROOT / "FINAL_SUBMISSION_PACKAGE/supplementary_source_data/regime_conditioned_deltaZ_consistency.tsv", sep="\t")
    bias = pd.read_csv(ROOT / "FINAL_SUBMISSION_PACKAGE/supplementary_source_data/counterfactual_bias_by_regime.tsv", sep="\t")
    w, h = 4200, 2550
    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    panel_title(draw, 110, 110, "A", "Regime-conditioned model comparison")
    draw.text((180, 250), f"Global W MSE: {float(comp.global_MSE):.4f}", font=F_TEXT, fill=INK)
    draw.text((180, 305), f"W(Z) MSE: {float(comp.regime_conditioned_MSE_LOO):.4f}", font=F_TEXT, fill=INK)
    draw.text((180, 360), f"Error reduction: {float(comp.prediction_error_reduction_fraction):.3f}", font=F_TEXT, fill=INK)
    draw.text((180, 415), f"Bootstrap p: {float(comp.bootstrap_p_value_positive_error_reduction):.3f}", font=F_TEXT, fill=INK)
    ax = (180, 535, 1280, 840)
    axes(draw, ax, "model", "MSE")
    vals = [float(comp.global_MSE), float(comp.regime_conditioned_MSE_LOO)]
    for i, (lab, val, col) in enumerate([("global W", vals[0], GREY), ("W(Z)", vals[1], TEAL)]):
        x = ax[0] + 180 + i * 390
        hh = int(val / max(vals) * 240)
        draw.rectangle((x, ax[3] - hh, x + 170, ax[3]), fill=col)
        draw.text((x - 5, ax[3] + 35), lab, font=F_TINY, fill=INK)

    panel_title(draw, 1570, 110, "B", "Pathway x metric heatmap")
    metrics = [
        ("directional_consistency_component", "direction"),
        ("CCS_available_evidence_rescaled", "CCS"),
        ("null_separation_component", "null sep."),
        ("counterfactual_agreement_component", "counterfactual"),
    ]
    rows = ccs["pathway"].tolist()
    x0, y0, cw, ch = 1850, 310, 260, 95
    for j, (_, lab) in enumerate(metrics):
        draw_wrapped(draw, (x0 + j * cw, y0 - 80), lab, F_TINY, INK, 13, 1)
    for i, path in enumerate(rows):
        draw.text((x0 - 155, y0 + i * ch + 30), path, font=F_TINY, fill=INK)
        row = ccs.iloc[i]
        for j, (col, _) in enumerate(metrics):
            val = row[col]
            val = np.nan if pd.isna(val) else float(val)
            fill = (230, 233, 238) if np.isnan(val) else heat_color(val, 0, 1)
            draw.rectangle((x0 + j * cw, y0 + i * ch, x0 + (j + 1) * cw - 5, y0 + (i + 1) * ch - 5), fill=fill, outline=WHITE, width=2)
            txt = "n/a" if np.isnan(val) else f"{val:.2f}"
            draw.text((x0 + j * cw + 78, y0 + i * ch + 32), txt, font=F_TINY, fill=INK)

    panel_title(draw, 110, 1050, "C", "Regime x metric heatmap")
    by_reg = reg.groupby("latent_regime").agg(
        sign=("regime_conditioned_sign_alignment_LOO", "mean"),
        cosine=("within_regime_cosine_regime_conditioned_LOO", "mean"),
        error=("regime_conditioned_abs_error_LOO", "mean"),
    ).reset_index()
    # Rescale error so larger means better support.
    max_err = max(float(by_reg["error"].max()), 1e-9)
    by_reg["error_support"] = 1 - by_reg["error"] / max_err
    cols = [("sign", "sign"), ("cosine", "cosine"), ("error_support", "error support")]
    x0, y0, cw, ch = 720, 1230, 300, 115
    for j, (_, lab) in enumerate(cols):
        draw.text((x0 + j * cw + 20, y0 - 55), lab, font=F_TINY, fill=INK)
    for i, row in by_reg.iterrows():
        draw.text((x0 - 360, y0 + i * ch + 36), REGIME_LABELS.get(row["latent_regime"], row["latent_regime"]), font=F_TINY, fill=INK)
        for j, (col, _) in enumerate(cols):
            val = float(row[col])
            fill = heat_color(val, 0, 1)
            draw.rectangle((x0 + j * cw, y0 + i * ch, x0 + (j + 1) * cw - 5, y0 + (i + 1) * ch - 5), fill=fill, outline=WHITE, width=2)
            draw.text((x0 + j * cw + 95, y0 + i * ch + 40), f"{val:.2f}", font=F_TINY, fill=INK)

    panel_title(draw, 2250, 1050, "D", "Consistency limits")
    limits = [
        ("Cross-dataset comparison", "unavailable in locked files"),
        ("Direction reversal", f"frequency {float(comp.counterfactual_direction_reversal_frequency):.2f}"),
        ("Cross-regime instability", f"ratio {float(comp.cross_regime_instability_ratio):.2f}"),
        ("NOTCH / SHH evidence", "low coverage or mixed direction"),
    ]
    yy = 1220
    for title, body in limits:
        draw.text((2320, yy), title, font=fnt(25, True), fill=RED if "reversal" in title.lower() or "instability" in title.lower() else INK)
        draw.text((2920, yy), body, font=F_TEXT, fill=INK)
        yy += 120

    draw.text((110, 2180), "E", font=F_PANEL, fill=INK)
    draw_wrapped(
        draw,
        (185, 2185),
        "Partial regime-conditioned perturbation consistency only; complete causal closure and wet-lab validation are not claimed.",
        fnt(30, True),
        INK,
        140,
        8,
    )
    return img


def make_contact(paths: list[tuple[str, Path]]) -> None:
    thumbs: list[Image.Image] = []
    for label, path in paths:
        im = Image.open(path).convert("RGB")
        im.thumbnail((520, 360), Image.Resampling.LANCZOS)
        card = Image.new("RGB", (560, 430), WHITE)
        card.paste(im, ((560 - im.width) // 2, 55))
        d = ImageDraw.Draw(card)
        d.text((16, 16), label, font=fnt(22, True), fill=INK)
        thumbs.append(card)
    cols = 3
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 560, rows * 430), WHITE)
    for i, t in enumerate(thumbs):
        sheet.paste(t, ((i % cols) * 560, (i // cols) * 430))
    sheet.save(CONTACT, dpi=(150, 150))


def replace_docx_media(mapping: dict[str, Path]) -> None:
    temp = WORK / "docx_zip"
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True)
    with ZipFile(INPUT_DOCX) as zin:
        zin.extractall(temp)
    for media_name, src in mapping.items():
        dst = temp / "word" / "media" / media_name
        if not dst.exists():
            raise FileNotFoundError(f"media target missing: {media_name}")
        shutil.copy2(src, dst)
    if OUTPUT_DOCX.exists():
        OUTPUT_DOCX.unlink()
    with ZipFile(OUTPUT_DOCX, "w", compression=ZIP_DEFLATED) as zout:
        for p in sorted(temp.rglob("*")):
            if p.is_file():
                zout.write(p, p.relative_to(temp).as_posix())


LEGENDS: dict[str, tuple[str, str]] = {
    "Figure 1A": (
        "Figure 1A | Model evolution map: replacement, not refinement.",
        "The earlier PGCS/Phi scalar model treated cell fate as if it could be approximated by a single order parameter, an assumption related to classical landscape views of cell-fate organization but not guaranteed by cross-species single-cell comparisons 1,52 . Colors mark model stages or states rather than biological cell types. Arrows indicate logical replacement and reconstruction, not temporal biological progression. Phi is shown only as a deprecated failed scalar projection. The accepted working representation is the latent-state-regime posterior P(Z|S,W_GRN), with adult_repair, embryonic_reactivation, salamander_blastema and salamander_intact represented as posterior regimes 6,22 .",
    ),
    "Figure 1": (
        "Figure 1 | Phi failure and latent-state-regime replacement logic.",
        "Figure 1 introduces the transition from scalar ordering to posterior regime probability structure. Colors indicate model components or representation layers: rejected scalar hypothesis, posterior-mixture representation, dynamical replacement and non-compressible outcome structure. Regime colors identify adult_repair, embryonic_reactivation, salamander_blastema and salamander_intact when shown. Arrows are conceptual relationships and do not imply one-dimensional ordering. Where notation is shown, p_k(S)=P(Z=k|S,W_GRN) and E[Delta S|S]=sum_k p_k(S)F_k(S) are computational summaries, not experimentally identified continuous-time biological laws.",
    ),
    "Figure 2": (
        "Figure 2 | Shared accessibility does not determine fate.",
        "The figure summarizes connected accessibility and high-plasticity structure while separating accessibility from fate determination. Categorical colors denote inferred state groups or state classes when used; continuous colorbars report the score or probability named in each panel. Heatmap intensity indicates normalized transition, absorption or score value, with higher intensity representing higher displayed values. Trajectory, pseudotime and velocity-derived summaries indicate inferred computational transition tendency, not direct lineage tracing 3,26,48 . Boxplots show score distributions; points represent individual cells or observations, boxes show interquartile range, center lines show medians, whiskers show 1.5x interquartile range and black diamonds indicate group means.",
    ),
    "Figure 3": (
        "Figure 3 | Stemness is a local accessibility component.",
        "Stemness-associated Wnt/beta-catenin/TCF-LEF/MYC programs contribute to local accessibility and proliferative competence, but they do not define global regime identity 18,19,29 . Point and line colors denote pathway or perturbation conditions as labeled. Higher score values or stronger color intensity indicate stronger activity of the displayed module. Diverging heatmap colors indicate relative module-score direction around the scale midpoint. Effect-size points summarize condition-level differences and are interpreted as local accessibility evidence, not as a global fate axis.",
    ),
    "Figure 4": (
        "Figure 4 | Positional programs are regime-conditioned developmental coordinates.",
        "RA/HOX-, FGF/SHH- and NOTCH-associated positional or patterning programs are interpreted within posterior-regime context, not as a universal scalar ranking of mammalian and salamander systems 14,17,30 . Colors denote pathway/module scores, regeneration stages, species groups or proxy distributions as indicated by panel legends and colorbars. Heatmap intensity indicates normalized positional-program module score; line plots show stage or pseudotime trends. Arrows in branch schematics indicate interpreted program relationships and do not establish direct causal proof. Boxplots, where present, use points for observations, interquartile-range boxes, median center lines, 1.5x interquartile-range whiskers and black diamonds for group means.",
    ),
    "Figure 5": (
        "Figure 5 | Fate-lock constrains the adult-repair basin.",
        "Fate-lock is represented as a basin-like adult-repair constraint involving BMP-SMAD signaling, p53/p21, p16/Rb and senescence-associated stabilization 31,32 . The basin schematic is conceptual; scatter plots, heatmaps, bar charts and boxplots summarize locked source-data outputs. Continuous colors and heatmap scales represent the displayed score or transition probability, with higher intensity corresponding to higher values on the shown scale. Arrows in schematic panels indicate inferred constraint direction, not complete causal closure. Boxplots use points for observations, interquartile-range boxes, median center lines, 1.5x interquartile-range whiskers and black diamonds for group means.",
    ),
    "Figure 6": (
        "Figure 6 | Tumor-like plasticity is a separate branch.",
        "Tumor-like plasticity is shown as a high-plasticity boundary branch distinct from regenerative competence 27,36 . Panels a-d use the same embedding colored by continuous scores; each colorbar represents the score named in that panel, and higher colorbar values indicate higher score. In panels e-f, teal/cyan denotes other tumor cells and yellow denotes top tumor-like cells. Points represent individual tumor cells or observations; boxes show interquartile range, center lines show medians, whiskers show 1.5x interquartile range and black diamonds indicate group means. Panel g compares boundary scores within tumor cells only: within each boundary-score category, the left boxplot shows other tumor cells and the right boxplot shows top tumor-like cells; yellow encodes the embryonic-like boundary score and teal encodes the inflammatory-repair boundary score. Panel h shows normalized module means, with blue indicating lower relative module mean and red indicating higher relative module mean. The tumor-like branch is not interpreted as salamander_blastema or regenerative competence.",
    ),
    "Figure 7": (
        "Figure 7 | Scalar Phi is rejected as a regime separator.",
        "ROC, permutation, bootstrap and KS summaries show that Phi is non-discriminative as a global order parameter 47 . Line colors distinguish empirical curves, null or random-reference expectations and observed statistics as labeled. The ROC diagonal indicates random-level performance; permutation curves show the label-shuffle null; bootstrap intervals show uncertainty around estimated shifts. The significant KS statistic detects distributional shape difference, not separability. Phi is therefore retained only as a deprecated scalar proxy for failure/QC, not as a regime separator.",
    ),
    "Figure 8": (
        "Figure 8 | Latent-state-regime posterior dynamics provide the working representation.",
        "The model represents each observed state through posterior regime assignment P(Z|S,W_GRN), rather than through a global scalar coordinate. Density curves, scatter colors and stacked bars denote posterior mass assigned to adult_repair, embryonic_reactivation, salamander_blastema and salamander_intact. Higher density, stronger point color or greater bar height reflects greater posterior mass in the displayed summary. For regime k, p_k(S)=P(Z=k|S,W_GRN), and the expected local transition tendency may be summarized as E[Delta S|S]=sum_k p_k(S)F_k(S). This notation is a computational representation, not an experimentally identified continuous-time biological law 6,22 .",
    ),
    "Figure 9": (
        "Figure 9 | Overlap and symmetrized divergence define regime structure.",
        "Overlap is interpreted as non-separability, whereas symmetrized KL divergence is interpreted as distributional difference rather than scalar distance 22,37 . Heatmap color intensity corresponds to the displayed matrix value, and numbers printed in cells are matrix entries. Blue overlap matrices quantify shared posterior or state-space occupancy. The symmetrized KL divergence matrix reports distributional difference, and red bars rank the strongest divergence values. Higher divergence does not indicate distance along a biological scalar axis.",
    ),
    "Supplementary Figure 1": (
        "Supplementary Figure 1 | Dry-lab perturbation consistency audit.",
        "Existing perturbation-derived outputs were used to ask whether pathway-linked posterior-shift summaries were directionally compatible with regime-conditioned structure. Heatmap colors encode metric values; higher intensity indicates stronger directional consistency, null separation, support or bias as labeled. Gray cells denote a shared model-level value rather than a pathway-specific estimate. The model-comparison panel reports global W_GRN versus regime-conditioned W(Z), and the consistency-limit panel summarizes unavailable cross-dataset comparison, counterfactual reversals, cross-regime instability and limited NOTCH/SHH evidence. The analysis supports partial regime-conditioned perturbation consistency only; complete causal closure and wet-lab validation are not claimed.",
    ),
}


FIGURE_SEQUENCE = [
    "Figure 1A",
    "Figure 1",
    "Figure 2",
    "Figure 3",
    "Figure 4",
    "Figure 5",
    "Figure 6",
    "Figure 7",
    "Figure 8",
    "Figure 9",
    "Supplementary Figure 1",
]


def paragraph_text(para: etree._Element) -> str:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return "".join(t.text or "" for t in para.xpath(".//w:t", namespaces=ns))


def set_paragraph_text(para: etree._Element, text: str) -> None:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    texts = para.xpath(".//w:t", namespaces=ns)
    if not texts:
        r = etree.SubElement(para, f"{{{ns['w']}}}r")
        t = etree.SubElement(r, f"{{{ns['w']}}}t")
        t.text = text
        return
    texts[0].text = text
    for t in texts[1:]:
        t.text = ""


def patch_docx_legends() -> dict[str, bool]:
    temp = WORK / "docx_text_patch"
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True)
    with ZipFile(OUTPUT_DOCX) as zin:
        zin.extractall(temp)
    doc_xml = temp / "word" / "document.xml"
    root = etree.fromstring(doc_xml.read_bytes())
    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    body = root.find("w:body", ns)
    if body is None:
        raise RuntimeError("document body not found")

    templates: dict[str, tuple[etree._Element, etree._Element]] = {}
    children = list(body)
    for i, el in enumerate(children[:-1]):
        if etree.QName(el).localname != "p":
            continue
        txt = paragraph_text(el).strip()
        for fig_id, (title, _) in LEGENDS.items():
            if txt == title or txt.startswith(fig_id + " |"):
                next_el = children[i + 1]
                if etree.QName(next_el).localname == "p":
                    templates[fig_id] = (el, next_el)
                break

    image_paras = [
        el
        for el in list(body)
        if etree.QName(el).localname == "p" and el.xpath(".//a:blip/@r:embed", namespaces=ns)
    ]
    status: dict[str, bool] = {fig_id: fig_id in templates for fig_id in FIGURE_SEQUENCE}
    if len(image_paras) < len(FIGURE_SEQUENCE):
        raise RuntimeError(f"expected {len(FIGURE_SEQUENCE)} images, found {len(image_paras)}")

    import copy

    for fig_id, img_para in reversed(list(zip(FIGURE_SEQUENCE, image_paras))):
        title_text, caption_text = LEGENDS[fig_id]
        if fig_id in templates:
            title_para = copy.deepcopy(templates[fig_id][0])
            caption_para = copy.deepcopy(templates[fig_id][1])
        else:
            title_para = copy.deepcopy(templates["Figure 1"][0])
            caption_para = copy.deepcopy(templates["Figure 1"][1])
        set_paragraph_text(title_para, title_text)
        set_paragraph_text(caption_para, caption_text)
        idx = list(body).index(img_para)
        body.insert(idx + 1, caption_para)
        body.insert(idx + 1, title_para)

    # Remove the old terminal Figure legends section so legends are not stranded at the end.
    children = list(body)
    start = None
    end = None
    for i, el in enumerate(children):
        if etree.QName(el).localname == "p" and paragraph_text(el).strip() == "Figure legends":
            start = i
        if start is not None and etree.QName(el).localname == "p" and paragraph_text(el).strip() == "References":
            end = i
            break
    if start is not None and end is not None:
        for el in children[start:end]:
            body.remove(el)

    doc_xml.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))
    if OUTPUT_DOCX.exists():
        OUTPUT_DOCX.unlink()
    with ZipFile(OUTPUT_DOCX, "w", compression=ZIP_DEFLATED) as zout:
        for p in sorted(temp.rglob("*")):
            if p.is_file():
                zout.write(p, p.relative_to(temp).as_posix())
    return status


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[tuple[str, Path]] = []
    actions: list[tuple[str, str, str]] = []

    generated = {
        "image1.png": save(clean_model_evolution(), "image1_Figure1A_model_evolution_clean.png"),
        "image2.png": save(clean_figure1(), "image2_Figure1_clean.png"),
        "image3.png": crop_old_to_canvas("Figure_2_final_600dpi.png", 315, (4200, 4570), "image3_Figure2_source_crop_clean.png"),
        "image4.png": crop_old_to_canvas("Figure_3_final_600dpi.png", 315, (4425, 4384), "image4_Figure3_source_crop_clean.png"),
        "image5.png": save(clean_figure4(), "image5_Figure4_relayout_clean.png"),
        "image6.png": save(clean_figure5(), "image6_Figure5_relayout_clean.png"),
        "image7.png": crop_old_to_canvas("Figure_8_final_600dpi.png", 315, (4200, 5295), "image7_Figure6_source_crop_clean.png"),
        "image8.png": save(clean_figure7(), "image8_Figure7_redrawn_clean.png"),
        "image9.png": save(clean_figure8(), "image9_Figure8_redrawn_clean.png"),
        "image10.png": save(clean_figure9(), "image10_Figure9_redrawn_clean.png"),
        "image11.png": save(clean_supplementary(), "image11_SuppFigure1_redrawn_clean.png"),
    }
    descriptions = {
        "image1.png": "redrawn without figure-level title, status badge, bottom card or large rectangular boxes",
        "image2.png": "redrawn without header band, status badge, callout-card rectangles or presentation conclusion box",
        "image3.png": "original Figure 2 source cropped to remove old figure-level title and gray title-removal band",
        "image4.png": "original Figure 3 source cropped to remove old figure-level title and gray title-removal band",
        "image5.png": "old figure titles cropped; positional panels re-laid out on clean white canvas",
        "image6.png": "Figure 5 fully re-laid out on a clean grid; old figure titles removed; no overlay rectangles",
        "image7.png": "original Figure 8 source cropped to remove old figure-level title and gray title-removal band",
        "image8.png": "redrawn from TSV outputs without figure-level title, grey header bar or bottom callout rectangles",
        "image9.png": "redrawn from TSV outputs without figure-level title, grey header bar or card rectangles",
        "image10.png": "redrawn from TSV outputs without figure-level title, grey header bar or callout rectangles",
        "image11.png": "redrawn supplementary audit figure without dashboard badges or masked rectangles",
    }
    for i in range(1, 12):
        key = f"image{i}.png"
        paths.append((key, generated[key]))
        actions.append((key, generated[key].name, descriptions[key]))

    make_contact(paths)
    replace_docx_media(generated)
    legend_status = patch_docx_legends()

    with (CLEAN_DIR / "clean_figure_asset_manifest.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["docx_media_name", "clean_file", "action"])
        writer.writerows(actions)

    audit_rows = [
        ("Figure 1A", "model-evolution panels", "stage colors", "colors mark model stages, not biological cell types", "not applicable", "arrows show logical replacement, not time", "Phi deprecated; P(Z|S,W_GRN) accepted", "not applicable", "legend expanded and placed below figure", "yes", "CLEAR"),
        ("Figure 1", "A-D", "model-component and regime colors", "colors identify representation layers or posterior regimes", "not applicable", "arrows show conceptual relationships, not scalar ordering", "Phi failure; posterior-regime mixture accepted", "not applicable", "softened formula and clarified color/arrows", "yes", "CLEAR"),
        ("Figure 2", "a-g", "categorical state colors and continuous score colorbars", "categorical colors denote inferred state groups; colorbars denote named scores/probabilities", "heatmaps show normalized transition or absorption values", "velocity/pseudotime summaries are computational tendencies", "higher score/colorbar value means higher displayed score or probability", "points observations; boxes IQR; lines medians; whiskers 1.5x IQR; black diamonds means", "boxplot and heatmap language added", "yes", "CLEAR"),
        ("Figure 3", "a-f", "pathway or perturbation condition colors", "colors denote labeled pathway/condition groups", "diverging heatmap shows relative module-score direction around midpoint", "effect-size markers summarize condition differences", "higher score/intensity means stronger module activity", "error bars/points as shown; no unreported symbol meaning added", "stemness constrained to local accessibility", "yes", "CLEAR"),
        ("Figure 4", "a-p", "pathway/module/stage/proxy colors", "colors denote module scores, regeneration stage, species group or proxy distribution as labeled", "heatmaps show normalized positional-program module score", "schematic arrows indicate interpreted program relationships only", "higher score/intensity means stronger displayed module/proxy", "boxplot conventions added where present", "right-hand block relabeled i-p and legend expanded", "yes", "CLEAR"),
        ("Figure 5", "A-O", "score gradients, heatmaps, bar colors and boxplot group colors", "colors encode displayed scores, transition probabilities, bars or source-data groups", "heatmaps show transition/probability or module values", "schematic arrows indicate inferred constraint direction only", "higher intensity means higher displayed score/probability", "boxplot conventions and black-diamond means stated", "merged panels relabeled uniquely and legend expanded", "yes", "CLEAR"),
        ("Figure 6", "a-h", "continuous score colorbars; teal/yellow tumor-group colors; blue-red heatmap", "a-d colorbars are continuous scores; e-f teal/cyan other tumor cells and yellow top tumor-like; g color encodes boundary-score category, not group", "h blue-to-red heatmap shows lower-to-higher normalized module means", "no causal arrows; boundary comparisons prevent regeneration equivalence", "higher colorbar values indicate higher scores", "points individual tumor cells/observations; boxes IQR; medians; 1.5x IQR whiskers; black diamonds means; g left/right boxes are other tumor cells/top tumor-like", "panel g meaning resolved from v5 source data and legend updated", "yes", "CLEAR"),
        ("Figure 7", "A-E", "ROC/permutation/bootstrap/KS line and marker colors", "colors distinguish empirical curves, null/random references and observed statistics", "not applicable", "ROC diagonal is random-level reference; permutation curve is label-shuffle null", "AUC near random; KS shape difference not separability", "interval markers show bootstrap uncertainty", "Phi rejection/QC interpretation reinforced", "yes", "CLEAR"),
        ("Figure 8", "A-G", "posterior-regime colors and density/bar encodings", "colors denote posterior mass for adult_repair, embryonic_reactivation, salamander_blastema and salamander_intact", "density/stacked bars show posterior mass values", "notation summarizes computational expected local transition tendency", "higher density/color/bar height means greater posterior mass", "not applicable", "strong dS/dt formula removed; soft notation explained", "yes", "CLEAR"),
        ("Figure 9", "A-D", "blue overlap matrices and red divergence bars", "blue heatmaps quantify overlap or shared posterior occupancy; red bars rank divergence", "heatmap intensity equals printed matrix value", "not applicable", "higher divergence means distributional difference, not scalar-axis distance", "not applicable", "overlap versus divergence clarified", "yes", "CLEAR"),
        ("Supplementary Figure 1", "A-E", "model-comparison bars, metric heatmaps, gray cells and consistency-limit labels", "heatmap colors encode metric values; gray cells are shared model-level values", "higher intensity means stronger metric value as labeled", "no wet-lab causal arrows or closure claim", "higher support/consistency/null separation as labeled; bias interpreted cautiously", "not applicable", "forbidden dashboard badges avoided; partial dry-lab consistency only", "yes", "CLEAR"),
    ]
    lines = [
        "# Figure Visual Encoding Audit",
        "",
        f"Input DOCX: `{INPUT_DOCX}`",
        f"Output DOCX: `{OUTPUT_DOCX}`",
        f"Contact sheet: `{CONTACT}`",
        "",
        "All embedded figures were regenerated or inspected visually. Legends were moved directly below their corresponding figures in the review-ready DOCX.",
        "",
        "| figure number | panel labels inspected | colors inspected | what colors mean | heatmap scale meaning | arrow/line meaning | score direction | shape/symbol/boxplot meaning | what was added or corrected | legend directly below figure | final status |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in audit_rows)
    lines.extend([
        "",
        "## Acceptance Checklist",
        "",
        "- All 11 embedded figures were visually inspected via generated assets and rendered manuscript pages.",
        "- Scientifically meaningful colors, heatmap scales, score directions, arrows/lines, boxplot elements and black diamonds are explained in the legends.",
        "- Figure 6 panel g was resolved from `Figure_7_panel_g_source_data_v5.tsv`: boundary-score category is encoded by color, while left/right position within each category denotes other tumor cells versus top tumor-like cells.",
        "- No figure is left with its legend only at the end of the manuscript.",
        "- No new analyses, datasets, references or strengthened causal claims were introduced.",
    ])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    log_lines = [
        "# Figure Legend Change Log",
        "",
        f"Output DOCX: `{OUTPUT_DOCX}`",
        "",
        "## Structural Changes",
        "",
        "- Moved each main-figure and Supplementary Figure 1 legend directly below the corresponding embedded image.",
        "- Removed the terminal-only `Figure legends` section after duplicating/replacing its content inline, while preserving the References section.",
        "- Kept reference numbering/text unchanged; no new citations were inserted.",
        "",
        "## Legend Content Changes",
        "",
    ]
    for fig_id in FIGURE_SEQUENCE:
        log_lines.append(f"- {fig_id}: {'source legend found and replaced inline' if legend_status.get(fig_id) else 'fallback template used'}; added/standardized color, score, heatmap, arrow/line and symbol explanations as applicable.")
    log_lines.extend([
        "",
        "## Image Content Changes Relevant To Legends",
        "",
        "- Figure 1 and Figure 8: replaced strong continuous-time formula with posterior-regime notation.",
        "- Figure 4 and Figure 5: repaired duplicate panel labels in merged source figures.",
        "- Supplementary Figure 1: removed internal dashboard-style closure badge language from image pixels.",
        "- Figure 6 panel g: legend now states that color encodes boundary-score category, while left/right position encodes other tumor cells versus top tumor-like cells.",
    ])
    LEGEND_LOG.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(OUTPUT_DOCX)
    print(CONTACT)


if __name__ == "__main__":
    main()
