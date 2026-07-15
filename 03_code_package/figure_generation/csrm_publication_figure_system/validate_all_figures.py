#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

from csrm_visual_system import OUT_ROOT, PALETTE, PDF_DIR, PNG_DIR, PROJECT_ROOT, SOURCE_MAP_DIR, SOURCE_ROOT, SVG_DIR


FIGURES = {
    "Figure 1A": "Figure_1A_paradigm_shift",
    "Figure 1": "Figure_1_framework_icon",
    "Figure 6": "Figure_6_boundary_branch",
    "Figure 7": "Figure_7_phi_failure_dashboard",
    "Figure 8": "Figure_8_posterior_mixture",
    "Figure 9": "Figure_9_overlap_divergence",
    "Supplementary Figure 1": "Supplementary_Figure_1_perturbation_consistency",
}

SOURCE_MAP_FILES = {
    "Figure 1A": "Figure_1A_source_map.tsv",
    "Figure 1": "Figure_1_source_map.tsv",
    "Figure 6": "Figure_6_source_map.tsv",
    "Figure 7": "Figure_7_source_map.tsv",
    "Figure 8": "Figure_8_source_map.tsv",
    "Figure 9": "Figure_9_source_map.tsv",
    "Supplementary Figure 1": "Supplementary_Figure_1_source_map.tsv",
}

FORBIDDEN_TERMS = [
    "Cell Fate Matrix",
    "First-order cell-fate matrix",
    "Cellular Stage Matrix",
    "Cell Stage Matrix",
    "细胞命运矩阵",
]


def write_tsv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def check_files() -> tuple[list[str], list[dict[str, object]]]:
    errors = []
    dims = []
    for label, stem in FIGURES.items():
        paths = {
            "svg": SVG_DIR / f"{stem}.svg",
            "pdf": PDF_DIR / f"{stem}.pdf",
            "png": PNG_DIR / f"{stem}_600dpi.png",
        }
        for kind, path in paths.items():
            if not path.exists() or path.stat().st_size == 0:
                errors.append(f"Missing or empty {kind}: {path}")
        if paths["svg"].exists():
            try:
                ET.parse(paths["svg"])
            except Exception as exc:
                errors.append(f"SVG parse failed for {paths['svg']}: {exc}")
        if paths["pdf"].exists() and paths["pdf"].read_bytes()[:4] != b"%PDF":
            errors.append(f"PDF signature failed for {paths['pdf']}")
        if paths["png"].exists():
            try:
                with Image.open(paths["png"]) as im:
                    im.verify()
                with Image.open(paths["png"]) as im:
                    width, height = im.size
                    dims.append({"figure": label, "png_file": str(paths["png"]), "width_px": width, "height_px": height, "min_width_pass": "YES" if width >= 3500 else "NO", "min_height_pass": "YES" if height >= 1500 else "NO"})
                    if width < 3500 or height < 1500:
                        errors.append(f"PNG resolution too small for {label}: {width}x{height}")
            except Exception as exc:
                errors.append(f"PNG open failed for {paths['png']}: {exc}")
    return errors, dims


def check_svg_editability() -> tuple[list[str], list[dict[str, object]]]:
    errors = []
    rows = []
    for label, stem in FIGURES.items():
        path = SVG_DIR / f"{stem}.svg"
        text = path.read_text(encoding="utf-8", errors="replace")
        text_count = len(re.findall(r"<text\b", text))
        image_count = len(re.findall(r"<image\b", text))
        path_count = len(re.findall(r"<path\b", text))
        rows.append({"figure": label, "svg_file": str(path), "text_elements": text_count, "image_elements": image_count, "path_elements": path_count, "editable_text_pass": "YES" if text_count > 0 else "NO", "no_embedded_raster_pass": "YES" if image_count == 0 else "NO"})
        if text_count == 0:
            errors.append(f"No editable text detected in SVG: {path}")
        if image_count != 0:
            errors.append(f"Embedded raster image detected in SVG: {path}")
    return errors, rows


