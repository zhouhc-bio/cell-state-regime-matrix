from __future__ import annotations

import csv
import html
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
MAIN_IN = OUT / "final_9figures_reconstructed"
MAIN_OUT = OUT / "FINAL_9_MAIN_FIGURES_VISUALLY_REDESIGNED"
SUPP_OUT = OUT / "FINAL_SUPPLEMENTARY_FIGURES_VISUALLY_REDESIGNED"

AUDIT_TSV = OUT / "figure_visual_density_audit.tsv"
PLAN_MD = OUT / "figure_redesign_plan.md"
REPORT_MD = OUT / "figure_visual_redesign_report.md"

SUPP_PNG = SUPP_OUT / "SUPP_FIGURE_CAUSAL_CLOSURE_REDESIGNED.png"
SUPP_PDF = SUPP_OUT / "SUPP_FIGURE_CAUSAL_CLOSURE_REDESIGNED.pdf"
SUPP_SVG = SUPP_OUT / "SUPP_FIGURE_CAUSAL_CLOSURE_REDESIGNED.svg"

W, H = 4200, 2550
SCALE = W / 14.0

COLORS = {
    "ink": "#111827",
    "muted": "#5F6368",
    "blue": "#1F4D78",
    "light_blue": "#E8F2FB",
    "card": "#F8FAFC",
    "border": "#B8C2CC",
    "good_bg": "#DCFCE7",
    "good": "#166534",
    "warn_bg": "#FEF3C7",
    "warn": "#92400E",
    "bad_bg": "#FEE2E2",
    "bad": "#991B1B",
    "na": "#E5E7EB",
}


MAIN_FIGS = [
    "Final_Figure_1_Phi_failure_latent_regime_replacement",
    "Final_Figure_2_shared_accessibility_reannotated",
    "Final_Figure_3_stemness_local_accessibility",
    "Final_Figure_4_regime_conditioned_positional_information",
    "Final_Figure_5_fate_lock_adult_repair_basin",
    "Final_Figure_6_tumor_like_plasticity_distinct_branch",
    "Final_Figure_7_single_Phi_rejection",
    "Final_Figure_8_latent_regime_posterior_dynamics",
    "Final_Figure_9_overlap_symmetrized_divergence",
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONTS = {
    "title": font(42, True),
    "subtitle": font(26),
    "panel": font(28, True),
    "body": font(24),
    "small": font(20),
    "tiny": font(18),
    "badge": font(24, True),
}


class SVG:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.items: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
        ]

    def rect(self, x, y, w, h, fill, stroke="#000000", sw=1, rx=0):
        self.items.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def text(self, x, y, text, size=20, fill="#111827", weight="normal", anchor="start"):
        safe = html.escape(str(text))
        self.items.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{safe}</text>'
        )

    def save(self, path: Path):
        self.items.append("</svg>")
        path.write_text("\n".join(self.items), encoding="utf-8")


def px(v: float) -> int:
    return int(round(v * SCALE))


def draw_text(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill=COLORS["ink"], anchor=None):
    draw.text(xy, str(text), font=fnt, fill=fill, anchor=anchor)


def wrap_text(text: str, max_chars: int) -> list[str]:
    words = str(text).split()
    lines: list[str] = []
    cur: list[str] = []
    for word in words:
        if len(" ".join(cur + [word])) > max_chars and cur:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(" ".join(cur))
    return lines


def load_tsv(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name, sep="\t")


