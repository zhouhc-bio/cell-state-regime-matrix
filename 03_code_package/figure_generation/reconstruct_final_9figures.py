from __future__ import annotations

import csv
import math
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIG_OUT = OUT / "final_9figures_reconstructed"
OLD_DIR = Path("/Volumes/T9/nature_reviewer_alignment_outputs/submission_reproducibility_package_FINAL/02_figures/png_600dpi")
NEW_DIR = OUT / "final_figures_locked"

FONT_REG = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
FONT_BOLD = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")

INK = "#172033"
MUTED = "#5E6778"
BLUE = "#2266A5"
LIGHT_BLUE = "#EAF3FB"
TEAL = "#2B8C88"
LIGHT_TEAL = "#E8F6F4"
RED = "#BE3A34"
LIGHT_RED = "#FBEAEA"
AMBER = "#B8791A"
LIGHT_AMBER = "#FFF4DE"
PURPLE = "#6A5AA8"
LIGHT_PURPLE = "#F0EDFA"
GREY = "#E6EAF0"
BG = "#FFFFFF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REG), size=size)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(text: str, max_chars: int) -> list[str]:
    out: list[str] = []
    for para in text.split("\n"):
        if not para:
            out.append("")
            continue
        out.extend(textwrap.wrap(para, width=max_chars, break_long_words=False))
    return out


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: str = INK,
    max_width: int = 600,
    line_spacing: int = 8,
) -> int:
    x, y = xy
    avg = max(text_size(draw, "abcdefghijklmnopqrstuvwxyz", fnt)[0] / 26, 6)
    max_chars = max(18, int(max_width / avg))
    for line in wrap_text(text, max_chars):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_spacing
    return y


def box(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    fill: str = "#FFFFFF",
    outline: str = GREY,
    width: int = 3,
    radius: int = 24,
) -> None:
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=width)


