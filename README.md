# Cell-State Regime Matrix support package

This repository contains source-data tables and analysis code for the Cell-State Regime Matrix framework.

The package is organized for inspection, reuse, and archival release:

- `02_source_data/`: figure-level and panel-level source-data tables, validation summaries, model-comparison outputs, posterior-regime summaries, and supplementary source tables.
- `03_code_package/`: scripts for scoring, model comparison, perturbation audit, manuscript support, and the current publication figure-generation system.
- `TERMINOLOGY_UPDATE_LOG.md`: terminology migration record for the current Cell-State Regime Matrix naming standard.

## Current figure-generation entry point

The current publication figure system is located at:

```text
03_code_package/figure_generation/csrm_publication_figure_system/
```

Use `build_all_figures.py` to regenerate the current framework figures from the supplied source-data tables. Use `validate_all_figures.py` to check SVG editability, terminology consistency, source-map coverage, and numerical consistency.

Older scripts retained elsewhere in `03_code_package/figure_generation/` document reconstruction, cleanup, and audit steps. They are preserved for provenance.

## Source-data status

The source-data package contains mapped source tables for the figure panels and supporting validation reports. See:

```text
02_source_data/source_data_master_index.tsv
02_source_data/source_data_completeness_report_FINAL.md
```

## Reproducibility notes

The included code supports computational traceability for the analyses and figures represented in this package. Some upstream raw-data preprocessing steps remain partially archived rather than fully locked in this repository. The package should therefore be cited as a support package for source data, figure reconstruction, and computational provenance.

## Citation

Please cite the archived release DOI generated from this repository. Repository-level citation metadata is provided in `CITATION.cff` and `.zenodo.json`.

## License

Code in `03_code_package/` is released under the MIT License. Source-data tables and documentation in `02_source_data/` are released under Creative Commons Attribution 4.0 International unless a source file states otherwise.