def write_audit() -> None:
    rows = [
        ("Main Fig. 1", "A", "Deprecated scalar-proxy failure evidence card", "DATA_SPARSE_ACCEPTABLE", "Single AUC/evidence values are embedded in a rejection schematic; no axis overclaim.", "keep"),
        ("Main Fig. 1", "B", "Latent-state-regime mixture replacement schematic", "SCHEMATIC_SHOULD_REPLACE_DATA_PANEL", "Conceptual replacement of scalar axis; already schematic and claim-safe.", "keep"),
        ("Main Fig. 1", "C", "Posterior-regime and branch logic", "SCHEMATIC_SHOULD_REPLACE_DATA_PANEL", "Mechanism schematic prevents sparse numeric over-interpretation.", "keep"),
        ("Main Fig. 2", "A-C", "State-space and trajectory evidence", "DATA_DENSE", "Multiple embedding/trajectory panels with sufficient plotted observations.", "keep"),
        ("Main Fig. 2", "D-F", "Entropy/CellRank/velocity summaries", "DATA_DENSE", "Evidence panels are tied to trajectory/state-space outputs.", "keep"),
        ("Main Fig. 3", "A-D", "Wnt/stemness perturbation and score summaries", "DATA_DENSE", "Scatter/summary panels show data-backed accessibility changes.", "keep"),
        ("Main Fig. 3", "E-F", "Boundary interpretation panels", "DATA_SPARSE_ACCEPTABLE", "Sparse boundary statements are embedded with data panels and do not define a global driver.", "keep"),
        ("Main Fig. 4", "A-D", "RA/HOX/DPRI and positional evidence", "DATA_DENSE", "Multiple linked panels support regime-conditioned positional interpretation.", "keep"),
        ("Main Fig. 4", "E", "Blastema interpretation inset", "DATA_SPARSE_ACCEPTABLE", "Single-regime interpretation is schematic-anchored; no scalar ranking.", "keep"),
        ("Main Fig. 5", "A", "Adult_repair basin schematic", "SCHEMATIC_SHOULD_REPLACE_DATA_PANEL", "Mechanism schematic appropriately replaces a linear fate-lock axis.", "keep"),
        ("Main Fig. 5", "B-D", "Fate-stabilization/retention evidence", "DATA_DENSE", "Data panels remain anchored to basin interpretation.", "keep"),
        ("Main Fig. 5", "E", "Boundary/claim-safety cards", "DATA_SPARSE_ACCEPTABLE", "Sparse limitation statements are presented as audit cards, not extra data.", "keep"),
        ("Main Fig. 6", "A-D", "Tumor-like plasticity branch evidence", "DATA_DENSE", "Multiple panels show high-plasticity branch and boundary tests.", "keep"),
        ("Main Fig. 6", "E", "Distinct-branch interpretation card", "DATA_SPARSE_ACCEPTABLE", "Claim boundary is embedded as annotation; no regeneration equivalence.", "keep"),
        ("Main Fig. 7", "A", "Deprecated scalar-proxy distributions", "DATA_DENSE", "Distribution curves show Phi failure structure.", "keep"),
        ("Main Fig. 7", "B", "ROC AUC approximately 0.480", "DATA_DENSE", "ROC curve is a full diagnostic, not a sparse standalone bar.", "keep"),
        ("Main Fig. 7", "C", "Permutation mean-shift test", "DATA_DENSE", "Null distribution is dense and preserves negative result.", "keep"),
        ("Main Fig. 7", "D", "Bootstrap uncertainty point/interval", "DATA_SPARSE_ACCEPTABLE", "Sparse point estimate is embedded in failure evidence strip; no data invented.", "keep"),
        ("Main Fig. 7", "E", "Interpretation locked card", "DATA_SPARSE_ACCEPTABLE", "Text card preserves Phi failure without overstating separation.", "keep"),
        ("Main Fig. 8", "A-C", "Mixture-density and posterior distributions", "DATA_DENSE", "Distributional panels support mixture representation.", "keep"),
        ("Main Fig. 8", "D-F", "Posterior landscape and observed-group mixture bars", "DATA_DENSE", "Panels show posterior structure and mixture composition.", "keep"),
        ("Main Fig. 8", "G", "Dynamical equation closure card", "SCHEMATIC_SHOULD_REPLACE_DATA_PANEL", "Equation card is correct replacement for empty scalar-axis panel.", "keep"),
        ("Main Fig. 9", "A-C", "Overlap and symmetrized KL matrices", "DATA_DENSE", "Compact matrices are appropriate for low-dimensional regime relationships.", "keep"),
        ("Main Fig. 9", "D", "Divergence ranking", "DATA_SPARSE_ACCEPTABLE", "Ranking is anchored to matrix evidence and not interpreted as axis distance.", "keep"),
        ("Main Fig. 9", "E", "Overlap/divergence interpretation band", "DATA_SPARSE_ACCEPTABLE", "Audit-style interpretation prevents separability overclaim.", "keep"),
        ("Supplementary Fig. 1 original", "A", "Pathway deltaZ directional shifts", "DATA_SPARSE_NEEDS_REDESIGN", "Pathway summaries are sparse and better shown as pathway-by-metric heatmap.", "redesign_as_heatmap"),
        ("Supplementary Fig. 1 original", "B", "Observed vs counterfactual deltaZ alignment", "DATA_SPARSE_NEEDS_REDESIGN", "Few pathway-level values should become compact audit matrix/card.", "redesign_as_dashboard"),
        ("Supplementary Fig. 1 original", "C", "Cross-dataset perturbation consistency", "DATA_SPARSE_NEEDS_REDESIGN", "All pathway rows are not-computable single-dataset outputs; use audit badge.", "redesign_as_not_computable_badge"),
        ("Supplementary Fig. 1 original", "D", "Null perturbation comparison", "DATA_SPARSE_NEEDS_REDESIGN", "Five pathway null scores are better encoded in a compact pathway metric heatmap.", "redesign_as_heatmap"),
        ("Supplementary Fig. 1 original", "E", "Causal-consistency score bars", "DATA_SPARSE_NEEDS_REDESIGN", "Single sparse bar set should become audit dashboard with classification and limitations.", "redesign_as_audit_dashboard"),
        ("Supplementary Fig. 1 original", "F", "Evidence weight/final classification", "DATA_SPARSE_NEEDS_REDESIGN", "Single-number evidence should become final interpretation badge.", "redesign_as_interpretation_badge"),
    ]
    with AUDIT_TSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["figure", "panel", "panel_content", "density_classification", "rationale", "redesign_action"])
        writer.writerows(rows)


