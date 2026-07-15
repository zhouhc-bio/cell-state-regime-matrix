# CSRM Publication Figure System

This directory contains a reproducible SVG-first figure system for the Cell-State Regime Matrix framework.

## Environment

```bash
cd /Users/a1-6/Documents/细胞阶段矩阵
source "Reproducibility_Setup/.venv/bin/activate"
python Figure_Redesign_Output/scripts/build_all_figures.py
python Figure_Redesign_Output/scripts/validate_all_figures.py
```

## Visual Motifs

- Failed Scalar Axis
- Posterior Regime Ribbon
- Cell-State Regime Matrix
- Boundary Branch
- Overlap-Divergence Pair

## Output Structure

- `scripts/`: reproducible build and validation scripts.
- `svg/`: editable source-of-truth vector figures.
- `pdf/`: publication PDF exports.
- `png/`: 600 dpi raster exports from the same figure objects.
- `source_maps/`: panel-level source-data mappings.
- `qc/`: validation tables, reports and contact sheet.

## Source Data

Source data root: `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/02_source_data`

## Figure Intent

- Figure 1A: paradigm shift from failed Phi scalar to CSRM.
- Figure 1: reusable framework icon for observed states, posterior vectors and matrix.
- Figure 6: tumour-like plasticity as a boundary branch, not organized regeneration.
- Figure 7: validation dashboard showing why Phi fails.
- Figure 8: posterior state-regime mixture and matrix/dynamics representation.
- Figure 9: overlap plus divergence as non-compressible regime structure.
- Supplementary Figure 1: partial dry-lab perturbation consistency audit.

## Dependencies

- numpy
- pandas
- matplotlib
- scipy available but not required for new tests
- networkx available but not required by the current build

## Export Specifications

- SVG text is kept editable with `svg.fonttype = none`.
- PDF is exported from the same Matplotlib figure object.
- PNG is exported at 600 dpi.
- Existing figure PNG/JPG files are not used as drawing bases.

## Scientific Limitations

- No scientific data were fabricated.
- No new hypothesis tests, differential analyses, confidence intervals or biological conclusions were generated.
- Transformations are limited to filtering, deterministic sampling for display, grouping, averaging already-defined posterior probabilities and plotting transformations.
- Alluvial/ribbon elements in Figure 8 represent posterior mass allocation only, not lineage flow.

## Built Outputs

- Figure 1A: `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/svg/Figure_1A_paradigm_shift.svg`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/pdf/Figure_1A_paradigm_shift.pdf`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/png/Figure_1A_paradigm_shift_600dpi.png`
- Figure 1: `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/svg/Figure_1_framework_icon.svg`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/pdf/Figure_1_framework_icon.pdf`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/png/Figure_1_framework_icon_600dpi.png`
- Figure 6: `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/svg/Figure_6_boundary_branch.svg`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/pdf/Figure_6_boundary_branch.pdf`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/png/Figure_6_boundary_branch_600dpi.png`
- Figure 7: `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/svg/Figure_7_phi_failure_dashboard.svg`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/pdf/Figure_7_phi_failure_dashboard.pdf`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/png/Figure_7_phi_failure_dashboard_600dpi.png`
- Figure 8: `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/svg/Figure_8_posterior_mixture.svg`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/pdf/Figure_8_posterior_mixture.pdf`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/png/Figure_8_posterior_mixture_600dpi.png`
- Figure 9: `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/svg/Figure_9_overlap_divergence.svg`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/pdf/Figure_9_overlap_divergence.pdf`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/png/Figure_9_overlap_divergence_600dpi.png`
- Supplementary Figure 1: `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/svg/Supplementary_Figure_1_perturbation_consistency.svg`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/pdf/Supplementary_Figure_1_perturbation_consistency.pdf`, `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package/03_code_package/figure_generation/csrm_publication_figure_system/outputs/png/Supplementary_Figure_1_perturbation_consistency_600dpi.png`
