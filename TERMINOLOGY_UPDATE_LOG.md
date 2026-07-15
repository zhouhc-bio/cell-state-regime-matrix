# GitHub Package Minimal Terminology Update Log

Generated: 2026-07-14T23:33:02

## Inputs

- Source data: `/Users/a1-6/Library/Group Containers/group.com.apple.notes/Accounts/448B657F-32D7-4470-9632-3D71F62A2E0A/Media/8D191378-A3CA-45AB-9A50-587FBA8CD3C5/1_103BFF73-DB40-401E-BA6F-E3BA1BA912EE/02_source_data`
- Code package: `/Users/a1-6/Library/Group Containers/group.com.apple.notes/Accounts/448B657F-32D7-4470-9632-3D71F62A2E0A/Media/F86767E6-8E88-44B3-8AB4-7AFD4C7783B9/1_973180E1-0B5C-4DD7-B1E5-A1EC95C119AE/03_code_package`

## Output

- Revised package: `/Users/a1-6/Documents/细胞阶段矩阵/GitHub_Term_Revised_Package`

## Scope

- Copied originals first; original Apple Notes attachment folders were not modified.
- Edited only text-like files: `.py`, `.md`, `.tsv`, `.csv`, `.txt`, `.json`, `.yml`, `.yaml`, `.rst`.
- Did not rename files, directories, Python identifiers, data columns, dataset IDs, figure numbers, or numeric values.
- Did not edit binary/image files.

## Replacement Summary

- Files changed: 40
- Total replacements/cleanups: 311

- `latent_state_regime`: 279
- `latent_state_regime_cn`: 6
- `posterior_precision`: 20
- `theory_name_en`: 6

## Controlled Terminology Applied

- `Cell Fate Matrix` -> `Cell-State Regime Matrix` when used as the project theory name.
- `First-order Cell Fate Matrix` -> `First-order Cell-State Regime Matrix` when used as the project theory name.
- `细胞命运矩阵` -> `细胞状态—状态域矩阵`; `一阶细胞命运矩阵` -> `一阶细胞状态—状态域矩阵`.
- `latent regime` / `latent-regime` -> `latent state regime` / `latent-state-regime` for model-Z display text.
- Selected ambiguous figure labels using `posterior regime` were clarified as `posterior regime assignment` or `posterior regime probability`.

## Standard Terms Deliberately Retained

- `cell fate`, `fate probability`, `terminal fate`, `fate mapping`, and related field-standard uses were not globally replaced.
- `CellRank`, `Palantir`, `RNA velocity`, `PAGA`, `pseudotime`, `trajectory inference`, `stemness`, `plasticity`, `regeneration`, `repair`, `attractor`, and `basin` were retained.
- Existing file names such as `latent_regime...` and data tables such as `regime_posterior...` were retained to preserve reproducibility paths.

## Changed Files

- `02_source_data/Figure_1/README.md`: latent_state_regime=2
- `02_source_data/Figure_1/inconsistency_report.md`: latent_state_regime=2
- `02_source_data/Figure_1/model_architecture_reconstruction.md`: latent_state_regime=6
- `02_source_data/Figure_1/model_evolution_map_caption.md`: latent_state_regime=1
- `02_source_data/Figure_1/model_lineage_section.md`: latent_state_regime=1
- `02_source_data/Figure_1/project_state_summary.md`: latent_state_regime=6
- `02_source_data/Figure_1/single_phi_model_invalidation.md`: latent_state_regime=3
- `02_source_data/Figure_1/submission_readiness_report.md`: latent_state_regime=2
- `02_source_data/Figure_1A/README.md`: latent_state_regime=1
- `02_source_data/Figure_1A/model_architecture_reconstruction.md`: latent_state_regime=6
- `02_source_data/Figure_1A/single_phi_model_invalidation.md`: latent_state_regime=3
- `02_source_data/Figure_7/single_phi_model_invalidation.md`: latent_state_regime=3
- `02_source_data/Figure_8/README.md`: latent_state_regime=2
- `02_source_data/Supplementary_Figure_1/final_closure_state_report.md`: latent_state_regime=1
- `02_source_data/source_data_master_index.tsv`: latent_state_regime=13
- `03_code_package/code_inventory.tsv`: latent_state_regime=4
- `03_code_package/figure_generation/complete_figure_1_to_6_manifest.py`: latent_state_regime=1
- `03_code_package/figure_generation/final_lock_figures_and_audit.py`: latent_state_regime=20, posterior_precision=3
- `03_code_package/figure_generation/old_new_figure_integration_audit.py`: latent_state_regime=28
- `03_code_package/figure_generation/reconstruct_final_9figures.py`: latent_state_regime=6
- `03_code_package/figure_generation/redesign_sparse_data_figures.py`: latent_state_regime=2
- `03_code_package/figure_generation/rerender_clean_figures.py`: latent_state_regime=6, posterior_precision=2
- `03_code_package/figure_generation/structural_figure_recovery.py`: latent_state_regime=2
- `03_code_package/model_comparison/add_model_evolution_map.py`: latent_state_regime=9
- `03_code_package/model_comparison/causal_closure_consistency_validation.py`: latent_state_regime=5
- `03_code_package/model_comparison/integrate_causal_consistency_into_manuscript.py`: latent_state_regime=4, posterior_precision=1
- `03_code_package/model_comparison/replace_phi_with_regime_mixture.py`: latent_state_regime=9
- `03_code_package/model_comparison/representational_consistency_analysis.py`: latent_state_regime=3
- `03_code_package/perturbation_audit/regime_conditioned_causal_dynamics_v2.py`: latent_state_regime=2
- `03_code_package/utilities/apply_scu_undergraduate_format.py`: latent_state_regime_cn=1
- `03_code_package/utilities/assemble_final_submission_package.py`: latent_state_regime=2
- `03_code_package/utilities/build_endnote_safe_package.py`: latent_state_regime=8, latent_state_regime_cn=5, posterior_precision=1
- `03_code_package/utilities/build_natcomms_support_package.py`: latent_state_regime=9, theory_name_en=1
- `03_code_package/utilities/build_polished_bilingual_manuscripts.py`: latent_state_regime=14, posterior_precision=5
- `03_code_package/utilities/final_nature_cell_manuscript.py`: latent_state_regime=22
- `03_code_package/utilities/finalize_manuscript.py`: latent_state_regime=15, posterior_precision=6
- `03_code_package/utilities/predictive_superiority_benchmark.py`: latent_state_regime=5
- `03_code_package/utilities/rewrite_manuscript_locked_9fig.py`: latent_state_regime=30
- `03_code_package/utilities/story_strengthening_endnote_safe.py`: latent_state_regime=1, posterior_precision=1, theory_name_en=5
- `03_code_package/utilities/submission_stabilization.py`: latent_state_regime=20, posterior_precision=1

## Residual Old-Term Check

### old_theory_terms
- PASS: no residual hits in text-like files.

### bad_double_terms
- PASS: no residual hits in text-like files.

## Python Syntax Check

- PASS: all `.py` files in `03_code_package` compiled successfully.

## File Counts

```json
{
  "02_source_data": {
    ".md": 30,
    ".tsv": 80,
    "[no_ext]": 1
  },
  "03_code_package": {
    ".md": 1,
    ".py": 43,
    ".tsv": 1
  }
}
```

## Scientific Content

- Changed scientific content: NO.
- Terminology-only migration for GitHub re-upload: YES.
