#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import textwrap
from pathlib import Path
from typing import Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Circle, PathPatch, Rectangle
from matplotlib.path import Path as MplPath
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent


def find_source_root() -> Path:
    candidates = [
        SCRIPT_DIR.parents[2] / "02_source_data",
        SCRIPT_DIR.parents[3] / "GitHub_Term_Revised_Package" / "02_source_data",
        SCRIPT_DIR.parents[1] / "02_source_data",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not locate 02_source_data from CSRM figure script directory")


SOURCE_ROOT = find_source_root()
PROJECT_ROOT = SOURCE_ROOT.parent
OUT_ROOT = SCRIPT_DIR / "outputs"
SVG_DIR = OUT_ROOT / "svg"
PDF_DIR = OUT_ROOT / "pdf"
PNG_DIR = OUT_ROOT / "png"
SOURCE_MAP_DIR = OUT_ROOT / "source_maps"
QC_DIR = OUT_ROOT / "qc"

MM_PER_INCH = 25.4
FIG_WIDTH_MM = 180

PALETTE = {
    "ink": "#111827",
    "muted": "#5F6673",
    "grid": "#D8DEE8",
    "matrix": "#173B63",
    "adult_repair": "#6F8798",
    "embryonic_reactivation": "#D9903D",
    "salamander_blastema": "#3E8F63",
    "salamander_intact": "#7A65A8",
    "tumour_like": "#B85C5C",
    "failed_phi": "#9B6A6A",
    "background": "#FFFFFF",
    "soft": "#F7F9FC",
}

REGIME_ORDER = [
    "adult_repair",
    "embryonic_reactivation",
    "salamander_blastema",
    "salamander_intact",
]

REGIME_LABELS = {
    "adult_repair": "adult repair",
    "embryonic_reactivation": "embryonic\nreactivation",
    "salamander_blastema": "salamander\nblastema",
    "salamander_intact": "salamander\nintact",
    "tumour_like": "tumour-like\nplasticity",
    "mammalian_inflammatory_repair": "mammalian\nrepair",
    "salamander_blastema_reactivation": "salamander\nblastema",
    "salamander_intact_reference": "salamander\nintact",
}

PZ_COLS = [f"P_Z_{r}" for r in REGIME_ORDER]
REGIME_COLORS = {r: PALETTE[r] for r in REGIME_ORDER}


def ensure_dirs() -> None:
    for path in [SVG_DIR, PDF_DIR, PNG_DIR, SOURCE_MAP_DIR, QC_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def setup_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
            "font.size": 7.5,
            "axes.linewidth": 0.6,
            "axes.edgecolor": PALETTE["ink"],
            "axes.labelcolor": PALETTE["ink"],
            "xtick.color": PALETTE["muted"],
            "ytick.color": PALETTE["muted"],
            "xtick.major.width": 0.5,
            "ytick.major.width": 0.5,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.facecolor": PALETTE["background"],
            "axes.facecolor": PALETTE["background"],
            "savefig.facecolor": PALETTE["background"],
            "savefig.transparent": False,
        }
    )


def fig_size(width_mm: float = FIG_WIDTH_MM, height_mm: float = 100) -> tuple[float, float]:
    return width_mm / MM_PER_INCH, height_mm / MM_PER_INCH


def make_figure(height_mm: float, width_mm: float = FIG_WIDTH_MM):
    setup_style()
    fig = plt.figure(figsize=fig_size(width_mm, height_mm), constrained_layout=False)
    return fig