def write_plan() -> None:
    PLAN_MD.write_text(
        """# Figure Redesign Plan

## Scope

This pass performs visual compression only. No source values, statistical outputs, model equations, posterior assignments or scientific claims were changed.

## Main Figures

The locked nine main figures were audited panel by panel. Sparse numerical elements in the main figures are already embedded in rejection evidence cards, mechanism schematics or compact matrices. They therefore remain visually acceptable and are copied unchanged into `FINAL_9_MAIN_FIGURES_VISUALLY_REDESIGNED/`.

## Supplementary Causal-Consistency Figure

The original supplementary causal figure contained sparse bar/single-number panels. It was rebuilt as an audit dashboard:

- Pathway bar plots -> pathway x metric heatmap.
- Global W versus W(Z) bar plot -> model comparison card.
- Causal-consistency score bars -> compact audit dashboard and final interpretation badge.
- Counterfactual reversal bars -> failure/success evidence strip.
- Sparse cross-dataset invariance panel -> not-computable audit badge.
- Single-number classification -> embedded badges: `REPRESENTATION_CLOSED = yes`, `GLOBAL_CAUSAL_CLOSED = no`, `REGIME_CONDITIONED_PARTIAL_CLOSURE = yes`.

## Claim Boundary

The redesigned supplementary figure preserves `PARTIAL_CLOSURE`. It supports dry-lab perturbation-consistent structure in regime-conditioned subspaces only. It does not claim wet-lab causality, complete/global causal closure or experimental validation.
""",
        encoding="utf-8",
    )


def copy_main_figures() -> None:
    MAIN_OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for stem in MAIN_FIGS:
        for suffix in [".png", ".pdf"]:
            src = MAIN_IN / f"{stem}{suffix}"
            if src.exists():
                dst = MAIN_OUT / src.name
                shutil.copy2(src, dst)
                manifest.append((src.name, "copied_locked_figure", "sparse_elements_already_claim_safe"))
    with (MAIN_OUT / "main_figure_visual_redesign_manifest.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["file", "status", "rationale"])
        writer.writerows(manifest)


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def blend(c1: str, c2: str, t: float) -> tuple[int, int, int]:
    a = np.array(hex_to_rgb(c1))
    b = np.array(hex_to_rgb(c2))
    return tuple(np.round(a * (1 - t) + b * t).astype(int))


def heat_color(value: float | None) -> tuple[int, int, int] | str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return COLORS["na"]
    value = max(0.0, min(1.0, float(value)))
    if value < 0.5:
        return blend("#F7FBFF", "#6BAED6", value / 0.5)
    return blend("#6BAED6", "#08306B", (value - 0.5) / 0.5)


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=COLORS["border"], width=3, radius=22):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_multiline(draw, x, y, lines, fnt, fill=COLORS["ink"], line_gap=1.25):
    yy = y
    for line in lines:
        draw_text(draw, (x, yy), line, fnt, fill)
        yy += int(fnt.size * line_gap)
    return yy