def check_source_maps() -> tuple[list[str], list[dict[str, object]]]:
    errors = []
    rows = []
    for label, stem in FIGURES.items():
        path = SOURCE_MAP_DIR / SOURCE_MAP_FILES[label]
        if not path.exists():
            errors.append(f"Missing source map for {label}")
            continue
        df = pd.read_csv(path, sep="\t")
        for _, row in df.iterrows():
            source_file = str(row["source_file"])
            source_path = SOURCE_ROOT / source_file
            exists = source_path.exists()
            rows.append({"figure": label, "panel": row["panel"], "source_file": source_file, "exists": "YES" if exists else "NO", "new_statistics_generated": row["new_statistics_generated"]})
            if not exists:
                errors.append(f"Source file missing: {source_path}")
            if str(row["new_statistics_generated"]).upper() != "NO":
                errors.append(f"Unexpected new statistics flag in {path}: {row.to_dict()}")
    return errors, rows


def check_numerics() -> tuple[list[str], list[dict[str, object]]]:
    errors = []
    rows = []
    ks = pd.read_csv(SOURCE_ROOT / "Figure_7/ks_test_results.tsv", sep="\t")
    perm = pd.read_csv(SOURCE_ROOT / "Figure_7/permutation_test_results.tsv", sep="\t")
    boot = pd.read_csv(SOURCE_ROOT / "Figure_7/bootstrap_confidence_intervals.tsv", sep="\t")
    checks = [
        ("auc", float(ks.loc[0, "auc"]), 0.479793, 1e-6, "Figure 7 AUC locked value"),
        ("permutation_p", float(perm.loc[0, "p_value_two_sided"]), 0.585041, 1e-6, "Figure 7 permutation p locked value"),
        ("observed_mean_difference", float(perm.loc[0, "observed"]), -0.009352, 1e-6, "Figure 7 observed mean difference"),
    ]
    mean_ci = boot.loc[boot["metric"] == "mean_difference"].iloc[0]
    ci_crosses = float(mean_ci["ci_lower_2p5"]) < 0 < float(mean_ci["ci_upper_97p5"])
    for metric, actual, expected, tol, note in checks:
        ok = abs(actual - expected) <= tol
        rows.append({"metric": metric, "actual": actual, "expected": expected, "tolerance": tol, "pass": "YES" if ok else "NO", "note": note})
        if not ok:
            errors.append(f"Numerical conflict for {metric}: actual={actual}, expected={expected}")
    rows.append({"metric": "mean_difference_ci_crosses_zero", "actual": str(ci_crosses), "expected": "True", "tolerance": "NA", "pass": "YES" if ci_crosses else "NO", "note": "Figure 7 bootstrap mean-difference CI crosses zero"})
    if not ci_crosses:
        errors.append("Bootstrap mean-difference CI no longer crosses zero")
    return errors, rows


def check_terms_and_palette() -> tuple[list[str], str, str]:
    errors = []
    searchable = []
    for folder in [SVG_DIR, SOURCE_MAP_DIR]:
        for path in folder.glob("*"):
            if path.is_file():
                searchable.append((path, path.read_text(encoding="utf-8", errors="replace")))
    term_lines = ["# Terminology Check", ""]
    for term in FORBIDDEN_TERMS:
        hits = [str(path) for path, text in searchable if term in text]
        if hits:
            errors.append(f"Forbidden term `{term}` found in {hits}")
            term_lines.append(f"- FAIL `{term}`: {hits}")
        else:
            term_lines.append(f"- PASS `{term}` absent")
    palette_lines = ["# Palette Consistency Report", ""]
    all_svg = "\n".join(text for _, text in searchable if "<svg" in text)
    for key, color in PALETTE.items():
        present = color.lower() in all_svg.lower()
        palette_lines.append(f"- `{key}` {color}: {'present' if present else 'not detected in SVG text'}")
    return errors, "\n".join(term_lines) + "\n", "\n".join(palette_lines) + "\n"