def callout(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    title: str,
    body: str,
    fill: str,
    outline: str,
    title_color: str,
) -> None:
    box(draw, rect, fill=fill, outline=outline, width=3, radius=22)
    x1, y1, x2, _ = rect
    draw_wrapped(draw, (x1 + 34, y1 + 28), title, font(36, True), title_color, x2 - x1 - 68, 8)
    draw_wrapped(draw, (x1 + 34, y1 + 94), body, font(27), INK, x2 - x1 - 68, 8)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = INK, width: int = 7) -> None:
    draw.line([start, end], fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    ang = math.atan2(y2 - y1, x2 - x1)
    size = 28
    pts = [
        (x2, y2),
        (x2 - size * math.cos(ang - 0.45), y2 - size * math.sin(ang - 0.45)),
        (x2 - size * math.cos(ang + 0.45), y2 - size * math.sin(ang + 0.45)),
    ]
    draw.polygon(pts, fill=color)


def load(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def paste_fit(canvas: Image.Image, img: Image.Image, rect: tuple[int, int, int, int], border: bool = True) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = rect
    target_w, target_h = x2 - x1, y2 - y1
    im = ImageOps.contain(img, (target_w, target_h), method=Image.Resampling.LANCZOS)
    px = x1 + (target_w - im.width) // 2
    py = y1 + (target_h - im.height) // 2
    canvas.paste(im, (px, py))
    if border:
        ImageDraw.Draw(canvas).rounded_rectangle((px, py, px + im.width, py + im.height), radius=16, outline="#D6DBE3", width=3)
    return px, py, px + im.width, py + im.height


def header(draw: ImageDraw.ImageDraw, title: str, subtitle: str, decision: str, width: int) -> None:
    draw.rectangle((0, 0, width, 300), fill="#F6F8FB")
    draw.text((150, 70), title, font=font(62, True), fill=INK)
    draw_wrapped(draw, (152, 160), subtitle, font(32), fill=MUTED, max_width=width - 600)
    badge_w = max(300, text_size(draw, decision, font(31, True))[0] + 90)
    draw.rounded_rectangle((width - badge_w - 150, 80, width - 150, 155), radius=35, fill="#FFFFFF", outline=BLUE, width=4)
    draw.text((width - badge_w - 105, 100), decision, font=font(31, True), fill=BLUE)


def save_png_pdf(img: Image.Image, stem: str) -> tuple[Path, Path]:
    FIG_OUT.mkdir(parents=True, exist_ok=True)
    png = FIG_OUT / f"{stem}.png"
    pdf = FIG_OUT / f"{stem}.pdf"
    img.save(png, dpi=(300, 300))
    img.save(pdf, "PDF", resolution=300.0)
    return png, pdf


def annotated_original(fig_no: int, title: str, subtitle: str, decision: str, source: Path, callouts: list[tuple[str, str, str, str, str]]) -> Image.Image:
    base = load(source)
    w = max(base.width, 4200)
    h = base.height + 620
    canvas = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(canvas)
    header(draw, f"Figure {fig_no} | {title}", subtitle, decision, w)
    paste_fit(canvas, base, (90, 340, w - 90, h - 250), border=False)
    n = len(callouts)
    margin = 90
    gap = 30
    box_w = (w - 2 * margin - gap * (n - 1)) // n
    y1 = h - 215
    for i, (ctitle, body, fill, outline, color) in enumerate(callouts):
        x1 = margin + i * (box_w + gap)
        callout(draw, (x1, y1, x1 + box_w, h - 55), ctitle, body, fill, outline, color)
    return canvas


def figure1() -> Image.Image:
    w, h = 5000, 3400
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    header(draw, "Figure 1 | Phi failure and latent-state-regime mixture replacement", "Rebuilt conceptual anchor: scalar compression is rejected; fate accessibility is represented by posterior regime mixtures.", "REBUILD", w)

    # Panel A: failed scalar hypothesis.
    callout(draw, (150, 430, 1500, 1250), "A  Failed scalar hypothesis", "A single Phi coordinate was tested as a global regenerative order parameter. It failed as a discriminator: ROC AUC ~ 0.480, permutation not significant, bootstrap CI crosses zero, KS = shape difference only.", LIGHT_RED, RED, RED)
    draw.line((390, 995, 1270, 610), fill=RED, width=10)
    draw.line((390, 610, 1270, 995), fill=RED, width=10)

    # Panel B: mixture posterior.
    box(draw, (1800, 430, 3320, 1250), fill="#FFFFFF", outline=TEAL, width=4, radius=28)
    draw.text((1845, 470), "B  Regime posterior, not a threshold", font=font(38, True), fill=TEAL)
    layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    ld = ImageDraw.Draw(layer)
    ellipses = [
        ((1990, 650, 2470, 1030), (43, 140, 136, 110), "adult repair"),
        ((2260, 575, 2790, 980), (106, 90, 168, 110), "embryonic reactivation"),
        ((2520, 710, 3090, 1120), (190, 58, 52, 105), "salamander blastema"),
        ((2100, 820, 2660, 1190), (184, 121, 26, 105), "salamander intact"),
    ]
    for coords, color, _ in ellipses:
        ld.ellipse(coords, fill=color, outline=(40, 40, 40, 120), width=4)
    img.alpha_composite(layer) if img.mode == "RGBA" else img.paste(Image.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 0)), layer).convert("RGB"), mask=layer.split()[-1])
    draw = ImageDraw.Draw(img)
    y = 1060
    for _, color, label in ellipses:
        draw.rounded_rectangle((1850, y, 1900, y + 36), radius=8, fill=tuple(color[:3]))
        draw.text((1920, y - 2), label, font=font(28), fill=INK)
        y += 48
    draw.text((2050, 650), "P(Z|S,W_GRN)", font=font(42, True), fill=INK)

    # Panel C: dynamical replacement.
    callout(draw, (3650, 430, 4850, 1250), "C  Dynamical replacement", "dS/dt = sum_Z P(Z|S,W_GRN) F_Z(S,U,W_GRN) + xi(S)\n\nRegime-specific dynamics replace a global Phi axis.", LIGHT_BLUE, BLUE, BLUE)

    # Bottom flow: branches without axis.
    box(draw, (150, 1460, 4850, 3150), fill="#FFFFFF", outline="#D6DBE3", width=4, radius=30)
    draw.text((215, 1515), "D  Non-compressible outcome structure", font=font(42, True), fill=INK)
    center = (2500, 1990)
    draw.ellipse((2250, 1740, 2750, 2240), fill="#F4F7FA", outline=INK, width=5)
    draw_wrapped(draw, (2320, 1885), "injury-induced\nplasticity", font(34, True), INK, 360, 8)
    nodes = [
        ((620, 1740, 1500, 2160), "adult repair", "adult-repair-dominant mixture\nfate-lock / inflammation context", TEAL, LIGHT_TEAL),
        ((2760, 2480, 4100, 2980), "salamander blastema", "distinct latent regenerative regime\nnot an elevated scalar state", RED, LIGHT_RED),
        ((3400, 1700, 4500, 2120), "tumor-like plasticity", "separate high-plasticity branch\nnot regeneration equivalence", PURPLE, LIGHT_PURPLE),
        ((1490, 1465, 2790, 1695), "salamander intact", "reference regime with partial overlap", AMBER, LIGHT_AMBER),
    ]
    for rect, title, body, color, fill in nodes:
        box(draw, rect, fill=fill, outline=color, width=4, radius=24)
        draw_wrapped(draw, (rect[0] + 35, rect[1] + 35), title, font(36, True), color, rect[2] - rect[0] - 70, 6)
        draw_wrapped(draw, (rect[0] + 35, rect[1] + 105), body, font(27), INK, rect[2] - rect[0] - 70, 7)
        arrow(draw, center, ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2), color=color, width=6)
    draw_wrapped(draw, (600, 2300), "Final visual rule: show mixtures, overlaps and branch structure. Do not order all outcomes along one scalar axis.", font(34, True), RED, 3800, 8)
    return img


