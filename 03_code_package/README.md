# Code Package README

## Computational Environment

The available scripts are Python-based unless otherwise marked in `code_inventory.tsv`. Exact package versions are not fully locked in the current project folder. Bundled Codex workspace Python was used for document/package assembly; upstream analyses likely require standard scientific Python/R packages such as pandas, numpy, scipy, scikit-learn, matplotlib/seaborn and single-cell tooling where applicable.

## Reproducing Score Tables

Use scripts in `scoring/` and available workflow material under `utilities/` or copied `outputs/reproducible_workflows/` where present. Some raw-data preprocessing scripts are missing and are listed in `09_missing_items/missing_code_files.tsv`.

## Reproducing Model-Comparison Outputs

Use `model_comparison/` scripts including representational consistency, Phi invalidation, mixture replacement and regime-conditioned closure scripts.

## Reproducing Figure Source-Data Tables

Figure 2-6 panel-level source TSV files were recovered from the mounted T9 archive and copied into `02_source_data/`. Figure-generation and figure-QA scripts are included where found, but upstream raw-to-processed preprocessing remains only partially archived.

## Regenerating Figures

The current production figure system is in `figure_generation/csrm_publication_figure_system/`. Use `build_all_figures.py` to regenerate Figure 1A, Figure 1 and Figures 6-9 from the supplied `02_source_data/` tables, and use `validate_all_figures.py` for SVG editability, terminology, source-map and numerical checks.

Older scripts retained directly under `figure_generation/` are legacy reconstruction, cleanup or audit scripts. They are preserved for provenance, but the `csrm_publication_figure_system/` directory is the current figure-generation entry point.

## Known Missing Scripts

See `09_missing_items/missing_code_files.tsv`.

## Known Non-Reproducible Or Manually Assembled Elements

Conceptual schematic panels, figure label cleanup, and some final manuscript assembly operations were manually/graphically curated but documented through audit scripts and reports.

## Limitations For Formal Submission

- The available package includes figure-generation, model-comparison, scoring, perturbation-audit and manuscript-support scripts where found.
- The full raw GEO download/preprocessing workflow is not completely archived in this support package.
- A complete environment lockfile is not yet present.
- Before formal submission, generate `requirements.txt` or `environment.yml` from the working environment if possible.
- The package supports computational traceability only; it does not claim wet-lab validation or complete causal closure.