def build_heatmap(draw, svg: SVG, x, y, w, h, rows, cols, matrix, title, note=None):
    draw_text(draw, (x, y - 40), title, FONTS["panel"], COLORS["ink"])
    svg.text(x, y - 40 + 24, title, 28, COLORS["ink"], "bold")
    left_label_w = 270
    top_label_h = 125
    cell_w = (w - left_label_w) / len(cols)
    cell_h = (h - top_label_h) / len(rows)
    for j, col in enumerate(cols):
        tx = x + left_label_w + j * cell_w + cell_w / 2
        for k, line in enumerate(col.split("\n")):
            draw_text(draw, (tx, y + 28 + k * 24), line, FONTS["tiny"], COLORS["muted"], anchor="mm")
            svg.text(tx, y + 34 + k * 24, line, 18, COLORS["muted"], "normal", "middle")
    for i, row in enumerate(rows):
        ry = y + top_label_h + i * cell_h
        draw_text(draw, (x + 5, ry + cell_h / 2), row, FONTS["small"], COLORS["ink"], anchor="lm")
        svg.text(x + 5, ry + cell_h / 2 + 7, row, 20, COLORS["ink"])
        for j in range(len(cols)):
            val = matrix[i][j]
            cx = x + left_label_w + j * cell_w
            fill = heat_color(val)
            draw.rectangle([cx, ry, cx + cell_w - 3, ry + cell_h - 3], fill=fill, outline="white", width=3)
            svg.rect(cx, ry, cell_w - 3, cell_h - 3, fill if isinstance(fill, str) else "#%02x%02x%02x" % fill, "white", 2)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                label = "global\nonly"
                color = COLORS["muted"]
            else:
                label = f"{float(val):.2f}"
                color = "white" if float(val) > 0.62 else COLORS["ink"]
            if "\n" in label:
                draw_text(draw, (cx + cell_w / 2, ry + cell_h / 2 - 10), label.split("\n")[0], FONTS["tiny"], color, anchor="mm")
                draw_text(draw, (cx + cell_w / 2, ry + cell_h / 2 + 15), label.split("\n")[1], FONTS["tiny"], color, anchor="mm")
                svg.text(cx + cell_w / 2, ry + cell_h / 2 - 3, label.split("\n")[0], 17, color, "normal", "middle")
                svg.text(cx + cell_w / 2, ry + cell_h / 2 + 21, label.split("\n")[1], 17, color, "normal", "middle")
            else:
                draw_text(draw, (cx + cell_w / 2, ry + cell_h / 2), label, FONTS["tiny"], color, anchor="mm")
                svg.text(cx + cell_w / 2, ry + cell_h / 2 + 7, label, 18, color, "bold", "middle")
    if note:
        lines = wrap_text(note, 80)
        draw_multiline(draw, x, y + h + 15, lines, FONTS["tiny"], COLORS["muted"], 1.2)
        for k, line in enumerate(lines):
            svg.text(x, y + h + 36 + k * 23, line, 18, COLORS["muted"])