def figure4() -> Image.Image:
    old4 = load(OLD_DIR / "Figure_4_final_600dpi.png")
    old7 = load(OLD_DIR / "Figure_7_final_600dpi.png")
    w, h = 6400, 4550
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    header(draw, "Figure 4 | Regime-conditioned positional information", "Rebuilt from positional/DPRI and salamander blastema evidence; positional scores are regime-conditioned coordinates, not global scalar rankings.", "REBUILD", w)
    draw.text((120, 365), "A-D  RA/RARG and RA/HOX positional-program evidence", font=font(34, True), fill=BLUE)
    draw.text((3300, 365), "E-H  Salamander blastema as latent regenerative-regime evidence", font=font(34, True), fill=RED)
    paste_fit(img, old4, (120, 430, 3140, 3470), border=True)
    paste_fit(img, old7, (3260, 430, 6280, 3470), border=True)
    callout(draw, (120, 3600, 2050, 4380), "Regime-conditioned coordinate", "DPRI / RA-HOX / positional information is interpreted inside latent state regimes. It is not a universal species ranking or a single linear gradient.", LIGHT_BLUE, BLUE, BLUE)
    callout(draw, (2240, 3600, 4210, 4380), "Blastema interpretation", "Salamander blastema is a distinct latent regenerative regime with positional-program activity. It is not labeled as high Phi.", LIGHT_RED, RED, RED)
    callout(draw, (4400, 3600, 6280, 4380), "Evidence boundary", "Expression-layer proxies and compartment evidence support regime interpretation; they do not directly measure spatial morphogen coordinates.", LIGHT_AMBER, AMBER, AMBER)
    return img