def export_figure(fig, stem: str) -> dict[str, str]:
    ensure_dirs()
    svg_path = SVG_DIR / f"{stem}.svg"
    pdf_path = PDF_DIR / f"{stem}.pdf"
    png_path = PNG_DIR / f"{stem}_600dpi.png"
    fig.savefig(svg_path, format="svg", bbox_inches="tight", pad_inches=0.03)
    fig.savefig(pdf_path, format="pdf", bbox_inches="tight", pad_inches=0.03)
    fig.savefig(png_path, format="png", dpi=600, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    return {"svg": str(svg_path), "pdf": str(pdf_path), "png": str(png_path)}


def read_tsv(relative: str) -> pd.DataFrame:
    path = SOURCE_ROOT / relative
    if not path.exists():
        raise FileNotFoundError(f"Missing source table: {path}")
    return pd.read_csv(path, sep="\t")


def require_columns(df: pd.DataFrame, cols: Iterable[str], source: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{source} missing columns: {missing}")


def write_source_map(figure: str, rows: list[dict[str, object]]) -> Path:
    ensure_dirs()
    fields = [
        "figure",
        "panel",
        "source_file",
        "columns_used",
        "row_count",
        "aggregation",
        "transformation",
        "new_statistics_generated",
        "notes",
    ]
    path = SOURCE_MAP_DIR / f"{figure}_source_map.tsv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            payload = {field: row.get(field, "") for field in fields}
            payload["figure"] = figure
            writer.writerow(payload)
    return path


def source_row(panel: str, source_file: str, columns: Iterable[str], row_count: int, aggregation: str, transformation: str, notes: str = "") -> dict[str, object]:
    return {
        "panel": panel,
        "source_file": source_file,
        "columns_used": ",".join(columns),
        "row_count": row_count,
        "aggregation": aggregation,
        "transformation": transformation,
        "new_statistics_generated": "NO",
        "notes": notes,
    }


def add_panel_label(ax, label: str, x: float = -0.04, y: float = 1.04) -> None:
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="top", fontsize=10.5, fontweight="bold", color=PALETTE["ink"])


def add_subtitle(ax, text: str) -> None:
    ax.set_title(text, loc="left", fontsize=8.8, color=PALETTE["ink"], pad=4, fontweight="bold")


def clean_axes(ax, grid: bool = False) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if grid:
        ax.grid(True, color=PALETTE["grid"], linewidth=0.45, alpha=0.8)
        ax.set_axisbelow(True)


def off_axis(ax) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def draw_wrapped(ax, x: float, y: float, text: str, width: int = 24, size: float = 7.5, color: str | None = None, ha: str = "center", va: str = "center", weight: str = "normal") -> None:
    ax.text(x, y, "\n".join(textwrap.wrap(text, width=width)), ha=ha, va=va, fontsize=size, color=color or PALETTE["ink"], fontweight=weight)


def failed_scalar_axis(ax, x: float, y: float, w: float, label: str = "Phi scalar axis", rejected: bool = True) -> None:
    ax.plot([x, x + w], [y, y], color=PALETTE["failed_phi"], lw=0.9)
    ax.plot([x, x], [y - 0.015, y + 0.015], color=PALETTE["failed_phi"], lw=0.7)
    ax.plot([x + w, x + w], [y - 0.015, y + 0.015], color=PALETTE["failed_phi"], lw=0.7)
    ax.text(x + w / 2, y + 0.035, label, ha="center", va="bottom", fontsize=7.3, color=PALETTE["failed_phi"], fontweight="bold")
    if rejected:
        ax.plot([x + 0.08 * w, x + 0.92 * w], [y - 0.045, y + 0.045], color=PALETTE["failed_phi"], lw=1.1)
        ax.plot([x + 0.08 * w, x + 0.92 * w], [y + 0.045, y - 0.045], color=PALETTE["failed_phi"], lw=1.1)


def posterior_ribbon(ax, x: float, y: float, w: float, h: float, values: Iterable[float] | None = None, labels: bool = False) -> None:
    vals = np.array(list(values) if values is not None else [1, 1, 1, 1], dtype=float)
    vals = vals / vals.sum() if vals.sum() > 0 else np.ones(4) / 4
    x0 = x
    for regime, val in zip(REGIME_ORDER, vals):
        ww = w * float(val)
        ax.add_patch(Rectangle((x0, y), ww, h, facecolor=REGIME_COLORS[regime], edgecolor="white", linewidth=0.45))
        if labels and ww > 0.08:
            ax.text(x0 + ww / 2, y + h / 2, REGIME_LABELS[regime], ha="center", va="center", fontsize=5.8, color="white", fontweight="bold")
        x0 += ww
    ax.add_patch(Rectangle((x, y), w, h, facecolor="none", edgecolor=PALETTE["matrix"], linewidth=0.7))


def matrix_glyph(ax, x: float, y: float, w: float, h: float, values: np.ndarray | None = None, row_labels: list[str] | None = None, label: str = "M_ik = P(Z=k | S_i, W_GRN)") -> None:
    if values is None:
        values = np.array(
            [
                [0.55, 0.25, 0.05, 0.15],
                [0.20, 0.45, 0.20, 0.15],
                [0.08, 0.25, 0.55, 0.12],
                [0.16, 0.18, 0.11, 0.55],
                [0.25, 0.25, 0.25, 0.25],
            ]
        )
    values = np.asarray(values, float)
    n_rows, n_cols = values.shape
    cell_w = w / n_cols
    cell_h = h / n_rows
    for j, regime in enumerate(REGIME_ORDER[:n_cols]):
        ax.add_patch(Rectangle((x + j * cell_w, y + h + 0.01), cell_w, 0.025, facecolor=REGIME_COLORS[regime], edgecolor="white", linewidth=0.35))
    for i in range(n_rows):
        for j in range(n_cols):
            alpha = 0.12 + 0.75 * float(np.clip(values[i, j], 0, 1))
            ax.add_patch(Rectangle((x + j * cell_w, y + (n_rows - 1 - i) * cell_h), cell_w, cell_h, facecolor=PALETTE["matrix"], alpha=alpha, edgecolor="white", linewidth=0.4))
    ax.add_patch(Rectangle((x, y), w, h, facecolor="none", edgecolor=PALETTE["matrix"], linewidth=0.8))
    ax.text(x + w / 2, y - 0.035, label, ha="center", va="top", fontsize=7.2, color=PALETTE["matrix"], fontweight="bold")
    if row_labels:
        for i, row in enumerate(row_labels[:n_rows]):
            ax.text(x - 0.012, y + (n_rows - 0.5 - i) * cell_h, row, ha="right", va="center", fontsize=5.8, color=PALETTE["muted"])


def boundary_branch(ax, x: float, y: float, w: float, h: float) -> None:
    verts = [(x, y + h * 0.5), (x + w * 0.35, y + h * 0.8), (x + w * 0.72, y + h * 0.77), (x + w, y + h * 0.65)]
    codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4]
    ax.add_patch(PathPatch(MplPath(verts, codes), facecolor="none", edgecolor=PALETTE["tumour_like"], lw=1.1))
    ax.add_patch(Circle((x + w, y + h * 0.65), 0.012, facecolor=PALETTE["tumour_like"], edgecolor="none"))
    ax.text(x + w + 0.015, y + h * 0.65, "boundary branch", ha="left", va="center", fontsize=7.2, color=PALETTE["tumour_like"], fontweight="bold")