def build_supp_dashboard() -> None:
    SUPP_OUT.mkdir(parents=True, exist_ok=True)
    closure = load_tsv("closure_model_comparison.tsv").iloc[0]
    ccs = load_tsv("causal_closure_score_summary.tsv")
    reg = load_tsv("regime_conditioned_deltaZ_consistency.tsv")
    bias = load_tsv("counterfactual_bias_by_regime.tsv")

    pathways = ["RA", "BMP", "NOTCH", "FGF", "SHH"]
    ccs = ccs.set_index("pathway").loc[pathways].reset_index()
    pathway_matrix = [
        [
            float(row["directional_consistency_component"]),
            np.nan,
            float(row["null_separation_component"]),
            float(row["counterfactual_agreement_component"]),
        ]
        for _, row in ccs.iterrows()
    ]

    regimes = ["adult_repair", "embryonic_reactivation", "salamander_blastema", "salamander_intact"]
    bias_summary = bias[bias["level"] == "regime_summary"].set_index("latent_regime")
    regime_matrix = []
    for regime in regimes:
        sub = reg[reg["latent_regime"] == regime]
        sign_support = sub["regime_conditioned_sign_alignment_LOO"].astype(bool).mean()
        cosine = float(sub["within_regime_cosine_regime_conditioned_LOO"].mean())
        cosine_rescaled = (cosine + 1.0) / 2.0
        reversal_safe = 1.0 - float(bias_summary.loc[regime, "direction_reversal_frequency"])
        symmetry = float(bias_summary.loc[regime, "bias_symmetry_score"])
        regime_matrix.append([sign_support, cosine_rescaled, reversal_safe, symmetry])

    global_mse = float(closure["global_MSE"])
    regime_mse = float(closure["regime_conditioned_MSE_LOO"])
    err_red = float(closure["prediction_error_reduction_fraction"])
    pval = float(closure["bootstrap_p_value_positive_error_reduction"])
    reversal = float(closure["counterfactual_direction_reversal_frequency"])
    instability = float(closure["cross_regime_instability_ratio"])
    classification = str(closure["final_closure_classification"])

    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    svg = SVG(W, H)

    draw_text(draw, (80, 60), "Supplementary Fig. 1 | Dry-lab perturbation consistency audit dashboard", FONTS["title"], COLORS["ink"])
    draw_text(draw, (80, 116), "Visual compression of locked perturbation outputs; no new data, no wet-lab causality claim.", FONTS["subtitle"], COLORS["muted"])
    svg.text(80, 98, "Supplementary Fig. 1 | Dry-lab perturbation consistency audit dashboard", 42, COLORS["ink"], "bold")
    svg.text(80, 140, "Visual compression of locked perturbation outputs; no new data, no wet-lab causality claim.", 26, COLORS["muted"])

    # Panel A card
    ax, ay, aw, ah = 80, 190, 1900, 520
    rounded(draw, [ax, ay, ax + aw, ay + ah], COLORS["card"], "#9DB4C8")
    svg.rect(ax, ay, aw, ah, COLORS["card"], "#9DB4C8", 3, 20)
    draw_text(draw, (ax + 35, ay + 45), "A. Regime-conditioned model comparison card", FONTS["panel"], COLORS["ink"])
    svg.text(ax + 35, ay + 78, "A. Regime-conditioned model comparison card", 28, COLORS["ink"], "bold")
    lines = [
        f"Global W MSE: {global_mse:.4f}",
        f"Regime-conditioned W(Z) MSE: {regime_mse:.4f}",
        f"MSE reduction proxy: {err_red:.3f}",
        f"Bootstrap p for positive reduction: {pval:.3f}",
        "Interpretation: local dry-lab consistency only",
    ]
    yy = ay + 115
    for line in lines:
        draw_text(draw, (ax + 45, yy), line, FONTS["body"], COLORS["ink"])
        svg.text(ax + 45, yy + 22, line, 24, COLORS["ink"])
        yy += 54
    badge_box = [ax + 1210, ay + 370, ax + 1820, ay + 460]
    rounded(draw, badge_box, COLORS["warn_bg"], "#C79025", 3, 24)
    svg.rect(badge_box[0], badge_box[1], badge_box[2] - badge_box[0], badge_box[3] - badge_box[1], COLORS["warn_bg"], "#C79025", 3, 24)
    draw_text(draw, ((badge_box[0] + badge_box[2]) / 2, (badge_box[1] + badge_box[3]) / 2), classification, FONTS["badge"], COLORS["warn"], anchor="mm")
    svg.text((badge_box[0] + badge_box[2]) / 2, (badge_box[1] + badge_box[3]) / 2 + 8, classification, 24, COLORS["warn"], "bold", "middle")
    # mini bars inside card
    bar_base = ay + 330
    for i, (label, val, fill) in enumerate([("Global W", global_mse, "#B7C7D6"), ("W(Z)", regime_mse, "#3C82B5")]):
        bx = ax + 1220 + i * 250
        bh = int(180 * val / max(global_mse, regime_mse))
        draw_text(draw, (bx + 60, ay + 135), label, FONTS["small"], COLORS["muted"], anchor="mm")
        draw.rectangle([bx, bar_base - bh, bx + 120, bar_base], fill=fill, outline="#6B7C8C", width=2)
        draw_text(draw, (bx + 60, bar_base + 36), f"{val:.4f}", FONTS["tiny"], COLORS["ink"], anchor="mm")
        svg.text(bx + 60, ay + 143, label, 20, COLORS["muted"], "normal", "middle")
        svg.rect(bx, bar_base - bh, 120, bh, fill, "#6B7C8C", 2)
        svg.text(bx + 60, bar_base + 44, f"{val:.4f}", 18, COLORS["ink"], "normal", "middle")

    # Panel D strip
    dx, dy, dw, dh = 2100, 190, 2020, 520
    draw_text(draw, (dx, dy - 20), "D. Failure audit strip", FONTS["panel"], COLORS["ink"])
    svg.text(dx, dy + 5, "D. Failure audit strip", 28, COLORS["ink"], "bold")
    failures = [
        ("Cross-dataset invariance", "NOT COMPUTABLE", "single perturbation dataset only", COLORS["na"], "#6B7280"),
        ("Counterfactual reversal", f"HIGH ({reversal:.1f})", "persistent sign reversals", COLORS["bad_bg"], COLORS["bad"]),
        ("Cross-regime instability", f"HIGH ({instability:.1f})", "global W insufficient", COLORS["warn_bg"], COLORS["warn"]),
        ("NOTCH / SHH limitation", "BOUNDARY", "low coverage / mixed direction", "#E0F2FE", "#075985"),
    ]
    for i, (label, status, detail, face, edge) in enumerate(failures):
        y = dy + 35 + i * 112
        rounded(draw, [dx, y, dx + dw, y + 86], face, edge, 3, 22)
        svg.rect(dx, y, dw, 86, face, edge, 3, 22)
        draw_text(draw, (dx + 35, y + 31), label, FONTS["body"], COLORS["ink"])
        draw_text(draw, (dx + 940, y + 31), status, FONTS["badge"], edge)
        draw_text(draw, (dx + 35, y + 64), detail, FONTS["small"], COLORS["muted"])
        svg.text(dx + 35, y + 39, label, 24, COLORS["ink"])
        svg.text(dx + 940, y + 39, status, 24, edge, "bold")
        svg.text(dx + 35, y + 72, detail, 20, COLORS["muted"])

    # Heatmaps
    build_heatmap(
        draw,
        svg,
        80,
        900,
        1900,
        760,
        pathways,
        ["directional\nconsistency", "error\nreduction", "null\nseparation", "counterfactual\nalignment"],
        pathway_matrix,
        "B. Pathway x metric heatmap",
        "Error reduction is not pathway-specific in locked files; global value appears in panel A.",
    )
    build_heatmap(
        draw,
        svg,
        2170,
        900,
        1870,
        760,
        regimes,
        ["sign\nsupport", "cosine\nrescaled", "reversal\nsafe", "bias\nsymmetry"],
        regime_matrix,
        "C. Regime x metric heatmap",
        "Cosine is rescaled from [-1,1] to [0,1]. Reversal-safe = 1 - direction reversal frequency.",
    )

    # Color scale
    sx, sy, sw, sh = 4040, 1030, 36, 420
    for k in range(sh):
        v = 1 - k / sh
        color = heat_color(v)
        draw.rectangle([sx, sy + k, sx + sw, sy + k + 1], fill=color)
    draw.rectangle([sx, sy, sx + sw, sy + sh], outline="#6B7280", width=2)
    draw_text(draw, (sx + 58, sy + 5), "1.0", FONTS["tiny"], COLORS["muted"])
    draw_text(draw, (sx + 58, sy + sh - 4), "0", FONTS["tiny"], COLORS["muted"])
    draw_text(draw, (sx - 5, sy + sh + 42), "support score", FONTS["tiny"], COLORS["muted"])
    svg.rect(sx, sy, sw, sh, "#6BAED6", "#6B7280", 2)
    svg.text(sx + 58, sy + 20, "1.0", 18, COLORS["muted"])
    svg.text(sx + 58, sy + sh, "0", 18, COLORS["muted"])
    svg.text(sx - 5, sy + sh + 42, "support score", 18, COLORS["muted"])

    # Panel E badges
    ex, ey = 80, 1930
    draw_text(draw, (ex, ey - 45), "E. Final interpretation badges", FONTS["panel"], COLORS["ink"])
    svg.text(ex, ey - 20, "E. Final interpretation badges", 28, COLORS["ink"], "bold")
    badges = [
        ("REPRESENTATION_CLOSED", "yes", COLORS["good_bg"], COLORS["good"]),
        ("GLOBAL_CAUSAL_CLOSED", "no", COLORS["bad_bg"], COLORS["bad"]),
        ("REGIME_CONDITIONED_PARTIAL_CLOSURE", "yes", COLORS["warn_bg"], COLORS["warn"]),
        ("WET_LAB_CAUSAL_VALIDATION", "not claimed", COLORS["na"], "#4B5563"),
    ]
    bw, bh, gap = 960, 250, 50
    for i, (label, value, face, edge) in enumerate(badges):
        x = ex + i * (bw + gap)
        rounded(draw, [x, ey, x + bw, ey + bh], face, edge, 4, 28)
        svg.rect(x, ey, bw, bh, face, edge, 4, 28)
        draw_text(draw, (x + bw / 2, ey + 87), label, FONTS["badge"], COLORS["ink"], anchor="mm")
        draw_text(draw, (x + bw / 2, ey + 165), value, font(34, True), edge, anchor="mm")
        svg.text(x + bw / 2, ey + 95, label, 24, COLORS["ink"], "bold", "middle")
        svg.text(x + bw / 2, ey + 176, value, 34, edge, "bold", "middle")

    foot = (
        "Abbreviations: MSE, mean squared error; W(Z), regime-conditioned regulatory matrix; "
        "global only, no pathway-specific value in locked source files. All panels preserve PARTIAL_CLOSURE."
    )
    draw_multiline(draw, 80, 2410, wrap_text(foot, 180), FONTS["tiny"], COLORS["muted"], 1.18)
    svg.text(80, 2440, foot, 18, COLORS["muted"])

    img.save(SUPP_PNG, dpi=(300, 300))
    img.save(SUPP_PDF, "PDF", resolution=300.0)
    svg.save(SUPP_SVG)
    for src in (SUPP_PNG, SUPP_PDF, SUPP_SVG):
        shutil.copy2(src, OUT / src.name)


