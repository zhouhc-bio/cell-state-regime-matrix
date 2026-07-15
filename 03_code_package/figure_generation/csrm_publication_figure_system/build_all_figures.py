#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys
from datetime import datetime
from pathlib import Path

from csrm_visual_system import OUT_ROOT, PROJECT_ROOT, SOURCE_ROOT, ensure_dirs


FIGURE_MODULES = [
    ("Figure 1A", "figure_1A_paradigm_shift", "Figure_1A_paradigm_shift"),
    ("Figure 1", "figure_1_framework_icon", "Figure_1_framework_icon"),
    ("Figure 6", "figure_6_boundary_branch", "Figure_6_boundary_branch"),
    ("Figure 7", "figure_7_phi_failure_dashboard", "Figure_7_phi_failure_dashboard"),
    ("Figure 8", "figure_8_posterior_mixture", "Figure_8_posterior_mixture"),
    ("Figure 9", "figure_9_overlap_divergence", "Figure_9_overlap_divergence"),
    ("Supplementary Figure 1", "figure_s1_perturbation_consistency", "Supplementary_Figure_1_perturbation_consistency"),
]


def write_readme(outputs: dict[str, dict[str, str]]) -> None:
    readme = [
        "# CSRM Publication Figure System",
        "",
        "This directory contains a reproducible SVG-first figure system for the Cell-State Regime Matrix framework.",
        "",
        "## Environment",
        "",
        "```bash",
        "cd /Users/a1-6/Documents/细胞阶段矩阵",
        "source \"Reproducibility_Setup/.venv/bin/activate\"",
        "python Figure_Redesign_Output/scripts/build_all_figures.py",
        "python Figure_Redesign_Output/scripts/validate_all_figures.py",
        "```",
        "",
        "## Visual Motifs",
        "",
        "- Failed Scalar Axis",
        "- Posterior Regime Ribbon",
        "- Cell-State Regime Matrix",
        "- Boundary Branch",
        "- Overlap-Divergence Pair",
        "",
        "## Output Structure",
        "",
        "- `scripts/`: reproducible build and validation scripts.",
        "- `svg/`: editable source-of-truth vector figures.",
        "- `pdf/`: publication PDF exports.",
        "- `png/`: 600 dpi raster exports from the same figure objects.",
        "- `source_maps/`: panel-level source-data mappings.",
        "- `qc/`: validation tables, reports and contact sheet.",
        "",
        "## Source Data",
        "",
        f"Source data root: `{SOURCE_ROOT}`",
        "",
        "## Figure Intent",
        "",
        "- Figure 1A: paradigm shift from failed Phi scalar to CSRM.",
        "- Figure 1: reusable framework icon for observed states, posterior vectors and matrix.",
        "- Figure 6: tumour-like plasticity as a boundary branch, not organized regeneration.",
        "- Figure 7: validation dashboard showing why Phi fails.",
        "- Figure 8: posterior state-regime mixture and matrix/dynamics representation.",
        "- Figure 9: overlap plus divergence as non-compressible regime structure.",
        "- Supplementary Figure 1: partial dry-lab perturbation consistency audit.",
        "",
        "## Dependencies",
        "",
        "- numpy",
        "- pandas",
        "- matplotlib",
        "- scipy available but not required for new tests",
        "- networkx available but not required by the current build",
        "",
        "## Export Specifications",
        "",
        "- SVG text is kept editable with `svg.fonttype = none`.",
        "- PDF is exported from the same Matplotlib figure object.",
        "- PNG is exported at 600 dpi.",
        "- Existing figure PNG/JPG files are not used as drawing bases.",
        "",
        "## Scientific Limitations",
        "",
        "- No scientific data were fabricated.",
        "- No new hypothesis tests, differential analyses, confidence intervals or biological conclusions were generated.",
        "- Transformations are limited to filtering, deterministic sampling for display, grouping, averaging already-defined posterior probabilities and plotting transformations.",
        "- Alluvial/ribbon elements in Figure 8 represent posterior mass allocation only, not lineage flow.",
        "",
        "## Built Outputs",
        "",
    ]
    for fig, paths in outputs.items():
        readme.append(f"- {fig}: `{paths['svg']}`, `{paths['pdf']}`, `{paths['png']}`")
    (OUT_ROOT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")


def write_build_report(outputs: dict[str, dict[str, str]], warnings: list[str]) -> None:
    lines = [
        "# Figure Build Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Project root: `{PROJECT_ROOT}`",
        f"Source data root: `{SOURCE_ROOT}`",
        "",
        "## Build Status",
        "",
        "- All six figures were generated from source tables and explicit schematic primitives.",
        "- Existing manuscript figures were not imported as drawing bases.",
        "- No DOCX files were modified.",
        "",
        "## Figure Outputs",
        "",
    ]
    for fig, paths in outputs.items():
        lines += [
            f"### {fig}",
            "",
            f"- SVG: `{paths['svg']}`",
            f"- PDF: `{paths['pdf']}`",
            f"- PNG: `{paths['png']}`",
            "- Visual motif: see v3 Art Director design specification.",
            "- Computation beyond plotting: NO.",
            "- New statistics generated: NO.",
            "",
        ]
    lines += ["## Source Maps", ""]
    for path in sorted((OUT_ROOT / "source_maps").glob("*_source_map.tsv")):
        lines.append(f"- `{path}`")
    lines += ["", "## Warnings", ""]
    if warnings:
        lines.extend(f"- {w}" for w in warnings)
    else:
        lines.append("- None.")
    (OUT_ROOT / "FIGURE_BUILD_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ensure_dirs()
    warnings: list[str] = []
    outputs: dict[str, dict[str, str]] = {}
    try:
        if not SOURCE_ROOT.exists():
            raise FileNotFoundError(f"Missing source data root: {SOURCE_ROOT}")
        for label, module_name, _stem in FIGURE_MODULES:
            module = importlib.import_module(module_name)
            outputs[label] = module.build()
        write_readme(outputs)
        write_build_report(outputs, warnings)
        print(f"Built {len(outputs)} figures in {OUT_ROOT}")
        return 0
    except Exception as exc:
        print(f"BUILD_FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