def regime_color_for_name(name: str) -> str:
    normalized = str(name)
    normalized = normalized.replace("latent_regime_", "")
    if normalized in REGIME_COLORS:
        return REGIME_COLORS[normalized]
    if "adult" in normalized or "mammalian" in normalized:
        return PALETTE["adult_repair"]
    if "embryonic" in normalized:
        return PALETTE["embryonic_reactivation"]
    if "blastema" in normalized:
        return PALETTE["salamander_blastema"]
    if "intact" in normalized:
        return PALETTE["salamander_intact"]
    return PALETTE["muted"]


def readable_label(name: str) -> str:
    return REGIME_LABELS.get(str(name), str(name).replace("_", " "))


def posterior_entropy(df: pd.DataFrame) -> pd.Series:
    p = df[PZ_COLS].clip(lower=1e-12).to_numpy(float)
    ent = -(p * np.log(p)).sum(axis=1) / math.log(len(PZ_COLS))
    return pd.Series(ent, index=df.index)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def color_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))


def tumour_cmap():
    return LinearSegmentedColormap.from_list("csrm_tumour", ["#F3F4F6", PALETTE["tumour_like"]])


def phi_cmap():
    return LinearSegmentedColormap.from_list("csrm_phi", ["#F4EEEE", PALETTE["failed_phi"]])


def minmax(values: np.ndarray | pd.Series) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    lo = np.nanmin(arr)
    hi = np.nanmax(arr)
    if hi - lo < 1e-12:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)