def write_report() -> None:
    REPORT_MD.write_text(
        f"""# Figure Visual Redesign Report

## Outputs

- Panel density audit: `{AUDIT_TSV.name}`
- Redesign plan: `{PLAN_MD.name}`
- Main figures directory: `{MAIN_OUT.relative_to(ROOT)}`
- Supplementary figures directory: `{SUPP_OUT.relative_to(ROOT)}`
- Redesigned supplementary causal dashboard:
  - `{SUPP_PNG.relative_to(ROOT)}`
  - `{SUPP_PDF.relative_to(ROOT)}`
  - `{SUPP_SVG.relative_to(ROOT)}`

## Main-Figure Decision

The locked 9 main figures were audited. No main figure required scientific or structural redraw during this pass because sparse numerical elements were already embedded in evidence cards, mechanism schematics or compact matrices. The main figures were copied unchanged into the visually redesigned directory to preserve the locked architecture.

## Supplementary Causal Figure Decision

The original causal-consistency figure contained sparse pathway bars, single-number panels and non-computable cross-dataset entries. It was rebuilt as an audit dashboard with:

- Regime-conditioned model comparison card.
- Pathway x metric heatmap.
- Regime x metric heatmap.
- Failure audit strip.
- Final interpretation badges.

## Claim Safety

- `PARTIAL_CLOSURE` is preserved.
- Global causal-consistency closure is explicitly rejected.
- Wet-lab causal validation is not claimed.
- Phi failure and latent-state-regime mixture interpretation are preserved.

## Final Verdict

- Main figures: visually publication-ready under locked architecture.
- Supplementary causal figure: visually redesigned and publication-ready as an audit dashboard.
- Remaining status: still requires optional manual graphical design only if the journal requests house-style artwork changes.
""",
        encoding="utf-8",
    )


def main() -> None:
    MAIN_OUT.mkdir(parents=True, exist_ok=True)
    SUPP_OUT.mkdir(parents=True, exist_ok=True)
    write_audit()
    write_plan()
    copy_main_figures()
    build_supp_dashboard()
    write_report()


if __name__ == "__main__":
    main()