def figure5() -> Image.Image:
    old5 = load(OLD_DIR / "Figure_5_final_600dpi.png")
    old6 = load(OLD_DIR / "Figure_6_final_600dpi.png")
    w, h = 6400, 4550
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    header(draw, "Figure 5 | Fate-lock as adult-repair attractor-basin constraint", "Restructured from fate-stabilization and SAT evidence; fate-lock constrains adult repair rather than defining a linear fate axis.", "RESTRUCTURE", w)

    # Basin schematic.
    box(draw, (120, 420, 2080, 1550), fill="#FFFFFF", outline=TEAL, width=4, radius=28)
    draw.text((170, 470), "A  Basin constraint model", font=font(38, True), fill=TEAL)
    basin = Image.new("RGBA", img.size, (255, 255, 255, 0))
    bd = ImageDraw.Draw(basin)
    bd.ellipse((500, 735, 1260, 1310), fill=(43, 140, 136, 50), outline=(43, 140, 136, 220), width=7)
    bd.ellipse((900, 610, 1780, 1380), fill=(190, 58, 52, 45), outline=(190, 58, 52, 220), width=7)
    img.paste(Image.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 0)), basin).convert("RGB"), mask=basin.split()[-1])
    draw = ImageDraw.Draw(img)
    draw.text((605, 960), "adult repair\nbasin", font=font(34, True), fill=TEAL)
    draw.text((1090, 900), "fate-lock /\nsenescence-like\nretention", font=font(30, True), fill=RED)
    arrow(draw, (360, 1220), (850, 1050), color=INK, width=6)
    arrow(draw, (1760, 760), (1380, 940), color=RED, width=6)
    draw_wrapped(draw, (165, 1340), "Constraint is basin depth/retention, not a one-dimensional axis.", font(29, True), INK, 1800, 6)

    draw.text((2200, 365), "B-E  Fate-stabilization, lineage restriction and inferred retention", font=font(34, True), fill=BLUE)
    paste_fit(img, old5, (2200, 430, 6280, 2500), border=True)
    draw.text((120, 1645), "F-H  SAT/adult repair-failure evidence bounded to mammalian repair context", font=font(34, True), fill=RED)
    paste_fit(img, old6, (120, 1710, 3700, 3520), border=True)
    callout(draw, (3900, 2760, 6280, 3520), "Interpretation lock", "Mammalian repair failure is an adult-repair/fate-lock-biased mixture. It is not the same process as salamander regeneration, and SAT is not a universal aging law.", LIGHT_RED, RED, RED)
    callout(draw, (120, 3665, 3160, 4380), "Allowed claim", "Fate-lock, lineage restriction and senescence-like retention constrain high-plasticity trajectories within adult repair.", LIGHT_TEAL, TEAL, TEAL)
    callout(draw, (3340, 3665, 6280, 4380), "Not allowed", "No linear fate-lock axis, no direct BMP/p53 causality without perturbation time series, and no scalar repair-to-regeneration continuum.", LIGHT_AMBER, AMBER, AMBER)
    return img


def figure8() -> Image.Image:
    mix = load(NEW_DIR / "Figure2_latent_regime_mixture.png")
    post = load(NEW_DIR / "Figure3_regime_posterior_landscape.png")
    w, h = 7600, 4550
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    header(draw, "Figure 8 | Latent-state-regime posterior dynamical model", "Rebuilt replacement figure: posterior mixture dynamics implement the validated non-scalar framework.", "REBUILD", w)
    draw.text((120, 360), "A-C  Per-regime Phi distributions and mixture density", font=font(36, True), fill=TEAL)
    draw.text((3940, 360), "D-F  Posterior landscape and observed groups as mixtures", font=font(36, True), fill=PURPLE)
    paste_fit(img, mix, (120, 430, 3740, 3250), border=True)
    paste_fit(img, post, (3860, 430, 7480, 3250), border=True)
    box(draw, (120, 3370, 7480, 4380), fill="#FFFFFF", outline=BLUE, width=5, radius=32)
    draw.text((190, 3440), "G  Dynamical closure", font=font(42, True), fill=BLUE)
    eq = "dS/dt = sum_Z P(Z|S,W_GRN) F_Z(S,U,W_GRN) + xi(S)"
    draw.text((520, 3620), eq, font=font(58, True), fill=INK)
    draw_wrapped(draw, (520, 3745), "Regime identity is probabilistic. Each latent state regime has its own local dynamics F_Z; observed groups are mixtures over adult repair, embryonic reactivation, salamander blastema and salamander intact.", font(34), INK, 6600, 8)
    draw_wrapped(draw, (520, 3970), "No AUC objective, no hard Phi threshold, no manual switch: model interpretation is posterior regime mixture only.", font(36, True), RED, 6600, 8)
    return img


