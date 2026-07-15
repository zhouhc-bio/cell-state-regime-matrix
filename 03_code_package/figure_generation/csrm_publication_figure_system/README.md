# CSRM Publication Figure System

This directory contains the current production code for the Cell-State Regime Matrix publication figure system.

## Scope

The scripts generate the redesigned publication figures:

- Figure 1A
- Figure 1
- Figure 6
- Figure 7
- Figure 8
- Figure 9
- Supplementary Figure 1

The code locates source tables from the package-level `02_source_data/` directory when run from the repository package layout.

## Entry Points

Run all figures:

```bash
python build_all_figures.py
```

Validate all generated figures:

```bash
python validate_all_figures.py
```

## Current Visual System

Core visual constants and reusable primitives are defined in:

```text
csrm_visual_system.py
```

Individual figure scripts:

```text
figure_1A_paradigm_shift.py
figure_1_framework_icon.py
figure_6_boundary_branch.py
figure_7_phi_failure_dashboard.py
figure_8_posterior_mixture.py
figure_9_overlap_divergence.py
figure_s1_perturbation_consistency.py
```

## Manuscript Support

`update_manuscript_figures.py` was used to replace selected figure media in the local manuscript DOCX files while preserving EndNote field counts. It is included for traceability; it assumes the local manuscript filenames and `Figure_Redesign_Output/png/` paths.

## Notes

Older scripts in `figure_generation/` are retained as legacy reconstruction or cleanup scripts. This `csrm_publication_figure_system/` directory is the current production entry point.

Generated outputs are written to:

```text
outputs/svg/
outputs/pdf/
outputs/png/
outputs/source_maps/
outputs/qc/
```