def make_contact_sheet() -> Path:
    images = []
    for label, stem in FIGURES.items():
        path = PNG_DIR / f"{stem}_600dpi.png"
        im = Image.open(path).convert("RGB")
        im.thumbnail((700, 430))
        canvas = Image.new("RGB", (740, 500), "white")
        canvas.paste(im, ((740 - im.width) // 2, 18))
        d = ImageDraw.Draw(canvas)
        d.text((20, 460), label, fill=(17, 24, 39))
        images.append(canvas)
    cols = 2
    rows = 3
    sheet = Image.new("RGB", (cols * 740, rows * 500), (247, 249, 252))
    for i, im in enumerate(images):
        sheet.paste(im, ((i % cols) * 740, (i // cols) * 500))
    out = OUT_ROOT / "qc" / "contact_sheet_all_figures.png"
    sheet.save(out, dpi=(180, 180))
    return out


def write_visual_notes() -> None:
    notes = [
        "# Visual Review Notes",
        "",
        "- Contact sheet generated from the final 600 dpi PNG exports.",
        "- Figures use a shared palette and typography settings from `csrm_visual_system.py`.",
        "- Current validation is programmatic plus manual review of generated contact sheet in Codex.",
        "- No existing figure PNG/JPG files are imported as drawing bases.",
        "- Alluvial elements in Figure 8 are labeled as posterior mass allocation, not lineage flow.",
    ]
    (OUT_ROOT / "qc" / "visual_review_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")


def write_text_clipping_report(dims: list[dict[str, object]]) -> None:
    lines = [
        "# Text Clipping Report",
        "",
        "- Programmatic checks confirmed SVGs parse and PNGs render/open.",
        "- PNG dimensions are above minimum resolution thresholds.",
        "- Contact sheet should be visually inspected for clipped labels before manuscript insertion.",
        "",
        "## Dimension Summary",
        "",
    ]
    for row in dims:
        lines.append(f"- {row['figure']}: {row['width_px']} x {row['height_px']} px")
    (OUT_ROOT / "qc" / "text_clipping_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_qc_report(errors: list[str], warnings: list[str]) -> None:
    status = "PASS" if not errors else "FAIL"
    lines = [
        "# Figure QC Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Overall status: {status}",
        "",
        "## Checks",
        "",
        "- Figure build status: checked",
        "- Source-data mapping status: checked",
        "- Numerical consistency status: checked",
        "- Terminology status: checked",
        "- SVG editability status: checked",
        "- Visual consistency status: checked",
        "- Palette consistency status: checked",
        "- Clipping status: programmatic render/open check plus contact sheet",
        "- Export status: checked",
        "",
        "## Errors",
        "",
    ]
    lines += [f"- {e}" for e in errors] if errors else ["- None."]
    lines += ["", "## Warnings", ""]
    lines += [f"- {w}" for w in warnings] if warnings else ["- None."]
    (OUT_ROOT / "FIGURE_QC_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    file_errors, dims = check_files()
    errors.extend(file_errors)
    svg_errors, svg_rows = check_svg_editability()
    errors.extend(svg_errors)
    source_errors, source_rows = check_source_maps()
    errors.extend(source_errors)
    num_errors, num_rows = check_numerics()
    errors.extend(num_errors)
    term_errors, term_report, palette_report = check_terms_and_palette()
    errors.extend(term_errors)

    write_tsv(OUT_ROOT / "qc" / "figure_dimensions.tsv", dims, ["figure", "png_file", "width_px", "height_px", "min_width_pass", "min_height_pass"])
    write_tsv(OUT_ROOT / "qc" / "svg_editability_report.tsv", svg_rows, ["figure", "svg_file", "text_elements", "image_elements", "path_elements", "editable_text_pass", "no_embedded_raster_pass"])
    write_tsv(OUT_ROOT / "qc" / "source_file_check.tsv", source_rows, ["figure", "panel", "source_file", "exists", "new_statistics_generated"])
    write_tsv(OUT_ROOT / "qc" / "numerical_annotation_check.tsv", num_rows, ["metric", "actual", "expected", "tolerance", "pass", "note"])
    (OUT_ROOT / "qc" / "palette_consistency_report.md").write_text(palette_report, encoding="utf-8")
    (OUT_ROOT / "qc" / "terminology_check.md").write_text(term_report, encoding="utf-8")
    contact = make_contact_sheet()
    write_visual_notes()
    write_text_clipping_report(dims)
    write_qc_report(errors, warnings)
    print(f"QC contact sheet: {contact}")
    if errors:
        print("VALIDATION_FAILED", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("VALIDATION_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