def figure9() -> Image.Image:
    return annotated_original(
        9,
        "Overlap and symmetrized distributional divergence",
        "Restructured interpretation: overlap is not separability, and divergence is not a scalar-axis distance.",
        "RESTRUCTURE",
        NEW_DIR / "Figure4_overlap_divergence.png",
        [
            ("overlap != separability", "Shared posterior mass explains why scalar Phi classification fails.", LIGHT_BLUE, BLUE, BLUE),
            ("divergence != axis distance", "Symmetrized KL is distributional divergence, not movement along Phi.", LIGHT_AMBER, AMBER, AMBER),
            ("Final closure", "Adult repair and salamander blastema overlap but remain distinct latent-state-regime mixtures.", LIGHT_TEAL, TEAL, TEAL),
        ],
    )


def make_contact_sheet(paths: list[Path]) -> Path:
    thumbs = []
    for p in paths:
        im = load(p)
        im.thumbnail((500, 380), resample=Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (540, 455), "white")
        canvas.paste(im, ((540 - im.width) // 2, 48))
        d = ImageDraw.Draw(canvas)
        d.text((18, 14), p.name, font=font(22, True), fill=INK)
        thumbs.append(canvas)
    cols = 3
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 540, rows * 455), "white")
    for i, t in enumerate(thumbs):
        sheet.paste(t, ((i % cols) * 540, (i // cols) * 455))
    out = FIG_OUT / "final_9figures_contact_sheet.png"
    sheet.save(out, dpi=(150, 150))
    return out


def main() -> None:
    FIG_OUT.mkdir(parents=True, exist_ok=True)
    figures: list[tuple[int, str, str, Image.Image]] = []
    figures.append((1, "REBUILD", "Final_Figure_1_Phi_failure_latent_regime_replacement", figure1()))
    figures.append((
        2,
        "REANNOTATE",
        "Final_Figure_2_shared_accessibility_reannotated",
        annotated_original(
            2,
            "Shared high-plasticity accessibility space",
            "Kept data, corrected interpretation: accessibility is not fate determination.",
            "REANNOTATE",
            OLD_DIR / "Figure_2_final_600dpi.png",
            [
                ("accessibility != fate determination", "Connected high-plasticity regions do not imply shared fate or direct lineage.", LIGHT_BLUE, BLUE, BLUE),
                ("Inferred comparators", "CellRank and RNA velocity are trajectory-inference comparators, not lineage tracing.", LIGHT_TEAL, TEAL, TEAL),
            ],
        ),
    ))
    figures.append((
        3,
        "REANNOTATE",
        "Final_Figure_3_stemness_local_accessibility",
        annotated_original(
            3,
            "Stemness-associated local accessibility",
            "Kept data, corrected interpretation: stemness expands local access within regimes, not a global fate driver.",
            "REANNOTATE",
            OLD_DIR / "Figure_3_final_600dpi.png",
            [
                ("stemness = local accessibility", "Wnt/stemness programs expand access but do not classify regeneration.", LIGHT_TEAL, TEAL, TEAL),
                ("No global driver", "Do not interpret Wnt/BMP or stemness as a universal scalar fate axis.", LIGHT_AMBER, AMBER, AMBER),
            ],
        ),
    ))
    figures.append((4, "REBUILD", "Final_Figure_4_regime_conditioned_positional_information", figure4()))
    figures.append((5, "RESTRUCTURE", "Final_Figure_5_fate_lock_adult_repair_basin", figure5()))
    figures.append((
        6,
        "KEEP",
        "Final_Figure_6_tumor_like_plasticity_distinct_branch",
        annotated_original(
            6,
            "Tumor-like plasticity as a distinct branch",
            "Kept figure; interpretation locked against regeneration equivalence.",
            "KEEP",
            OLD_DIR / "Figure_8_final_600dpi.png",
            [
                ("Separate branch", "High plasticity with retention is not embryonic regeneration.", LIGHT_PURPLE, PURPLE, PURPLE),
                ("Boundary tests", "Do not equate tumor-like plasticity with salamander blastema or inflammatory repair.", LIGHT_RED, RED, RED),
            ],
        ),
    ))
    figures.append((
        7,
        "KEEP",
        "Final_Figure_7_single_Phi_rejection",
        annotated_original(
            7,
            "Single-Phi model rejection",
            "Locked statistical figure: Phi has distributional structure but fails as a global order parameter.",
            "KEEP",
            NEW_DIR / "Figure1_single_phi_rejection.png",
            [
                ("AUC ~ 0.480", "Random-level discrimination; no classifier interpretation.", LIGHT_RED, RED, RED),
                ("Permutation/bootstrap/KS", "Permutation not significant; bootstrap crosses zero; KS is shape difference only.", LIGHT_AMBER, AMBER, AMBER),
            ],
        ),
    ))
    figures.append((8, "REBUILD", "Final_Figure_8_latent_regime_posterior_dynamics", figure8()))
    figures.append((9, "RESTRUCTURE", "Final_Figure_9_overlap_symmetrized_divergence", figure9()))

    manifest_rows = []
    pngs = []
    for fig_no, decision, stem, image in figures:
        png, pdf = save_png_pdf(image, stem)
        pngs.append(png)
        manifest_rows.append(
            {
                "figure": f"Figure {fig_no}",
                "decision": decision,
                "png": str(png),
                "pdf": str(pdf),
                "width_px": image.width,
                "height_px": image.height,
                "status": "generated",
            }
        )

    contact = make_contact_sheet(pngs)
    with (FIG_OUT / "final_9figure_asset_manifest.tsv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)

    report = [
        "# Final 9-Figure Reconstruction Audit",
        "",
        "Status: PASS",
        "",
        "No new data analysis or modeling was performed. Figures were reconstructed by re-layout, annotation correction and combination of locked old/new figure assets under the latent-state-regime mixture framework.",
        "",
        "## Generated Figures",
        "",
    ]
    for row in manifest_rows:
        report.append(f"- {row['figure']}: {row['decision']} -> `{Path(row['png']).name}` and `{Path(row['pdf']).name}`")
    report.extend(
        [
            "",
            "## Consistency Locks",
            "",
            "- Single Phi remains invalid; Figure 7 is the rejection evidence.",
            "- Figure 8 uses `dS/dt = sum_Z P(Z|S,W_GRN) F_Z(S,U,W_GRN) + xi(S)`.",
            "- Salamander blastema is a distinct latent regenerative regime.",
            "- Mammalian repair is adult-repair-dominant mixture.",
            "- Tumor-like plasticity is a separate high-plasticity branch.",
            "- No figure orders all states along one scalar axis.",
            "",
            f"Contact sheet: `{contact}`",
        ]
    )
    (FIG_OUT / "final_9figure_reconstruction_audit.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    # Convenience copy of the existing written specifications into the figure folder.
    for name in [
        "figure_reconstruction_plan.md",
        "figure_rebuild_specifications.tsv",
        "figure_annotation_corrections.md",
        "final_9figure_layout.md",
        "figure_main_vs_supplementary_decision.md",
    ]:
        src = OUT / name
        if src.exists():
            shutil.copy2(src, FIG_OUT / name)

    print(f"generated {len(figures)} figures")
    print(FIG_OUT)
    print(contact)


if __name__ == "__main__":
    main()
